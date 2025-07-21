from datetime import date, timedelta, datetime
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Security, Transaction, PriceHistory, Portfolio, PortfolioValueHistory, CashTransaction
from .tasks import auto_backfill_on_security_creation, fetch_historical_prices_task, portfolio_transaction_trigger_task, calculate_daily_portfolio_snapshots, auto_backfill_on_security_creation
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Security)
def trigger_price_backfill_on_security_creation(sender, instance, created, **kwargs):
    """
    Automatically trigger price backfill when a new security is created
    """
    if created and instance.is_active:
        logger.info(f"New security created: {instance.symbol}, triggering price backfill")

        # Trigger async backfill task
        auto_backfill_on_security_creation.delay(
            security_id=instance.id,
            days_back=365  # Default 1 year of historical data
        )


@receiver(post_save, sender=Transaction)
def trigger_backfill_on_historical_transaction(sender, instance, created, **kwargs):
    """
    Trigger backfill when a historical transaction is added
    This ensures we have price data for the transaction date
    """
    if created:
        transaction_date = instance.transaction_date.date()
        today = timezone.now().date()  # Now this will work correctly

        # If transaction is more than 7 days old, we might need historical price data
        if (today - transaction_date).days > 7:

            # Check if we have price data for this security around the transaction date
            price_exists = PriceHistory.objects.filter(
                security=instance.security,
                date__date__gte=transaction_date - timedelta(days=7),
                date__date__lte=transaction_date + timedelta(days=7)
            ).exists()

            if not price_exists:
                logger.info(f"Historical transaction detected for {instance.security.symbol} "
                            f"on {transaction_date}, triggering price backfill")

                # Calculate date range to backfill
                start_date = transaction_date - timedelta(days=30)  # Get some buffer
                end_date = today

                # Trigger backfill task
                fetch_historical_prices_task.delay(
                    security_id=instance.security.id,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    force_update=False
                )


# Enhanced signal for when securities are updated
@receiver(post_save, sender=Security)
def handle_security_symbol_change(sender, instance, created, **kwargs):
    """
    Handle when a security symbol is changed - might need to re-fetch price data
    """
    if not created:
        # Check if symbol changed
        try:
            original = Security.objects.get(pk=instance.pk)
            if hasattr(original, '_state') and original._state.adding:
                return  # This is a new object, not an update

            # Compare with database version to detect symbol changes
            if original.symbol != instance.symbol:
                logger.info(f"Security symbol changed from {original.symbol} to {instance.symbol}")

                # You might want to:
                # 1. Archive old price data
                # 2. Fetch new price data for the new symbol
                # 3. Alert administrators

                # For now, just fetch recent price data for the new symbol
                fetch_historical_prices_task.delay(
                    security_id=instance.id,
                    days_back=30,  # Just get recent data
                    force_update=True
                )

        except Security.DoesNotExist:
            # This shouldn't happen, but handle gracefully
            pass


@receiver(post_delete, sender=Security)
def cleanup_price_data_on_security_deletion(sender, instance, **kwargs):
    """
    Optionally clean up price data when a security is deleted
    """
    # Note: Due to foreign key constraints, price data will be deleted automatically
    # This signal is here in case you want to add logging or other cleanup
    logger.info(f"Security {instance.symbol} deleted, price data will be cleaned up automatically")


@receiver(post_save, sender=Transaction)
def trigger_portfolio_recalculation_on_transaction_save(sender, instance, created, **kwargs):
    """
    Trigger portfolio recalculation when a transaction is created or updated

    This ensures portfolio value history is automatically updated whenever
    transactions are added or modified.
    """
    try:
        # Get the portfolio
        portfolio = instance.portfolio

        # Get the transaction date
        transaction_date = instance.transaction_date.date() if hasattr(instance.transaction_date,
                                                                       'date') else instance.transaction_date

        # Determine trigger type
        trigger_type = 'create' if created else 'update'

        logger.info(f"Transaction {trigger_type} detected for portfolio {portfolio.name} on {transaction_date}")

        # Trigger async recalculation
        # We use apply_async with a small delay to avoid overwhelming the system
        # if multiple transactions are being processed in bulk
        portfolio_transaction_trigger_task.apply_async(
            args=[portfolio.id, transaction_date.isoformat()],
            countdown=5  # Wait 5 seconds before processing
        )

        logger.info(f"Portfolio recalculation task queued for {portfolio.name}")

    except Exception as e:
        logger.error(f"Error triggering portfolio recalculation: {str(e)}")


