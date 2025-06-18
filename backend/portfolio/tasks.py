from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Stock, PriceHistory, Asset
import yfinance as yf
from decimal import Decimal
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def update_stock_price(self, stock_id):
    """Update a single stock price"""
    try:
        stock = Stock.objects.get(id=stock_id)
        ticker = yf.Ticker(stock.symbol)
        info = ticker.info

        # Get current price
        current_price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('price')
        )

        if not current_price:
            raise ValueError(f"No price data available for {stock.symbol}")

        # Update stock
        old_price = stock.current_price
        stock.current_price = Decimal(str(current_price))
        stock.last_updated = timezone.now()
        stock.day_high = Decimal(str(info.get('dayHigh', 0))) if info.get('dayHigh') else None
        stock.day_low = Decimal(str(info.get('dayLow', 0))) if info.get('dayLow') else None
        stock.volume = info.get('volume')
        stock.market_cap = info.get('marketCap')
        stock.pe_ratio = Decimal(str(info.get('trailingPE', 0))) if info.get('trailingPE') else None
        stock.save()

        # Record price history
        PriceHistory.objects.create(
            stock=stock,
            price=stock.current_price,
            volume=stock.volume
        )

        # Check for significant price changes (optional alert)
        price_change_pct = ((current_price - float(old_price)) / float(old_price) * 100) if old_price else 0
        if abs(price_change_pct) > 5:  # 5% change
            send_price_alert.delay(stock.id, price_change_pct)

        logger.info(f"Updated {stock.symbol}: ${old_price} -> ${current_price} ({price_change_pct:.2f}%)")
        return {'symbol': stock.symbol, 'price': float(current_price), 'change_pct': price_change_pct}

    except Stock.DoesNotExist:
        logger.error(f"Stock with id {stock_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error updating stock {stock_id}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def update_all_stock_prices():
    """Update all stock prices"""
    # Check if market is open (optional)
    from .utils import is_market_open
    if not is_market_open():
        logger.info("Market is closed, skipping price update")
        return {'message': 'Market closed', 'updated': 0}

    stocks = Stock.objects.all()
    results = {'updated': 0, 'failed': 0, 'stocks': []}

    for stock in stocks:
        try:
            # Use sub-task for each stock
            result = update_stock_price.delay(stock.id)
            results['updated'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"Failed to queue update for {stock.symbol}: {str(e)}")

    logger.info(f"Queued price updates: {results['updated']} stocks")
    return results


@shared_task
def send_price_alert(stock_id, change_percentage):
    """Send email alert for significant price changes"""
    try:
        stock = Stock.objects.get(id=stock_id)
        # Get all users who own this stock
        users = Asset.objects.filter(stock=stock).values_list('user__email', flat=True).distinct()

        subject = f"Price Alert: {stock.symbol} {'↑' if change_percentage > 0 else '↓'} {abs(change_percentage):.2f}%"
        message = f"""
        {stock.name} ({stock.symbol}) has moved {change_percentage:.2f}% today.

        Current Price: ${stock.current_price}
        Day High: ${stock.day_high}
        Day Low: ${stock.day_low}

        Check your portfolio for more details.
        """

        for email in users:
            if email:  # Only send if user has email
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=True,
                )

        logger.info(f"Sent price alerts for {stock.symbol} to {len(users)} users")
    except Exception as e:
        logger.error(f"Error sending price alert: {str(e)}")


@shared_task
def cleanup_old_price_history():
    """Remove price history older than 1 year"""
    cutoff_date = timezone.now() - timedelta(days=365)
    deleted_count = PriceHistory.objects.filter(date__lt=cutoff_date).delete()[0]
    logger.info(f"Deleted {deleted_count} old price history records")
    return {'deleted': deleted_count}


@shared_task
def calculate_portfolio_performance(user_id):
    """Calculate and cache portfolio performance metrics"""
    # This is for future enhancement
    pass