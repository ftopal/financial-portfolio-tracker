import yfinance as yf
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from ..models import Security
import logging

logger = logging.getLogger(__name__)


class StockImportService:
    """Service to import and search stocks from Yahoo Finance"""

    @staticmethod
    def search_and_import_stock(symbol):
        """Search for a stock and import it if found"""
        try:
            # Check if already exists
            existing_stock = Stock.objects.filter(symbol__iexact=symbol).first()
            if existing_stock:
                return {'exists': True, 'stock': existing_stock}

            # Fetch from Yahoo Finance
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info

            # Check if valid stock
            if not info or 'symbol' not in info:
                return {'exists': False, 'error': 'Stock not found'}

            # Extract information
            stock_data = {
                'symbol': info.get('symbol', symbol.upper()),
                'name': info.get('longName') or info.get('shortName', symbol),
                'exchange': info.get('exchange', ''),
                'currency': info.get('currency', 'USD'),
                'country': info.get('country', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'current_price': Decimal(str(info.get('currentPrice', 0) or info.get('regularMarketPrice', 0) or 0)),
                'market_cap': info.get('marketCap'),
                'pe_ratio': Decimal(str(info.get('trailingPE', 0))) if info.get('trailingPE') else None,
                'day_high': Decimal(str(info.get('dayHigh', 0))) if info.get('dayHigh') else None,
                'day_low': Decimal(str(info.get('dayLow', 0))) if info.get('dayLow') else None,
                'volume': info.get('volume'),
                'week_52_high': Decimal(str(info.get('fiftyTwoWeekHigh', 0))) if info.get('fiftyTwoWeekHigh') else None,
                'week_52_low': Decimal(str(info.get('fiftyTwoWeekLow', 0))) if info.get('fiftyTwoWeekLow') else None,
            }

            # Determine asset type
            if 'ETF' in stock_data['name'].upper() or info.get('quoteType') == 'ETF':
                stock_data['asset_type'] = 'ETF'
            elif info.get('quoteType') == 'CRYPTOCURRENCY':
                stock_data['asset_type'] = 'CRYPTO'
            else:
                stock_data['asset_type'] = 'STOCK'

            # Create stock
            stock = Stock.objects.create(**stock_data)
            logger.info(f"Imported new stock: {stock}")

            return {'exists': False, 'stock': stock, 'created': True}

        except Exception as e:
            logger.error(f"Error importing stock {symbol}: {str(e)}")
            return {'exists': False, 'error': str(e)}

    @staticmethod
    def search_stocks(query):
        """Search for stocks in database"""
        if not query or len(query) < 1:
            return []

        # Search in database first
        stocks = Stock.objects.filter(
            Q(symbol__icontains=query) |  # Use Q instead of models.Q
            Q(name__icontains=query)
        ).filter(is_active=True)[:10]

        return stocks