@receiver(post_delete, sender=Transaction)
def trigger_portfolio_recalculation_on_transaction_delete(sender, instance, **kwargs):
    """
    Trigger portfolio recalculation when a transaction is deleted

    This ensures portfolio value history is recalculated when transactions
    are removed.
    """
    try:
        # Get the portfolio
        portfolio = instance.portfolio

        # Get the transaction date
        transaction_date = instance.transaction_date.date() if hasattr(instance.transaction_date,
                                                                       'date') else instance.transaction_date

        logger.info(f"Transaction deletion detected for portfolio {portfolio.name} on {transaction_date}")

        # Trigger async recalculation from the deleted transaction date
        portfolio_transaction_trigger_task.apply_async(
            args=[portfolio.id, transaction_date.isoformat()],
            countdown=5  # Wait 5 seconds before processing
        )

        logger.info(f"Portfolio recalculation task queued for {portfolio.name} after deletion")

    except Exception as e:
        logger.error(f"Error triggering portfolio recalculation after deletion: {str(e)}")


@receiver(post_save, sender=Portfolio)
def initialize_portfolio_history_on_creation(sender, instance, created, **kwargs):
    """
    Initialize portfolio history when a new portfolio is created

    This creates an initial snapshot for new portfolios.
    """
    if created:
        try:
            logger.info(f"New portfolio created: {instance.name}")

            # Create initial snapshot for today
            from .services.portfolio_history_service import PortfolioHistoryService

            # Use apply_async to avoid blocking the creation process
            from celery import current_app
            current_app.send_task(
                'portfolio.tasks.portfolio_transaction_trigger_task',
                args=[instance.id, None],  # None means full recalculation
                countdown=10  # Wait 10 seconds to ensure portfolio is fully created
            )

            logger.info(f"Initial portfolio history calculation queued for {instance.name}")

        except Exception as e:
            logger.error(f"Error initializing portfolio history for {instance.name}: {str(e)}")


@receiver(post_save, sender=CashTransaction)
def trigger_portfolio_recalculation_on_cash_transaction(sender, instance, created, **kwargs):
    """
    Trigger portfolio recalculation when cash transactions are added/modified
    """
    if created:
        try:
            portfolio = instance.cash_account.portfolio

            # FIXED: Proper date handling for both datetime and date objects
            if hasattr(instance.transaction_date, 'date'):
                # It's a datetime object
                transaction_date = instance.transaction_date.date()
            elif isinstance(instance.transaction_date, date):
                # It's already a date object
                transaction_date = instance.transaction_date
            else:
                # It's a string, convert it
                if isinstance(instance.transaction_date, str):
                    transaction_date = datetime.strptime(instance.transaction_date, '%Y-%m-%d').date()
                else:
                    transaction_date = instance.transaction_date

            logger.info(f"Cash transaction detected for portfolio {portfolio.name} on {transaction_date}")

            # FIXED: Ensure we're passing a proper date string
            portfolio_transaction_trigger_task.apply_async(
                args=[portfolio.id, transaction_date.isoformat()],
                countdown=5
            )

            logger.info(f"Portfolio recalculation task queued for {portfolio.name} due to cash transaction")

        except Exception as e:
            logger.error(f"Error triggering portfolio recalculation for cash transaction: {str(e)}")


# =====================
# ENHANCED SECURITY SIGNAL HANDLERS
# =====================

