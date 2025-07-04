from django.core.management.base import BaseCommand
from django.conf import settings
from portfolio.models_currency import Currency, ExchangeRate
from datetime import datetime, timedelta
import requests
import time
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch historical exchange rates for USD, EUR, GBP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date in YYYY-MM-DD format (default: 2020-01-01)',
            default='2020-01-01'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date in YYYY-MM-DD format (default: yesterday)',
            default=None
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing rates',
        )

    def handle(self, *args, **options):
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        force_update = options['force']

        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            self.stdout.write(self.style.ERROR('Invalid start date format. Use YYYY-MM-DD'))
            return

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid end date format. Use YYYY-MM-DD'))
                return
        else:
            # Default to yesterday
            end_date = (datetime.now() - timedelta(days=1)).date()

        if start_date > end_date:
            self.stdout.write(self.style.ERROR('Start date must be before end date'))
            return

        # Get API key
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)

        if not api_key:
            self.stdout.write(
                self.style.WARNING(
                    'No EXCHANGE_RATE_API_KEY found. Using free tier (limited requests).\n'
                    'Add EXCHANGE_RATE_API_KEY to your .env file for higher limits.'
                )
            )

        # Currency pairs we need (avoiding redundant pairs)
        currency_pairs = [
            ('USD', 'EUR'),
            ('USD', 'GBP'),
            ('EUR', 'GBP'),
        ]

        self.stdout.write(f'Fetching historical rates from {start_date} to {end_date}')
        self.stdout.write(f'Currency pairs: {currency_pairs}')

        total_fetched = 0
        total_skipped = 0
        errors = 0

        # Iterate through dates
        current_date = start_date
        while current_date <= end_date:
            self.stdout.write(f'Processing {current_date}...')

            # Check if we already have data for this date (unless force update)
            if not force_update:
                existing_rates = ExchangeRate.objects.filter(date=current_date).count()
                if existing_rates >= len(currency_pairs) * 2:  # We store both directions
                    self.stdout.write(f'  Skipping {current_date} - data already exists')
                    total_skipped += 1
                    current_date += timedelta(days=1)
                    continue

            try:
                # Fetch rates for this date
                rates_fetched = self.fetch_rates_for_date(current_date, currency_pairs, api_key, force_update)
                total_fetched += rates_fetched

                # Be nice to the API - wait between requests
                time.sleep(0.5)  # 500ms delay

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error fetching rates for {current_date}: {e}'))
                errors += 1

            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(
                f'Historical rate fetch complete!\n'
                f'Total fetched: {total_fetched} rates\n'
                f'Total skipped: {total_skipped} dates\n'
                f'Errors: {errors}'
            )
        )

    def fetch_rates_for_date(self, date, currency_pairs, api_key, force_update):
        """Fetch exchange rates for a specific date"""
        rates_fetched = 0

        for base_currency, target_currency in currency_pairs:
            try:
                # Check if we already have this rate
                if not force_update:
                    existing = ExchangeRate.objects.filter(
                        from_currency=base_currency,
                        to_currency=target_currency,
                        date=date
                    ).exists()
                    if existing:
                        continue

                # Build API URL for historical data
                if api_key:
                    # Paid API with historical endpoint
                    url = f"https://v6.exchangerate-api.com/v6/{api_key}/history/{base_currency}/{date.year}/{date.month}/{date.day}"
                else:
                    # For free tier, we'll use a different approach
                    # exchangerate-api.com free tier doesn't support historical data
                    # We'll try to use exchangerate.host (free alternative with historical data)
                    url = f"https://api.exchangerate.host/{date}?base={base_currency}&symbols={target_currency}"

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

                    # Store the rate
                    ExchangeRate.objects.update_or_create(
                        from_currency=base_currency,
                        to_currency=target_currency,
                        date=date,
                        defaults={
                            'rate': rate_value,
                            'source': 'exchangerate-api.com' if api_key else 'exchangerate.host'
                        }
                    )

                    # Also store the inverse rate
                    inverse_rate = Decimal('1') / rate_value
                    ExchangeRate.objects.update_or_create(
                        from_currency=target_currency,
                        to_currency=base_currency,
                        date=date,
                        defaults={
                            'rate': inverse_rate,
                            'source': 'exchangerate-api.com' if api_key else 'exchangerate.host'
                        }
                    )

                    rates_fetched += 2  # We stored both directions
                    self.stdout.write(f'  Saved {base_currency}/{target_currency}: {rate_value}')

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Failed to fetch {base_currency}/{target_currency}: {e}'))
                continue

        return rates_fetched