from django.core.management.base import BaseCommand
from portfolio.models_currency import Currency, ExchangeRate
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate sample exchange rates for testing (USD, EUR, GBP only)'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        # Sample exchange rates (these are approximate and for testing only)
        sample_rates = [
            # USD to others
            ('USD', 'EUR', '0.85'),
            ('USD', 'GBP', '0.73'),

            # EUR to others
            ('EUR', 'USD', '1.18'),
            ('EUR', 'GBP', '0.86'),

            # GBP to others
            ('GBP', 'USD', '1.37'),
            ('GBP', 'EUR', '1.16'),
        ]

        created_count = 0
        updated_count = 0

        for from_curr, to_curr, rate_str in sample_rates:
            # Check if both currencies exist and are active
            if not Currency.objects.filter(code=from_curr, is_active=True).exists():
                self.stdout.write(f"Skipping {from_curr} - currency not active")
                continue

            if not Currency.objects.filter(code=to_curr, is_active=True).exists():
                self.stdout.write(f"Skipping {to_curr} - currency not active")
                continue

            rate_obj, created = ExchangeRate.objects.update_or_create(
                from_currency=from_curr,
                to_currency=to_curr,
                date=today,
                defaults={
                    'rate': Decimal(rate_str),
                    'source': 'manual_sample'
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f"Created: {from_curr}/{to_curr} = {rate_str}")
            else:
                updated_count += 1
                self.stdout.write(f"Updated: {from_curr}/{to_curr} = {rate_str}")

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {created_count} rates created, {updated_count} rates updated'
            )
        )

        # Show what currencies are active
        active_currencies = Currency.objects.filter(is_active=True).values_list('code', flat=True)
        self.stdout.write(f"Active currencies: {', '.join(active_currencies)}")

        self.stdout.write(
            self.style.WARNING(
                '\nNote: These are sample rates for testing. '
                'Use setup_exchange_rates command to fetch real rates from an API.'
            )
        )