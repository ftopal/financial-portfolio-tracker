from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Security, PriceHistory, Transaction
import yfinance as yf
from decimal import Decimal
from datetime import timedelta
from .services.currency_service import CurrencyService
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def update_exchange_rates(self, base_currencies=None, target_currencies=None):
    """Update exchange rates from external API"""
    try:
        logger.info("Starting exchange rate update")
        CurrencyService.update_exchange_rates(base_currencies, target_currencies)
        logger.info("Exchange rate update completed successfully")
        return "Exchange rates updated successfully"
    except Exception as e:
        logger.error(f"Failed to update exchange rates: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def update_portfolio_base_amounts():
    """Update base amounts for all transactions"""
    from .models import Transaction
    from django.utils import timezone

    # Get transactions that need base amount calculation
    transactions = Transaction.objects.filter(
        base_amount__isnull=True
    ).select_related('portfolio', 'security')

    updated_count = 0
    for transaction in transactions:
        try:
            if transaction.currency != transaction.portfolio.currency:
                exchange_rate = CurrencyService.get_exchange_rate(
                    transaction.currency,
                    transaction.portfolio.currency,
                    transaction.transaction_date.date()
                )
                if exchange_rate:
                    transaction.exchange_rate = exchange_rate
                    transaction.base_amount = (
                            transaction.quantity * transaction.price * exchange_rate
                    )
                    transaction.save(update_fields=['exchange_rate', 'base_amount'])
                    updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update transaction {transaction.id}: {e}")

    logger.info(f"Updated base amounts for {updated_count} transactions")
    return f"Updated {updated_count} transactions"


@shared_task(bind=True, max_retries=3)
def update_security_price(self, security_id):
    """Update a single security price"""
    try:
        security = Security.objects.get(id=security_id)

        if security.security_type == 'CRYPTO':
            # For crypto, you might want to use a different API
            # For now, we'll try yfinance which supports some crypto
            symbol = f"{security.symbol}-USD"
        else:
            symbol = security.symbol

        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Get current price
        current_price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('price') or
                info.get('ask') or
                info.get('bid')
        )

        if not current_price:
            # Try to get price from history
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]

        if not current_price:
            raise ValueError(f"No price data available for {security.symbol}")

        # Update security
        old_price = security.current_price
        security.current_price = Decimal(str(current_price))
        security.last_updated = timezone.now()

        # Update additional fields if available
        if info.get('dayHigh'):
            security.day_high = Decimal(str(info.get('dayHigh')))
        if info.get('dayLow'):
            security.day_low = Decimal(str(info.get('dayLow')))
        if info.get('volume'):
            security.volume = info.get('volume')
        if info.get('marketCap'):
            security.market_cap = info.get('marketCap')
        if info.get('trailingPE'):
            security.pe_ratio = Decimal(str(info.get('trailingPE')))

        security.save()

        # Record price history
        PriceHistory.objects.create(
            security=security,
            date=timezone.now(),
            open_price=Decimal(str(info.get('open', current_price))),
            high_price=security.day_high,
            low_price=security.day_low,
            close_price=security.current_price,
            volume=security.volume
        )

        # Check for significant price changes (optional alert)
        if old_price:
            price_change_pct = ((float(current_price) - float(old_price)) / float(old_price) * 100)
            if abs(price_change_pct) > 5:  # 5% change
                send_price_alert.delay(security.id, price_change_pct)

        logger.info(f"Updated {security.symbol}: ${old_price} -> ${current_price}")
        return {'symbol': security.symbol, 'price': float(current_price)}

    except Security.DoesNotExist:
        logger.error(f"Security with id {security_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error updating security {security_id}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def update_all_security_prices():
    """Update all security prices"""
    # Optional: Check if market is open
    from .utils import is_market_open
    if hasattr(settings, 'CHECK_MARKET_HOURS') and settings.CHECK_MARKET_HOURS:
        if not is_market_open():
            logger.info("Market is closed, skipping price update")
            return {'message': 'Market closed', 'updated': 0}

    # Update only active securities
    securities = Security.objects.filter(is_active=True)
    results = {'updated': 0, 'failed': 0, 'securities': []}

    for security in securities:
        try:
            # Use sub-task for each security
            update_security_price.delay(security.id)
            results['updated'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"Failed to queue update for {security.symbol}: {str(e)}")

    logger.info(f"Queued price updates: {results['updated']} securities")
    return results


@shared_task
def update_securities_by_type(security_type):
    """Update all securities of a specific type"""
    securities = Security.objects.filter(
        is_active=True,
        security_type=security_type
    )

    results = {'updated': 0, 'failed': 0}

    for security in securities:
        try:
            update_security_price.delay(security.id)
            results['updated'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"Failed to queue update for {security.symbol}: {str(e)}")

    return results


@shared_task
def send_price_alert(security_id, change_percentage):
    """Send email alert for significant price changes"""
    try:
        security = Security.objects.get(id=security_id)
        # Get all users who own this security
        user_emails = Transaction.objects.filter(
            security=security,
            transaction_type='BUY'
        ).values_list('user__email', flat=True).distinct()

        subject = f"Price Alert: {security.symbol} {'↑' if change_percentage > 0 else '↓'} {abs(change_percentage):.2f}%"
        message = f"""
        {security.name} ({security.symbol}) has moved {change_percentage:.2f}% today.

        Current Price: ${security.current_price}
        Day High: ${security.day_high}
        Day Low: ${security.day_low}

        Check your portfolio for more details.
        """

        for email in user_emails:
            if email:  # Only send if user has email
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=True,
                )

        logger.info(f"Sent price alerts for {security.symbol} to {len(user_emails)} users")
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
def update_portfolio_performance(portfolio_id):
    """Calculate and cache portfolio performance metrics"""
    from .models import Portfolio
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        summary = portfolio.get_summary()
        logger.info(f"Updated performance for portfolio {portfolio.name}: {summary}")
        return summary
    except Portfolio.DoesNotExist:
        logger.error(f"Portfolio {portfolio_id} not found")
        return None


# Manual trigger tasks for testing
@shared_task
def test_celery():
    """Test task to verify Celery is working"""
    logger.info("Celery is working!")
    return "Celery task executed successfully!"