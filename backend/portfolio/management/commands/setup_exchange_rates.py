from django.core.management.base import BaseCommand
from portfolio.services.currency_service import CurrencyService
from portfolio.models_currency import Currency, ExchangeRate
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Setup exchange rates for active currencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if rates exist'
        )

    def handle(self, *args, **kwargs):
        force_update = kwargs['force']

        # Get active currencies
        active_currencies = list(Currency.objects.filter(is_active=True).values_list('code', flat=True))

        if not active_currencies:
            self.stdout.write(
                self.style.WARNING('No active currencies found. Run load_currencies first.')
            )
            return

        self.stdout.write(f"Active currencies: {', '.join(active_currencies)}")

        # Check if we already have recent exchange rates
        today = timezone.now().date()
        existing_rates = ExchangeRate.objects.filter(
            date=today,
            from_currency__in=active_currencies,
            to_currency__in=active_currencies
        ).count()

        if existing_rates > 0 and not force_update:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Exchange rates already exist for today ({existing_rates} rates). '
                    'Use --force to update anyway.'
                )
            )
            return

        # Fetch exchange rates
        self.stdout.write('Fetching exchange rates from external API...')

        try:
            CurrencyService.update_exchange_rates(
                base_currencies=active_currencies,
                target_currencies=active_currencies
            )

            # Count the rates we now have
            new_rates = ExchangeRate.objects.filter(
                date=today,
                from_currency__in=active_currencies,
                to_currency__in=active_currencies
            ).count()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully fetched {new_rates} exchange rates for {len(active_currencies)} currencies'
                )
            )

            # Display some sample rates
            sample_rates = ExchangeRate.objects.filter(
                date=today,
                from_currency__in=active_currencies,
                to_currency__in=active_currencies
            )[:5]

            if sample_rates:
                self.stdout.write('\nSample exchange rates:')
                for rate in sample_rates:
                    self.stdout.write(
                        f'  {rate.from_currency}/{rate.to_currency}: {rate.rate}'
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to fetch exchange rates: {e}')
            )

            # Provide guidance
            self.stdout.write(
                self.style.WARNING(
                    '\nIf you continue to have issues:\n'
                    '1. Check your internet connection\n'
                    '2. Consider setting EXCHANGE_RATE_API_KEY in your environment\n'
                    '3. Or manually add exchange rates through the admin interface'
                )
            )