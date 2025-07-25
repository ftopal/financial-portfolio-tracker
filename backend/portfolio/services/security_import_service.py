import yfinance as yf
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from ..models import Security
import logging

logger = logging.getLogger(__name__)


class SecurityImportService:
    """Service to import and search stocks from Yahoo Finance"""

    @staticmethod
    def search_and_import_security(symbol):
        """Search for a stock and import it if found"""
        try:
            # Clean the symbol
            symbol = symbol.strip().upper()

            # Check if already exists
            existing_security = Security.objects.filter(symbol__iexact=symbol).first()
            if existing_security:
                logger.info(f"Security {symbol} already exists")
                return {'exists': True, 'security': existing_security}

            # Fetch from Yahoo Finance
            logger.info(f"Fetching {symbol} from Yahoo Finance")
            ticker = yf.Ticker(symbol)

            # Try to get ticker info
            try:
                info = ticker.info
            except Exception as e:
                logger.error(f"Failed to get info for {symbol}: {str(e)}")
                return {'exists': False, 'error': f'Symbol {symbol} not found on Yahoo Finance'}

            # Check if we got valid data
            if not info or (isinstance(info, dict) and not info.get('symbol')):
                # Sometimes yfinance returns empty dict for invalid symbols
                logger.warning(f"No data returned for {symbol}")
                return {'exists': False, 'error': f'Symbol {symbol} not found or invalid'}

            # Get current price - try multiple fields
            current_price = None
            price_fields = ['currentPrice', 'regularMarketPrice', 'price', 'previousClose', 'ask', 'bid']

            for field in price_fields:
                if info.get(field):
                    current_price = info.get(field)
                    break

            # If still no price, try to get from recent history
            if not current_price:
                try:
                    hist = ticker.history(period="5d")
                    if not hist.empty and 'Close' in hist.columns:
                        current_price = float(hist['Close'].iloc[-1])
                except Exception as e:
                    logger.error(f"Failed to get history for {symbol}: {str(e)}")

            if not current_price:
                logger.warning(f"No price data available for {symbol}")
                current_price = 0  # Set to 0 rather than failing

            # Get currency from Yahoo Finance
            currency = info.get('currency', 'USD')

            # IMPROVED: More intelligent currency detection for UK securities
            display_currency = currency

            if currency == 'GBP' and symbol.endswith('.L'):
                # This is a UK security, but we need to determine if it's quoted in pence or pounds
                exchange = info.get('exchange', '').lower()
                quote_type = info.get('quoteType', '').upper()
                security_name = (info.get('longName') or info.get('shortName') or symbol).upper()

                # More precise logic for determining GBp vs GBP
                is_lse_security = ('lse' in exchange or 'london' in exchange)

                if is_lse_security:
                    # Use multiple criteria to determine if this should be GBp (pence) or GBP (pounds)

                    # ETFs and Trusts are more likely to be quoted in GBP (pounds)
                    is_likely_gbp = (
                            quote_type == 'ETF' or
                            'ETF' in security_name or
                            'TRUST' in security_name or
                            'FUND' in security_name or
                            'INVESTMENT' in security_name
                    )

                    # Individual stocks are more likely to be quoted in GBp (pence)
                    is_likely_gbp_pence = (
                            quote_type == 'EQUITY' or
                            current_price > 50  # High prices often indicate pence pricing
                    )

                    # Price analysis: If price is very low (< 10), it's likely already in pounds
                    # If price is high (> 50), it's likely in pence
                    if current_price > 0:
                        if current_price < 10 and is_likely_gbp:
                            # Low price + ETF/Trust = likely quoted in GBP
                            display_currency = 'GBP'
                            logger.info(f"{symbol}: Using GBP (low price + ETF/Trust characteristics)")
                        elif current_price > 50:
                            # High price = likely quoted in pence
                            display_currency = 'GBp'
                            logger.info(f"{symbol}: Using GBp (high price suggests pence)")
                        elif is_likely_gbp:
                            # ETF/Trust with reasonable price = likely GBP
                            display_currency = 'GBP'
                            logger.info(f"{symbol}: Using GBP (ETF/Trust characteristics)")
                        else:
                            # Default for individual stocks = pence
                            display_currency = 'GBp'
                            logger.info(f"{symbol}: Using GBp (default for individual stocks)")
                    else:
                        # No price data, use type-based heuristics
                        if is_likely_gbp:
                            display_currency = 'GBP'
                            logger.info(f"{symbol}: Using GBP (ETF/Trust, no price data)")
                        else:
                            display_currency = 'GBp'
                            logger.info(f"{symbol}: Using GBp (default, no price data)")
                else:
                    # Not LSE, keep as GBP
                    display_currency = 'GBP'

            # Extract stock information with safe defaults
            stock_data = {
                'symbol': info.get('symbol', symbol).upper(),
                'name': info.get('longName') or info.get('shortName') or symbol,
                'exchange': info.get('exchange', ''),
                'currency': display_currency,
                'country': info.get('country', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'current_price': Decimal(str(current_price)),
                'market_cap': info.get('marketCap'),
                'volume': info.get('volume'),
                'is_active': True,
                'data_source': 'yahoo',
                'last_updated': timezone.now()
            }

            # Add optional numeric fields with safe conversion
            optional_fields = {
                'pe_ratio': 'trailingPE',
                'day_high': 'dayHigh',
                'day_low': 'dayLow',
                'week_52_high': 'fiftyTwoWeekHigh',
                'week_52_low': 'fiftyTwoWeekLow',
                'dividend_yield': 'dividendYield'
            }

            for db_field, yahoo_field in optional_fields.items():
                value = info.get(yahoo_field)
                if value is not None:
                    try:
                        stock_data[db_field] = Decimal(str(value))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid {yahoo_field} value for {symbol}: {value}")

            # Determine security type
            quote_type = info.get('quoteType', '').upper()

            if quote_type == 'ETF' or 'ETF' in stock_data['name'].upper():
                stock_data['security_type'] = 'ETF'
            elif quote_type == 'CRYPTOCURRENCY':
                stock_data['security_type'] = 'CRYPTO'
            elif quote_type == 'INDEX':
                stock_data['security_type'] = 'INDEX'
            elif quote_type == 'MUTUALFUND':
                stock_data['security_type'] = 'MUTUAL_FUND'
            else:
                stock_data['security_type'] = 'STOCK'

            # Create security
            security = Security.objects.create(**stock_data)
            logger.info(f"Successfully imported security: {security} with currency: {display_currency}")

            return {
                'exists': False,
                'security': security,
                'created': True
            }

        except Exception as e:
            logger.error(f"Error importing security {symbol}: {str(e)}")
            return {
                'exists': False,
                'error': f'Failed to import {symbol}: {str(e)}'
            }

    @staticmethod
    def search_securities(query):
        """Search for securities in database"""
        if not query or len(query) < 1:
            return []

        # Search in database
        securities = Security.objects.filter(
            Q(symbol__icontains=query) |
            Q(name__icontains=query)
        ).filter(is_active=True).order_by('symbol')[:20]

        return securities

    @staticmethod
    def update_security_price(security):
        """Update a single security's price"""
        try:
            symbol = security.symbol
            if security.security_type == 'CRYPTO':
                symbol = f"{security.symbol}-USD"

            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get current price
            current_price = None
            price_fields = ['currentPrice', 'regularMarketPrice', 'price', 'previousClose']

            for field in price_fields:
                if info.get(field):
                    current_price = info.get(field)
                    break

            if current_price:
                security.current_price = Decimal(str(current_price))
                security.last_updated = timezone.now()

                # Update other fields if available
                if info.get('dayHigh'):
                    security.day_high = Decimal(str(info.get('dayHigh')))
                if info.get('dayLow'):
                    security.day_low = Decimal(str(info.get('dayLow')))
                if info.get('volume'):
                    security.volume = info.get('volume')

                security.save()
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating price for {security.symbol}: {str(e)}")
            return False