@receiver(post_save, sender='portfolio.Security')
def enhanced_auto_backfill_on_security_creation(sender, instance, created, **kwargs):
    """
    Enhanced version of security creation handler that also triggers
    portfolio recalculation for portfolios holding the security
    """
    if created:
        try:
            logger.info(f"New security created: {instance.symbol}")

            # Trigger original backfill task
            auto_backfill_on_security_creation.delay(instance.id)

            # Find portfolios that have transactions for this security
            portfolios_with_security = Portfolio.objects.filter(
                transactions__security=instance
            ).distinct()

            if portfolios_with_security.exists():
                logger.info(f"Found {portfolios_with_security.count()} portfolios with {instance.symbol}")

                # Trigger recalculation for each portfolio
                for portfolio in portfolios_with_security:
                    # Find the earliest transaction date for this security
                    earliest_transaction = Transaction.objects.filter(
                        portfolio=portfolio,
                        security=instance
                    ).order_by('date').first()

                    if earliest_transaction:
                        transaction_date = earliest_transaction.date.date() if hasattr(earliest_transaction.date,
                                                                                       'date') else earliest_transaction.date

                        # Trigger recalculation
                        portfolio_transaction_trigger_task.apply_async(
                            args=[portfolio.id, transaction_date.isoformat()],
                            countdown=60  # Wait 1 minute to allow price backfill to complete
                        )

                        logger.info(
                            f"Portfolio recalculation queued for {portfolio.name} due to new security {instance.symbol}")

        except Exception as e:
            logger.error(f"Error in enhanced security creation handler: {str(e)}")


# =====================
# PORTFOLIO HISTORY MAINTENANCE SIGNALS
# =====================

@receiver(post_save, sender=PortfolioValueHistory)
def log_portfolio_snapshot_creation(sender, instance, created, **kwargs):
    """
    Log when portfolio snapshots are created or updated

    This helps with monitoring and debugging the portfolio history system.
    """
    if created:
        logger.info(f"Portfolio snapshot created: {instance.portfolio.name} on {instance.date} "
                    f"(${instance.total_value:,.2f})")
    else:
        logger.info(f"Portfolio snapshot updated: {instance.portfolio.name} on {instance.date} "
                    f"(${instance.total_value:,.2f})")


# =====================
# BULK OPERATION HELPERS
# =====================

def bulk_trigger_portfolio_recalculation(portfolio_ids=None, start_date=None):
    """
    Utility function to trigger bulk portfolio recalculation

    Args:
        portfolio_ids: List of portfolio IDs to recalculate (None for all)
        start_date: Start date for recalculation (None for full recalculation)
    """
    try:
        # Get portfolios to process
        if portfolio_ids:
            portfolios = Portfolio.objects.filter(id__in=portfolio_ids, is_active=True)
        else:
            portfolios = Portfolio.objects.filter(is_active=True)

        if not portfolios.exists():
            logger.warning("No portfolios found for bulk recalculation")
            return

        # Determine start date
        if start_date is None:
            # Find the earliest transaction date across all portfolios
            earliest_transaction = Transaction.objects.filter(
                portfolio__in=portfolios
            ).order_by('date').first()

            if earliest_transaction:
                start_date = earliest_transaction.date.date() if hasattr(earliest_transaction.date,
                                                                         'date') else earliest_transaction.date

        # Trigger recalculation for each portfolio
        for i, portfolio in enumerate(portfolios):
            # Stagger the tasks to avoid overwhelming the system
            countdown = i * 10  # 10 second intervals

            portfolio_transaction_trigger_task.apply_async(
                args=[portfolio.id, start_date.isoformat() if start_date else None],
                countdown=countdown
            )

            logger.info(f"Bulk recalculation queued for {portfolio.name} (delay: {countdown}s)")

        logger.info(f"Bulk recalculation triggered for {len(portfolios)} portfolios")

    except Exception as e:
        logger.error(f"Error in bulk portfolio recalculation: {str(e)}")


