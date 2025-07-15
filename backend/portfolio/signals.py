# Replace the content of backend/portfolio/signals.py with this fixed version

from datetime import timedelta
from django.utils import timezone  # Use Django's timezone instead of datetime.timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Security, Transaction, PriceHistory
from .tasks import auto_backfill_on_security_creation, fetch_historical_prices_task
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