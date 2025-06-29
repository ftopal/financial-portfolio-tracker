from django.core.management.base import BaseCommand
from portfolio.models import Currency

class Command(BaseCommand):
    help = 'Load initial currency data'

    def handle(self, *args, **kwargs):
        currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'decimal_places': 2},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'decimal_places': 2},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'decimal_places': 2},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'decimal_places': 0},
            {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF', 'decimal_places': 2},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$', 'decimal_places': 2},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$', 'decimal_places': 2},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥', 'decimal_places': 2},
            {'code': 'HKD', 'name': 'Hong Kong Dollar', 'symbol': 'HK$', 'decimal_places': 2},
            {'code': 'SGD', 'name': 'Singapore Dollar', 'symbol': 'S$', 'decimal_places': 2},
        ]

        for currency_data in currencies:
            Currency.objects.update_or_create(
                code=currency_data['code'],
                defaults=currency_data
            )
            self.stdout.write(f"Created/Updated currency: {currency_data['code']}")

        self.stdout.write(self.style.SUCCESS('Successfully loaded currencies'))