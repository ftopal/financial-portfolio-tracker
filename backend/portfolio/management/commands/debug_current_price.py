# backend/portfolio/management/commands/debug_current_price.py

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import date, datetime
from django.utils import timezone

from portfolio.models import Portfolio, Security, PortfolioValueHistory, PriceHistory
from portfolio.services.portfolio_history_service import PortfolioHistoryService


class Command(BaseCommand):
    help = 'Debug current price currency conversion issue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio-name',
            type=str,
            default='Test 4',
            help='Name of the portfolio to debug'
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Force recalculate today\'s snapshot'
        )

    def handle(self, *args, **options):
        portfolio_name = options['portfolio_name']
        recalculate = options['recalculate']

        try:
            portfolio = Portfolio.objects.get(name=portfolio_name)
        except Portfolio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Portfolio '{portfolio_name}' not found")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"🔍 Debugging Current Price Issue: {portfolio.name}")
        )
        self.stdout.write("=" * 80)

        # Check current price sources
        self.check_current_prices(portfolio)

        # Check today's snapshot
        self.check_todays_snapshot(portfolio)

        # Check price history vs current price
        self.check_price_sources(portfolio)

        if recalculate:
            self.force_recalculate_today(portfolio)

    def check_current_prices(self, portfolio):
        """Check current prices and currency conversion"""
        self.stdout.write(f"\n💰 Current Price Analysis:")

        holdings = portfolio.get_holdings()

        for holding in holdings.values():
            security = holding['security']

            self.stdout.write(f"\n   Security: {security.symbol}")
            self.stdout.write(f"   Security Currency: {security.currency}")
            self.stdout.write(f"   Portfolio Currency: {portfolio.base_currency}")

            # Current price from security
            current_price = security.current_price
            self.stdout.write(f"   Current Price (security.current_price): {current_price} {security.currency}")

            # Get price using history service method
            today = date.today()
            history_price = PortfolioHistoryService.get_security_price_on_date(security, today)
            self.stdout.write(f"   History Service Price: {history_price} {security.currency}")

            # Test currency conversion
            from portfolio.services.currency_service import CurrencyService

            quantity = holding['quantity']
            raw_value = quantity * current_price
            self.stdout.write(f"   Raw Value: {quantity} × {current_price} = {raw_value} {security.currency}")

            try:
                converted_value = CurrencyService.convert_amount_with_normalization(
                    raw_value,
                    security.currency,
                    portfolio.base_currency,
                    today
                )
                self.stdout.write(f"   Converted Value: {converted_value} {portfolio.base_currency}")
                self.stdout.write(f"   Conversion Factor: {converted_value / raw_value:.6f}")
            except Exception as e:
                self.stdout.write(f"   ❌ Conversion Error: {e}")

    def check_todays_snapshot(self, portfolio):
        """Check today's portfolio snapshot"""
        self.stdout.write(f"\n📊 Today's Snapshot Analysis:")

        today = date.today()

        try:
            snapshot = PortfolioValueHistory.objects.get(portfolio=portfolio, date=today)
            self.stdout.write(f"   Found snapshot for {today}:")
            self.stdout.write(f"   Total Value: {snapshot.total_value} {portfolio.base_currency}")
            self.stdout.write(f"   Total Cost: {snapshot.total_cost} {portfolio.base_currency}")
            self.stdout.write(f"   Cash Balance: {snapshot.cash_balance} {portfolio.base_currency}")
            self.stdout.write(f"   Created: {snapshot.created_at}")
            self.stdout.write(f"   Source: {snapshot.calculation_source}")

            # Check if values look correct
            if snapshot.total_value > 50000:
                self.stdout.write(f"   ⚠️  Total value seems too high - possible currency issue")
            else:
                self.stdout.write(f"   ✅ Total value looks reasonable")

        except PortfolioValueHistory.DoesNotExist:
            self.stdout.write(f"   ❌ No snapshot found for {today}")

    def check_price_sources(self, portfolio):
        """Check different price sources"""
        self.stdout.write(f"\n📈 Price Sources Comparison:")

        holdings = portfolio.get_holdings()
        today = date.today()

        for holding in holdings.values():
            security = holding['security']

            self.stdout.write(f"\n   {security.symbol} Price Sources:")

            # 1. Current price from security
            current_price = security.current_price
            self.stdout.write(f"   1. security.current_price: {current_price}")

            # 2. Latest price history
            try:
                latest_price_history = PriceHistory.objects.filter(
                    security=security
                ).order_by('-date').first()

                if latest_price_history:
                    self.stdout.write(
                        f"   2. Latest PriceHistory: {latest_price_history.close_price} on {latest_price_history.date}")
                else:
                    self.stdout.write(f"   2. No PriceHistory found")
            except Exception as e:
                self.stdout.write(f"   2. PriceHistory error: {e}")

            # 3. History service method
            history_price = PortfolioHistoryService.get_security_price_on_date(security, today)
            self.stdout.write(f"   3. History service: {history_price}")

            # Check for discrepancies
            if current_price != history_price:
                self.stdout.write(f"   ⚠️  Price discrepancy detected!")

    def force_recalculate_today(self, portfolio):
        """Force recalculate today's snapshot"""
        self.stdout.write(f"\n🔄 Force Recalculating Today's Snapshot:")

        today = date.today()

        # Delete existing snapshot for today
        deleted_count = PortfolioValueHistory.objects.filter(
            portfolio=portfolio,
            date=today
        ).delete()[0]

        if deleted_count > 0:
            self.stdout.write(f"   🗑️  Deleted {deleted_count} existing snapshot(s)")

        # Create new snapshot
        result = PortfolioHistoryService.save_daily_snapshot(
            portfolio,
            today,
            'debug_recalc'
        )

        if result['success']:
            self.stdout.write(f"   ✅ Created new snapshot")
            calc_result = result['calculation_result']
            self.stdout.write(f"   New Total Value: {calc_result['total_value']} {portfolio.base_currency}")
            self.stdout.write(f"   Holdings Value: {calc_result['holdings_value']} {portfolio.base_currency}")
            self.stdout.write(f"   Cash Balance: {calc_result['cash_balance']} {portfolio.base_currency}")

            # Check if values are correct now
            if calc_result['total_value'] > 50000:
                self.stdout.write(f"   ❌ Still showing high values - currency conversion not working")
                self.debug_conversion_issue(portfolio, calc_result)
            else:
                self.stdout.write(f"   ✅ Values now look correct!")
        else:
            self.stdout.write(f"   ❌ Failed to create snapshot: {result.get('error')}")

    def debug_conversion_issue(self, portfolio, calc_result):
        """Debug why currency conversion isn't working"""
        self.stdout.write(f"\n🔧 Deep Conversion Debug:")

        holdings = portfolio.get_holdings()

        for holding in holdings.values():
            security = holding['security']
            quantity = holding['quantity']

            self.stdout.write(f"\n   Debugging {security.symbol}:")
            self.stdout.write(f"   Security currency: '{security.currency}'")
            self.stdout.write(f"   Portfolio currency: '{portfolio.base_currency}'")

            # Test the exact same logic as portfolio history service
            today = date.today()
            current_price = PortfolioHistoryService.get_security_price_on_date(security, today)

            self.stdout.write(f"   Current price: {current_price}")

            # Test currency conversion step by step
            from portfolio.services.currency_service import CurrencyService

            security_currency = security.currency or 'USD'
            portfolio_currency = portfolio.base_currency or 'GBP'

            self.stdout.write(f"   Security currency (normalized): '{security_currency}'")
            self.stdout.write(f"   Portfolio currency (normalized): '{portfolio_currency}'")

            raw_current_value = quantity * current_price
            self.stdout.write(f"   Raw current value: {raw_current_value}")

            if security_currency != portfolio_currency:
                self.stdout.write(f"   Different currencies - applying conversion")
                try:
                    converted_value = CurrencyService.convert_amount_with_normalization(
                        raw_current_value,
                        security_currency,
                        portfolio_currency,
                        today
                    )
                    self.stdout.write(f"   Converted value: {converted_value}")
                except Exception as e:
                    self.stdout.write(f"   Conversion failed: {e}")
            else:
                self.stdout.write(f"   Same currencies - applying normalization")
                try:
                    normalized_value = CurrencyService.convert_amount_with_normalization(
                        raw_current_value,
                        security_currency,
                        portfolio_currency,
                        today
                    )
                    self.stdout.write(f"   Normalized value: {normalized_value}")
                except Exception as e:
                    self.stdout.write(f"   Normalization failed: {e}")