from django.core.management.base import BaseCommand
from portfolio.services.currency_service import CurrencyService
from portfolio.models_currency import Currency, ExchangeRate
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = 'Test currency conversion functionality'

    def add_arguments(self, parser):
        parser.add_argument('amount', type=float, help='Amount to convert')
        parser.add_argument('from_currency', type=str, help='From currency code')
        parser.add_argument('to_currency', type=str, help='To currency code')

    def handle(self, *args, **kwargs):
        amount = Decimal(str(kwargs['amount']))
        from_currency = kwargs['from_currency'].upper()
        to_currency = kwargs['to_currency'].upper()

        self.stdout.write(f"\nTesting conversion: {amount} {from_currency} -> {to_currency}")

        # Check currencies exist and are active
        from_curr = Currency.objects.filter(code=from_currency).first()
        to_curr = Currency.objects.filter(code=to_currency).first()

        if not from_curr:
            self.stdout.write(self.style.ERROR(f"Currency {from_currency} not found"))
            return

        if not to_curr:
            self.stdout.write(self.style.ERROR(f"Currency {to_currency} not found"))
            return

        self.stdout.write(f"{from_currency} - Active: {from_curr.is_active}")
        self.stdout.write(f"{to_currency} - Active: {to_curr.is_active}")

        if not from_curr.is_active:
            self.stdout.write(self.style.WARNING(f"{from_currency} is not active"))

        if not to_curr.is_active:
            self.stdout.write(self.style.WARNING(f"{to_currency} is not active"))

        # Check exchange rates
        today = timezone.now().date()

        self.stdout.write(f"\nLooking for exchange rates on or before {today}:")

        # Direct rate
        direct_rate = ExchangeRate.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            date__lte=today
        ).order_by('-date').first()

        if direct_rate:
            self.stdout.write(
                f"✓ Direct rate found: {from_currency}/{to_currency} = {direct_rate.rate} (date: {direct_rate.date})")
        else:
            self.stdout.write(f"✗ No direct rate found for {from_currency}/{to_currency}")

        # Inverse rate
        inverse_rate = ExchangeRate.objects.filter(
            from_currency=to_currency,
            to_currency=from_currency,
            date__lte=today
        ).order_by('-date').first()

        if inverse_rate:
            calculated_rate = Decimal('1') / inverse_rate.rate
            self.stdout.write(f"✓ Inverse rate found: {to_currency}/{from_currency} = {inverse_rate.rate}")
            self.stdout.write(
                f"  Calculated {from_currency}/{to_currency} = {calculated_rate} (date: {inverse_rate.date})")
        else:
            self.stdout.write(f"✗ No inverse rate found for {to_currency}/{from_currency}")

        # Try to get rate using CurrencyService
        try:
            rate = CurrencyService.get_exchange_rate(from_currency, to_currency, today)
            if rate:
                self.stdout.write(f"\n✓ CurrencyService found rate: {rate}")

                # Perform conversion
                converted_amount = CurrencyService.convert_amount(amount, from_currency, to_currency, today)
                self.stdout.write(f"✓ Conversion result: {amount} {from_currency} = {converted_amount} {to_currency}")
            else:
                self.stdout.write(f"\n✗ CurrencyService could not find rate")
        except Exception as e:
            self.stdout.write(f"\n✗ CurrencyService error: {e}")

        # Show recent exchange rates for debugging
        self.stdout.write(f"\nRecent exchange rates involving {from_currency} and {to_currency}:")
        recent_rates = ExchangeRate.objects.filter(
            models.Q(from_currency=from_currency) | models.Q(to_currency=from_currency) |
            models.Q(from_currency=to_currency) | models.Q(to_currency=to_currency)
        ).order_by('-date')[:10]

        for rate in recent_rates:
            self.stdout.write(f"  {rate.from_currency}/{rate.to_currency}: {rate.rate} ({rate.date})")

        if not recent_rates:
            self.stdout.write("  No exchange rates found")


# Import Q for the command
from django.db import models