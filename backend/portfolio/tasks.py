from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Security, PriceHistory, Transaction
import yfinance as yf
from decimal import Decimal
from .services.currency_service import CurrencyService
from .services.price_history_service import PriceHistoryService
from datetime import date, timedelta, datetime, time
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
    """Remove price history older than 10 year"""
    cutoff_date = timezone.now() - timedelta(days=10*365)
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


@shared_task(bind=True, max_retries=3)
def sync_daily_exchange_rates(self):
    """
    Fetch yesterday's exchange rates to ensure we have historical data
    This runs daily to catch any missed rates
    """
    from datetime import date, timedelta
    from django.conf import settings
    from .models_currency import ExchangeRate
    import requests
    from decimal import Decimal

    try:
        # Get yesterday's date (markets are closed, rates are final)
        yesterday = date.today() - timedelta(days=1)

        # Skip weekends (no forex trading)
        if yesterday.weekday() >= 5:  # 5=Saturday, 6=Sunday
            logger.info(f"Skipping weekend date: {yesterday}")
            return f"Skipped weekend date: {yesterday}"

        # Check if we already have yesterday's rates
        existing_rates = ExchangeRate.objects.filter(date=yesterday).count()
        if existing_rates >= 6:  # We expect 6 rates: USD/EUR, EUR/USD, USD/GBP, GBP/USD, EUR/GBP, GBP/EUR
            logger.info(f"Yesterday's rates already exist: {yesterday}")
            return f"Rates already exist for {yesterday}"

        logger.info(f"Fetching exchange rates for {yesterday}")

        # Get API key
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)

        # Currency pairs we need
        currency_pairs = [
            ('USD', 'EUR'),
            ('USD', 'GBP'),
            ('EUR', 'GBP'),
        ]

        rates_fetched = 0

        for base_currency, target_currency in currency_pairs:
            try:
                # Build API URL for historical data
                if api_key:
                    # Paid API with historical endpoint
                    url = f"https://v6.exchangerate-api.com/v6/{api_key}/history/{base_currency}/{yesterday.year}/{yesterday.month}/{yesterday.day}"
                else:
                    # Free alternative with historical data
                    url = f"https://api.exchangerate.host/{yesterday}?base={base_currency}&symbols={target_currency}"

                response = requests.get(url, timeout=15)
                response.raise_for_status()
                data = response.json()

                # Parse response based on API
                if api_key:
                    # Paid exchangerate-api.com format
                    rates = data.get('conversion_rates', {})
                else:
                    # exchangerate.host format
                    rates = data.get('rates', {})

                if target_currency in rates:
                    rate_value = Decimal(str(rates[target_currency]))

                    # Store the rate (both directions)
                    ExchangeRate.objects.update_or_create(
                        from_currency=base_currency,
                        to_currency=target_currency,
                        date=yesterday,
                        defaults={
                            'rate': rate_value,
                            'source': 'exchangerate-api.com' if api_key else 'exchangerate.host'
                        }
                    )

                    # Store inverse rate
                    inverse_rate = Decimal('1') / rate_value
                    ExchangeRate.objects.update_or_create(
                        from_currency=target_currency,
                        to_currency=base_currency,
                        date=yesterday,
                        defaults={
                            'rate': inverse_rate,
                            'source': 'exchangerate-api.com' if api_key else 'exchangerate.host'
                        }
                    )

                    rates_fetched += 2
                    logger.info(f"Saved daily rate {base_currency}/{target_currency}: {rate_value}")

                # Small delay between requests
                import time
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Failed to fetch {base_currency}/{target_currency} for {yesterday}: {e}")
                continue

        logger.info(f"Daily rate sync complete: {rates_fetched} rates saved for {yesterday}")
        return f"Synced {rates_fetched} rates for {yesterday}"

    except Exception as e:
        logger.error(f"Daily rate sync failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_old_exchange_rates():
    """
    Clean up very old exchange rates (keep last 5 years)
    This prevents the database from growing too large
    """
    from datetime import date, timedelta
    from .models_currency import ExchangeRate

    # Keep last 5 years of data
    cutoff_date = date.today() - timedelta(days=20 * 365)

    deleted_count = ExchangeRate.objects.filter(date__lt=cutoff_date).delete()[0]
    logger.info(f"Cleaned up {deleted_count} old exchange rate records (older than {cutoff_date})")

    return {'deleted': deleted_count, 'cutoff_date': str(cutoff_date)}


@shared_task(bind=True, max_retries=3)
def fetch_historical_prices_task(self, security_id, start_date=None, end_date=None, days_back=365, force_update=False):
    """
    Background task to fetch historical prices for a security

    Args:
        security_id: int, ID of the security
        start_date: str (YYYY-MM-DD) or None
        end_date: str (YYYY-MM-DD) or None
        days_back: int, if start_date not provided, go back this many days
        force_update: bool, whether to overwrite existing data
    """
    try:
        security = Security.objects.get(id=security_id)

        # Parse dates
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = date.today() - timedelta(days=days_back)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()

        logger.info(f"Starting historical price fetch for {security.symbol} ({start_date} to {end_date})")

        # Fetch historical data
        result = PriceHistoryService.bulk_fetch_historical_prices(
            security, start_date, end_date, force_update
        )

        if result['success']:
            logger.info(f"Successfully fetched historical prices for {security.symbol}: {result}")
            return result
        else:
            logger.error(f"Failed to fetch historical prices for {security.symbol}: {result['error']}")
            raise Exception(result['error'])

    except Security.DoesNotExist:
        logger.error(f"Security with id {security_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error fetching historical prices for security {security_id}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def backfill_security_prices_task(self, security_id, days_back=365, force_update=False):
    """
    Background task to backfill missing historical prices for a security
    """
    try:
        security = Security.objects.get(id=security_id)

        logger.info(f"Starting price backfill for {security.symbol} ({days_back} days)")

        result = PriceHistoryService.backfill_security_prices(
            security, days_back, force_update
        )

        if result['success']:
            logger.info(f"Successfully backfilled prices for {security.symbol}: {result}")
        else:
            logger.warning(f"Backfill completed with issues for {security.symbol}: {result}")

        return result

    except Security.DoesNotExist:
        logger.error(f"Security with id {security_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error backfilling prices for security {security_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=120 * (self.request.retries + 1))


@shared_task
def backfill_all_securities_task(days_back=365, batch_size=10, force_update=False):
    """
    Backfill historical prices for all active securities

    Args:
        days_back: int, how many days back to fetch
        batch_size: int, how many securities to process in parallel
        force_update: bool, whether to overwrite existing data
    """
    try:
        # Get all active securities that don't have recent price data
        securities = Security.objects.filter(is_active=True)

        # Filter to securities that actually need backfill
        securities_needing_backfill = []

        for security in securities:
            # Check if we have recent price data
            recent_price = PriceHistory.objects.filter(
                security=security,
                date__date__gte=date.today() - timedelta(days=7)
            ).exists()

            if not recent_price or force_update:
                securities_needing_backfill.append(security)

        logger.info(f"Found {len(securities_needing_backfill)} securities needing price backfill")

        total_processed = 0
        total_success = 0

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(securities_needing_backfill), batch_size):
            batch = securities_needing_backfill[i:i + batch_size]

            # Submit batch of tasks
            job_group = []
            for security in batch:
                job = backfill_security_prices_task.delay(
                    security.id, days_back, force_update
                )
                job_group.append(job)

            # Wait for batch to complete before starting next batch
            for job in job_group:
                try:
                    result = job.get(timeout=300)  # 5 minute timeout per security
                    total_processed += 1
                    if result and result.get('success'):
                        total_success += 1
                except Exception as e:
                    logger.error(f"Batch job failed: {str(e)}")
                    total_processed += 1

            # Rate limiting between batches
            if i + batch_size < len(securities_needing_backfill):
                time.sleep(30)  # 30 second pause between batches

        logger.info(f"Backfill complete: {total_success}/{total_processed} securities processed successfully")

        return {
            'total_securities': len(securities_needing_backfill),
            'processed': total_processed,
            'successful': total_success,
            'failed': total_processed - total_success
        }

    except Exception as e:
        logger.error(f"Error in bulk backfill task: {str(e)}")
        raise


@shared_task
def detect_and_fill_price_gaps_task(security_id=None, max_gap_days=7):
    """
    Detect and fill gaps in price data

    Args:
        security_id: int or None (if None, process all securities)
        max_gap_days: int, maximum gap size to fill
    """
    try:
        if security_id:
            securities = [Security.objects.get(id=security_id)]
        else:
            securities = Security.objects.filter(is_active=True)

        total_gaps_filled = 0
        securities_processed = 0

        for security in securities:
            try:
                result = PriceHistoryService.fill_price_gaps(security, max_gap_days)

                if result['success']:
                    total_gaps_filled += result.get('gaps_filled', 0)
                    securities_processed += 1

                    if result.get('gaps_filled', 0) > 0:
                        logger.info(f"Filled {result['gaps_filled']} gaps for {security.symbol}")

                # Rate limiting
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error filling gaps for {security.symbol}: {str(e)}")
                continue

        logger.info(f"Gap filling complete: {total_gaps_filled} gaps filled across {securities_processed} securities")

        return {
            'securities_processed': securities_processed,
            'total_gaps_filled': total_gaps_filled
        }

    except Exception as e:
        logger.error(f"Error in gap filling task: {str(e)}")
        raise


@shared_task
def validate_all_price_data_task():
    """
    Validate price data integrity for all securities
    """
    try:
        securities = Security.objects.filter(is_active=True)
        validation_results = []

        for security in securities:
            result = PriceHistoryService.validate_price_data(security)
            result['security_symbol'] = security.symbol
            result['security_id'] = security.id
            validation_results.append(result)

        # Summary statistics
        total_securities = len(validation_results)
        valid_securities = sum(1 for r in validation_results if r.get('valid', False))
        securities_with_gaps = sum(1 for r in validation_results if r.get('gaps', 0) > 0)

        logger.info(f"Price data validation complete: {valid_securities}/{total_securities} securities valid, "
                    f"{securities_with_gaps} securities have gaps")

        return {
            'total_securities': total_securities,
            'valid_securities': valid_securities,
            'securities_with_gaps': securities_with_gaps,
            'details': validation_results
        }

    except Exception as e:
        logger.error(f"Error in price data validation task: {str(e)}")
        raise


@shared_task(bind=True, max_retries=3)
def auto_backfill_on_security_creation(self, security_id, days_back=365):
    """
    Automatically triggered when a new security is created
    Backfills historical data for the new security
    """
    try:
        security = Security.objects.get(id=security_id)

        logger.info(f"Auto-backfilling price data for newly created security: {security.symbol}")

        # Wait a bit to ensure the security is fully saved
        time.sleep(2)

        result = PriceHistoryService.backfill_security_prices(security, days_back)

        if result['success']:
            logger.info(f"Auto-backfill successful for {security.symbol}: {result}")
        else:
            logger.warning(f"Auto-backfill had issues for {security.symbol}: {result}")

        return result

    except Security.DoesNotExist:
        logger.error(f"Security with id {security_id} not found for auto-backfill")
        raise
    except Exception as exc:
        logger.error(f"Error in auto-backfill for security {security_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# Manual trigger tasks for testing
@shared_task
def test_celery():
    """Test task to verify Celery is working"""
    logger.info("Celery is working!")
    return "Celery task executed successfully!"