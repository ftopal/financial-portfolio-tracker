import yfinance as yf
import logging
from decimal import Decimal
from django.utils import timezone
from ..models import Stock

logger = logging.getLogger(__name__)


class StockService:
    """Service for managing stock data and prices"""

    @staticmethod
    def get_or_create_stock(symbol, name=None, asset_type='STOCK'):
        """Get existing stock or create new one with current price"""
        try:
            stock = Stock.objects.get(symbol=symbol.upper())
            return stock
        except Stock.DoesNotExist:
            # Fetch data from Yahoo Finance
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info

            # Get stock info
            stock_name = name or info.get('longName', info.get('shortName', symbol))
            current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)

            # Create stock
            stock = Stock.objects.create(
                symbol=symbol.upper(),
                name=stock_name,
                asset_type=asset_type,
                current_price=Decimal(str(current_price)),
                exchange=info.get('exchange', ''),
                currency=info.get('currency', 'USD'),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                day_high=info.get('dayHigh'),
                day_low=info.get('dayLow'),
                volume=info.get('volume')
            )

            logger.info(f"Created new stock: {stock}")
            return stock

    @staticmethod
    def update_stock_price(stock):
        """Update single stock price"""
        try:
            ticker = yf.Ticker(stock.symbol)
            info = ticker.info

            current_price = info.get('currentPrice') or info.get('regularMarketPrice')

            if current_price:
                stock.current_price = Decimal(str(current_price))
                stock.day_high = info.get('dayHigh')
                stock.day_low = info.get('dayLow')
                stock.volume = info.get('volume')
                stock.market_cap = info.get('marketCap')
                stock.pe_ratio = info.get('trailingPE')
                stock.last_updated = timezone.now()
                stock.save()

                # Record price history
                from ..models import PriceHistory
                PriceHistory.objects.create(
                    asset=None,  # We'll update PriceHistory model
                    stock=stock,
                    price=stock.current_price,
                    volume=stock.volume,
                    date=timezone.now()
                )

                logger.info(f"Updated {stock.symbol}: ${current_price}")
                return True
            else:
                logger.warning(f"No price data for {stock.symbol}")
                return False

        except Exception as e:
            logger.error(f"Error updating {stock.symbol}: {str(e)}")
            return False

    @staticmethod
    def update_all_stock_prices():
        """Update all stock prices in database"""
        stocks = Stock.objects.all()
        updated = 0
        failed = 0

        for stock in stocks:
            if StockService.update_stock_price(stock):
                updated += 1
            else:
                failed += 1

        logger.info(f"Price update complete: {updated} updated, {failed} failed")
        return {'updated': updated, 'failed': failed}