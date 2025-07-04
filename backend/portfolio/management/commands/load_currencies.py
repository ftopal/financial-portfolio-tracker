from django.core.management.base import BaseCommand
from portfolio.models_currency import Currency


class Command(BaseCommand):
    help = 'Load limited currency data (USD, GBP, EUR only)'

    def handle(self, *args, **kwargs):
        # The three main currencies we'll support
        active_currencies = [
            {
                'code': 'USD',
                'name': 'US Dollar',
                'symbol': '$',
                'decimal_places': 2,
                'is_active': True
            },
            {
                'code': 'EUR',
                'name': 'Euro',
                'symbol': '€',
                'decimal_places': 2,
                'is_active': True
            },
            {
                'code': 'GBP',
                'name': 'British Pound',
                'symbol': '£',
                'decimal_places': 2,
                'is_active': True
            },
        ]

        # Other currencies to deactivate (in case they exist)
        currencies_to_deactivate = [
            'JPY', 'CHF', 'CAD', 'AUD', 'CNY', 'HKD', 'SGD', 'INR', 'BRL', 'MXN'
        ]

        # Create/update active currencies
        for currency_data in active_currencies:
            currency, created = Currency.objects.update_or_create(
                code=currency_data['code'],
                defaults=currency_data
            )
            action = "Created" if created else "Updated"
            self.stdout.write(
                f"{action} active currency: {currency_data['code']} - {currency_data['name']}"
            )

        # Deactivate other currencies
        deactivated_count = Currency.objects.filter(
            code__in=currencies_to_deactivate
        ).update(is_active=False)

        if deactivated_count > 0:
            self.stdout.write(f"Deactivated {deactivated_count} currencies")

        active_codes = [c['code'] for c in active_currencies]
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully configured currencies. Active: {", ".join(active_codes)}'
            )
        )