def trigger_daily_snapshots_for_date(target_date=None):
    """
    Utility function to trigger daily snapshots for a specific date

    Args:
        target_date: Date to calculate snapshots for (defaults to today)
    """
    try:
        if target_date is None:
            target_date = date.today()

        # Convert date to string for task
        date_string = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)

        # Trigger daily snapshots task
        calculate_daily_portfolio_snapshots.delay(date_string)

        logger.info(f"Daily snapshots task triggered for {target_date}")

    except Exception as e:
        logger.error(f"Error triggering daily snapshots: {str(e)}")


# =====================
# SIGNAL DEBUGGING HELPERS
# =====================

def enable_portfolio_signal_debugging():
    """
    Enable detailed logging for portfolio signals
    """
    portfolio_logger = logging.getLogger('portfolio.signals')
    portfolio_logger.setLevel(logging.DEBUG)

    # Add console handler if not already present
    if not portfolio_logger.handlers:
        import sys
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        portfolio_logger.addHandler(handler)

    logger.info("Portfolio signal debugging enabled")


def disable_portfolio_signal_debugging():
    """
    Disable detailed logging for portfolio signals
    """
    portfolio_logger = logging.getLogger('portfolio.signals')
    portfolio_logger.setLevel(logging.INFO)

    logger.info("Portfolio signal debugging disabled")


# =====================
# SIGNAL MONITORING
# =====================

class PortfolioSignalMonitor:
    """
    Monitor portfolio signal activity for debugging and performance analysis
    """

    def __init__(self):
        self.transaction_signals = 0
        self.portfolio_signals = 0
        self.security_signals = 0
        self.start_time = timezone.now()

    def reset_counters(self):
        """Reset all signal counters"""
        self.transaction_signals = 0
        self.portfolio_signals = 0
        self.security_signals = 0
        self.start_time = timezone.now()

    def get_statistics(self):
        """Get signal statistics"""
        elapsed = timezone.now() - self.start_time

        return {
            'transaction_signals': self.transaction_signals,
            'portfolio_signals': self.portfolio_signals,
            'security_signals': self.security_signals,
            'elapsed_time': elapsed.total_seconds(),
            'signals_per_second': (
                    (self.transaction_signals + self.portfolio_signals + self.security_signals) /
                    elapsed.total_seconds()
            ) if elapsed.total_seconds() > 0 else 0
        }


# Global monitor instance
_signal_monitor = PortfolioSignalMonitor()


def get_signal_monitor():
    """Get the global signal monitor instance"""
    return _signal_monitor


# =====================
# SIGNAL HANDLER DECORATORS
# =====================

