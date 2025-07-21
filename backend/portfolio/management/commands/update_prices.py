from django.core.management.base import BaseCommand
from portfolio.models import Security
import yfinance as yf
from decimal import Decimal
from django.utils import timezone


class Command(BaseCommand):
    help = 'Update all stock prices from Yahoo Finance'

    def handle(self, *args, **options):
        stocks = Security.objects.all()
        updated = 0
        failed = 0

        for stock in stocks:
            try:
                self.stdout.write(f'Updating {stock.symbol}...')
                ticker = yf.Ticker(stock.symbol)
                info = ticker.info

                current_price = info.get('currentPrice') or info.get('regularMarketPrice')

                if current_price:
                    stock.current_price = Decimal(str(current_price))
                    stock.last_updated = timezone.now()
                    stock.save()
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ {stock.symbol}: ${current_price}'))
                else:
                    failed += 1
                    self.stdout.write(self.style.WARNING(f'✗ {stock.symbol}: No price data'))

            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'✗ {stock.symbol}: {str(e)}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nComplete! Updated: {updated}, Failed: {failed}'
            )
        )