# backend/portfolio/management/commands/test_currency_fix.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from portfolio.models import Portfolio, Security, Transaction, PriceHistory
from portfolio.services.portfolio_history_service import PortfolioHistoryService


class Command(BaseCommand):
    help = 'Test the currency conversion fix for UK stocks in portfolio history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio-name',
            type=str,
            default='Test 4',
            help='Name of the portfolio to test'
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate portfolio history with the fix'
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
            self.style.SUCCESS(f"🔍 Testing Currency Fix for Portfolio: {portfolio.name}")
        )
        self.stdout.write("=" * 80)

        # Show portfolio details
        self.show_portfolio_details(portfolio)

        # Test current portfolio value calculation
        self.test_current_calculation(portfolio)

        if recalculate:
            # Recalculate portfolio history with the fix
            self.recalculate_portfolio_history(portfolio)

        # Show the fix results
        self.show_fix_results(portfolio)

    def show_portfolio_details(self, portfolio):
        """Show current portfolio details"""
        self.stdout.write(f"\n📊 Portfolio Details:")
        self.stdout.write(f"   Currency: {portfolio.currency}")

        # Show holdings
        holdings = portfolio.get_holdings()
        self.stdout.write(f"   Holdings ({len(holdings)}):")

        for holding in holdings.values():
            security = holding['security']
            self.stdout.write(f"   - {security.symbol} ({security.currency})")
            self.stdout.write(f"     Quantity: {holding['quantity']}")
            self.stdout.write(f"     Current Price: {security.current_price} {security.currency}")
            self.stdout.write(f"     Current Value (raw): {holding['current_value']} {security.currency}")

            if 'current_value_base_currency' in holding:
                self.stdout.write(
                    f"     Current Value (converted): {holding['current_value_base_currency']} {portfolio.currency}")

        # Show transactions
        transactions = portfolio.transactions.all().order_by('transaction_date')
        self.stdout.write(f"\n📈 Recent Transactions ({transactions.count()}):")

        for tx in transactions[:5]:  # Show last 5
            self.stdout.write(f"   {tx.transaction_date.date()} | {tx.transaction_type} | "
                              f"{tx.security.symbol} | {tx.quantity} @ {tx.price} {tx.security.currency}")

    def test_current_calculation(self, portfolio):
        """Test current portfolio value calculation"""
        self.stdout.write(f"\n🧪 Testing Current Portfolio Value Calculation:")

        # Test using the FIXED service method
        today = date.today()
        result = PortfolioHistoryService.calculate_portfolio_value_on_date(portfolio, today)

        if result['success']:
            self.stdout.write(f"✅ Portfolio History Service (FIXED):")
            self.stdout.write(f"   Total Value: £{result['total_value']:,.2f}")
            self.stdout.write(f"   Holdings Value: £{result['holdings_value']:,.2f}")
            self.stdout.write(f"   Cash Balance: £{result['cash_balance']:,.2f}")
            self.stdout.write(f"   Holdings Count: {result['holdings_count']}")

            # Show individual holdings with conversion
            if 'holdings' in result:
                self.stdout.write(f"   Individual Holdings:")
                for holding in result['holdings']:
                    self.stdout.write(f"   - {holding['security']}: {holding['quantity']} × "
                                      f"{holding['current_price']} = £{holding['current_value']:,.2f}")
        else:
            self.stdout.write(f"❌ Error: {result.get('error')}")

        # Compare with original Portfolio.get_total_value() method
        try:
            original_total = portfolio.get_total_value()
            self.stdout.write(f"\n📊 Original Portfolio.get_total_value(): £{original_total:,.2f}")

            if result['success']:
                difference = abs(float(result['total_value']) - float(original_total))
                if difference < 1.0:  # Within £1
                    self.stdout.write(f"✅ Values match (difference: £{difference:.2f})")
                else:
                    self.stdout.write(f"⚠️  Values differ (difference: £{difference:.2f})")
        except Exception as e:
            self.stdout.write(f"❌ Error getting original total value: {e}")

    def recalculate_portfolio_history(self, portfolio):
        """Recalculate portfolio history with the currency fix"""
        self.stdout.write(f"\n🔄 Recalculating Portfolio History with Currency Fix:")

        # Backfill last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        self.stdout.write(f"   Backfilling from {start_date} to {end_date}...")

        result = PortfolioHistoryService.backfill_portfolio_history(
            portfolio, start_date, end_date
        )

        if result['success']:
            self.stdout.write(f"✅ Backfill completed:")
            self.stdout.write(f"   Created: {result['created_count']} snapshots")
            self.stdout.write(f"   Updated: {result['updated_count']} snapshots")
            if result['errors']:
                self.stdout.write(f"   Errors: {len(result['errors'])}")
                for error in result['errors'][:3]:  # Show first 3 errors
                    self.stdout.write(f"     - {error}")
        else:
            self.stdout.write(f"❌ Backfill failed: {result.get('error')}")

    def show_fix_results(self, portfolio):
        """Show the results after applying the currency fix"""
        self.stdout.write(f"\n📈 Historical Performance After Fix:")

        # Get performance data for different periods
        periods = [
            ('1 Week', 7),
            ('1 Month', 30),
            ('3 Months', 90)
        ]

        today = date.today()

        for period_name, days in periods:
            start_date = today - timedelta(days=days)

            performance = PortfolioHistoryService.get_portfolio_performance(
                portfolio, start_date, today
            )

            if performance['success']:
                summary = performance['performance_summary']
                chart_data = performance['chart_data']

                self.stdout.write(f"\n📊 {period_name} Performance:")
                self.stdout.write(f"   Start Value: £{summary['start_value']:,.2f}")
                self.stdout.write(f"   End Value: £{summary['end_value']:,.2f}")
                self.stdout.write(f"   Total Return: {summary['total_return_pct']:,.2f}%")
                self.stdout.write(f"   Volatility: {summary['volatility']:,.2f}%")
                self.stdout.write(f"   Data Points: {len(chart_data)}")

                # Check if values look reasonable (not in the hundreds of thousands)
                if summary['end_value'] < 50000:  # Reasonable for a test portfolio
                    self.stdout.write(f"   ✅ Values look reasonable")
                else:
                    self.stdout.write(f"   ⚠️  Values seem too high - may still have currency issue")
            else:
                self.stdout.write(f"\n❌ {period_name} Performance: {performance.get('error')}")

        # Show recent chart data points
        self.show_recent_chart_data(portfolio)

    def show_recent_chart_data(self, portfolio):
        """Show recent chart data to verify currency conversion"""
        self.stdout.write(f"\n📊 Recent Chart Data (Last 10 Days):")

        end_date = date.today()
        start_date = end_date - timedelta(days=10)

        performance = PortfolioHistoryService.get_portfolio_performance(
            portfolio, start_date, end_date
        )

        if performance['success']:
            chart_data = performance['chart_data']

            self.stdout.write(f"{'Date':<12} {'Total Value':<15} {'Holdings Value':<15} {'Cash':<10}")
            self.stdout.write("-" * 55)

            for data_point in chart_data[-10:]:  # Last 10 days
                date_str = data_point['date']
                total_val = data_point['total_value']
                holdings_val = total_val - data_point['cash_balance']
                cash_bal = data_point['cash_balance']

                self.stdout.write(f"{date_str:<12} £{total_val:<14,.2f} £{holdings_val:<14,.2f} £{cash_bal:<9,.2f}")

                # Flag any suspicious values
                if total_val > 50000:
                    self.stdout.write(f"    ⚠️  Value seems too high for test portfolio")
        else:
            self.stdout.write(f"❌ Could not get chart data: {performance.get('error')}")

        # Summary and recommendations
        self.stdout.write(f"\n🎯 Fix Summary:")
        self.stdout.write(f"   The currency conversion fix ensures that:")
        self.stdout.write(f"   1. UK stocks in GBp are converted to GBP (÷100)")
        self.stdout.write(f"   2. Portfolio values are consistent across all calculations")
        self.stdout.write(f"   3. Historical graphs show correct values")

        self.stdout.write(f"\n💡 Expected Results for Test 4 Portfolio:")
        self.stdout.write(f"   - NG.L: 100 shares at 980 GBp = £9.80 purchase price")
        self.stdout.write(f"   - Current price ~1060 GBp = £10.60 per share")
        self.stdout.write(f"   - Total value should be ~£1,060 (not £106,000)")

        # Final validation
        latest_performance = PortfolioHistoryService.get_portfolio_performance(
            portfolio, date.today() - timedelta(days=1), date.today()
        )

        if latest_performance['success'] and latest_performance['chart_data']:
            latest_value = latest_performance['chart_data'][-1]['total_value']
            if 1000 <= latest_value <= 2000:  # Reasonable range for test portfolio
                self.stdout.write(f"\n✅ Currency fix appears successful!")
                self.stdout.write(f"   Latest portfolio value: £{latest_value:,.2f} (reasonable)")
            else:
                self.stdout.write(f"\n❌ Currency fix may need more work")
                self.stdout.write(f"   Latest portfolio value: £{latest_value:,.2f} (seems wrong)")

        self.stdout.write(f"\n" + "=" * 80)
        self.stdout.write(f"Currency fix testing completed for {portfolio.name}")