def monitor_signal(signal_type):
    """
    Decorator to monitor signal handler execution

    Args:
        signal_type: Type of signal ('transaction', 'portfolio', 'security')
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                # Increment counter
                if signal_type == 'transaction':
                    _signal_monitor.transaction_signals += 1
                elif signal_type == 'portfolio':
                    _signal_monitor.portfolio_signals += 1
                elif signal_type == 'security':
                    _signal_monitor.security_signals += 1

                # Execute original function
                result = func(*args, **kwargs)

                logger.debug(f"Signal handler {func.__name__} executed successfully")

                return result

            except Exception as e:
                logger.error(f"Error in signal handler {func.__name__}: {str(e)}")
                raise

        return wrapper

    return decorator


# =====================
# ENHANCED SIGNAL HANDLERS WITH MONITORING
# =====================

# Update the original signal handlers to include monitoring
@receiver(post_save, sender=Transaction)
@monitor_signal('transaction')
def monitored_trigger_portfolio_recalculation_on_transaction_save(sender, instance, created, **kwargs):
    """
    Enhanced version of transaction save handler with monitoring
    """
    return trigger_portfolio_recalculation_on_transaction_save(sender, instance, created, **kwargs)


@receiver(post_delete, sender=Transaction)
@monitor_signal('transaction')
def monitored_trigger_portfolio_recalculation_on_transaction_delete(sender, instance, **kwargs):
    """
    Enhanced version of transaction delete handler with monitoring
    """
    return trigger_portfolio_recalculation_on_transaction_delete(sender, instance, **kwargs)


@receiver(post_save, sender=Portfolio)
@monitor_signal('portfolio')
def monitored_initialize_portfolio_history_on_creation(sender, instance, created, **kwargs):
    """
    Enhanced version of portfolio creation handler with monitoring
    """
    return initialize_portfolio_history_on_creation(sender, instance, created, **kwargs)


# =====================
# CONDITIONAL SIGNAL HANDLERS
# =====================

def enable_auto_portfolio_recalculation():
    """
    Enable automatic portfolio recalculation on transaction changes
    """
    # This can be used to toggle the behavior via settings
    from django.conf import settings
    settings.PORTFOLIO_AUTO_RECALCULATION = True
    logger.info("Automatic portfolio recalculation enabled")


def disable_auto_portfolio_recalculation():
    """
    Disable automatic portfolio recalculation on transaction changes
    """
    from django.conf import settings
    settings.PORTFOLIO_AUTO_RECALCULATION = False
    logger.info("Automatic portfolio recalculation disabled")


def is_auto_recalculation_enabled():
    """
    Check if automatic portfolio recalculation is enabled
    """
    from django.conf import settings
    return getattr(settings, 'PORTFOLIO_AUTO_RECALCULATION', True)


# =====================
# BATCH OPERATION HELPERS
# =====================

class BatchOperationContext:
    """
    Context manager to disable signals during batch operations
    """

    def __init__(self, disable_signals=True):
        self.disable_signals = disable_signals
        self.original_state = None

    def __enter__(self):
        if self.disable_signals:
            from django.conf import settings
            self.original_state = getattr(settings, 'PORTFOLIO_AUTO_RECALCULATION', True)
            settings.PORTFOLIO_AUTO_RECALCULATION = False
            logger.info("Signals disabled for batch operation")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.disable_signals and self.original_state is not None:
            from django.conf import settings
            settings.PORTFOLIO_AUTO_RECALCULATION = self.original_state
            logger.info("Signals re-enabled after batch operation")


# =====================
# SIGNAL TESTING UTILITIES
# =====================

def test_signal_handlers():
    """
    Test all signal handlers to ensure they're working correctly
    """
    try:
        from django.test.utils import override_settings

        # Test transaction signal
        portfolio = Portfolio.objects.filter(is_active=True).first()
        if portfolio:
            # Create a test transaction
            from .models import Security
            security = Security.objects.first()

            if security:
                transaction = Transaction.objects.create(
                    portfolio=portfolio,
                    security=security,
                    type='BUY',
                    quantity=1,
                    price=100.00,
                    date=timezone.now(),
                    description='Test transaction for signal testing'
                )

                logger.info("Test transaction created - signal should have fired")

                # Clean up
                transaction.delete()
                logger.info("Test transaction deleted - signal should have fired")

                return True

        return False

    except Exception as e:
        logger.error(f"Error testing signal handlers: {str(e)}")
        return False


def get_portfolio_settings():
    """
    Get portfolio-related settings with defaults
    """
    from django.conf import settings

    return {
        'auto_recalculation': getattr(settings, 'PORTFOLIO_AUTO_RECALCULATION', True),
        'signal_debugging': getattr(settings, 'PORTFOLIO_SIGNAL_DEBUGGING', False),
        'batch_delay': getattr(settings, 'PORTFOLIO_BATCH_RECALCULATION_DELAY', 300),
        'queue_name': getattr(settings, 'PORTFOLIO_RECALCULATION_QUEUE', 'celery')
    }


# =====================
# INITIALIZATION
# =====================

def initialize_portfolio_signals():
    """
    Initialize portfolio signal system
    """
    try:
        settings = get_portfolio_settings()

        if settings['signal_debugging']:
            enable_portfolio_signal_debugging()

        logger.info("Portfolio signal system initialized")
        logger.info(f"Auto recalculation: {settings['auto_recalculation']}")
        logger.info(f"Signal debugging: {settings['signal_debugging']}")
        logger.info(f"Batch delay: {settings['batch_delay']} seconds")

    except Exception as e:
        logger.error(f"Error initializing portfolio signals: {str(e)}")


# Initialize on module import
initialize_portfolio_signals()
