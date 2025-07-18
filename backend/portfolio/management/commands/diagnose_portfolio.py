# File: backend/portfolio/management/commands/diagnose_portfolio.py

from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date, datetime
from portfolio.models import Portfolio, Transaction, PriceHistory, PortfolioValueHistory
from portfolio.services.portfolio_history_service import PortfolioHistoryService


class Command(BaseCommand):
    help = 'Diagnose portfolio calculation issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio-name',
            type=str,
            help='Name of the portfolio to diagnose',
            default='Test 3'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix the identified issues'
        )

    def handle(self, *args, **options):
        portfolio_name = options['portfolio_name']
        fix_issues = options['fix']

        try:
            portfolio = Portfolio.objects.get(name=portfolio_name)
            self.stdout.write(f"🔍 Diagnosing portfolio: {portfolio.name}")

            # 1. Check transactions
            self.check_transactions(portfolio)

            # 2. Check price history
            self.check_price_history(portfolio)

            # 3. Check portfolio value calculations
            self.check_portfolio_values(portfolio)

            # 4. Check portfolio value history
            self.check_value_history(portfolio)

            if fix_issues:
                self.fix_portfolio_issues(portfolio)

        except Portfolio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Portfolio '{portfolio_name}' not found")
            )

    def check_transactions(self, portfolio):
        self.stdout.write("\n📊 TRANSACTION ANALYSIS")
        self.stdout.write("=" * 50)

        transactions = portfolio.transactions.all().order_by('date')

        for transaction in transactions:
            self.stdout.write(
                f"📅 {transaction.date} | {transaction.type.upper()} | "
                f"{transaction.security.symbol if transaction.security else 'CASH'} | "
                f"Qty: {transaction.quantity} | Price: {transaction.price} | "
                f"Amount: {transaction.amount}"
            )

        # Calculate expected balances
        cash_balance = Decimal('0')
        holdings = {}

        for transaction in transactions:
            if transaction.type == 'deposit':
                cash_balance += transaction.amount
            elif transaction.type == 'withdrawal':
                cash_balance -= transaction.amount
            elif transaction.type == 'buy':
                cash_balance -= (transaction.quantity * transaction.price)
                if transaction.security.symbol not in holdings:
                    holdings[transaction.security.symbol] = Decimal('0')
                holdings[transaction.security.symbol] += transaction.quantity
            elif transaction.type == 'sell':
                cash_balance += (transaction.quantity * transaction.price)
                if transaction.security.symbol in holdings:
                    holdings[transaction.security.symbol] -= transaction.quantity

        self.stdout.write(f"\n💰 Expected Cash Balance: {cash_balance} EUR")
        self.stdout.write("📈 Expected Holdings:")
        for symbol, quantity in holdings.items():
            self.stdout.write(f"   {symbol}: {quantity} shares")

    def check_price_history(self, portfolio):
        self.stdout.write("\n💹 PRICE HISTORY ANALYSIS")
        self.stdout.write("=" * 50)

        # Get all securities in portfolio
        securities = set()
        for transaction in portfolio.transactions.all():
            if transaction.security:
                securities.add(transaction.security)

        for security in securities:
            latest_price = PriceHistory.objects.filter(
                security=security
            ).order_by('-date').first()

            if latest_price:
                self.stdout.write(
                    f"📊 {security.symbol} | Latest: {latest_price.close} | "
                    f"Date: {latest_price.date}"
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {security.symbol} | No price history found")
                )

    def check_portfolio_values(self, portfolio):
        self.stdout.write("\n📈 PORTFOLIO VALUE CALCULATION")
        self.stdout.write("=" * 50)

        # Test key dates
        test_dates = [
            date(2025, 1, 1),  # Initial deposit
            date(2025, 1, 31),  # Purchase date
            date.today()  # Current date
        ]

        for test_date in test_dates:
            self.stdout.write(f"\n📅 Testing date: {test_date}")

            # Manual calculation
            cash_balance = portfolio.get_cash_balance_on_date(test_date)

            # Get holdings on this date
            transactions = portfolio.transactions.filter(
                date__lte=test_date
            ).order_by('date')

            holdings = {}
            for transaction in transactions:
                if transaction.type == 'buy' and transaction.security:
                    if transaction.security.symbol not in holdings:
                        holdings[transaction.security.symbol] = Decimal('0')
                    holdings[transaction.security.symbol] += transaction.quantity

            holdings_value = Decimal('0')
            for symbol, quantity in holdings.items():
                security = portfolio.transactions.filter(
                    security__symbol=symbol
                ).first().security

                current_price = PortfolioHistoryService.get_security_price_on_date(
                    security, test_date
                )

                if current_price:
                    value = quantity * current_price
                    holdings_value += value
                    self.stdout.write(
                        f"   {symbol}: {quantity} × {current_price} = {value} EUR"
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"   {symbol}: No price found for {test_date}")
                    )

            total_value = cash_balance + holdings_value

            self.stdout.write(f"💰 Cash Balance: {cash_balance} EUR")
            self.stdout.write(f"📊 Holdings Value: {holdings_value} EUR")
            self.stdout.write(f"💎 Total Value: {total_value} EUR")

            # Compare with service calculation
            service_result = PortfolioHistoryService.calculate_portfolio_value_on_date(
                portfolio, test_date
            )

            if service_result['success']:
                self.stdout.write(f"🔧 Service Total: {service_result['total_value']} EUR")
                if abs(total_value - service_result['total_value']) > Decimal('0.01'):
                    self.stdout.write(
                        self.style.ERROR("❌ Manual and service calculations don't match!")
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Manual and service calculations match")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Service calculation failed: {service_result.get('error')}")
                )

    def check_value_history(self, portfolio):
        self.stdout.write("\n📊 VALUE HISTORY ANALYSIS")
        self.stdout.write("=" * 50)

        history_records = PortfolioValueHistory.objects.filter(
            portfolio=portfolio
        ).order_by('date')

        if history_records.exists():
            self.stdout.write(f"📈 Found {history_records.count()} history records")

            for record in history_records:
                self.stdout.write(
                    f"📅 {record.date} | Total: {record.total_value} | "
                    f"Cash: {record.cash_balance} | Holdings: {record.holdings_count}"
                )
        else:
            self.stdout.write(
                self.style.WARNING("⚠️  No portfolio value history found")
            )

    def fix_portfolio_issues(self, portfolio):
        self.stdout.write("\n🔧 FIXING PORTFOLIO ISSUES")
        self.stdout.write("=" * 50)

        # 1. Recalculate all portfolio value history
        self.stdout.write("🔄 Recalculating portfolio value history...")

        # Delete existing incorrect records
        PortfolioValueHistory.objects.filter(portfolio=portfolio).delete()

        # Backfill from the beginning
        start_date = date(2025, 1, 1)
        end_date = date.today()

        result = PortfolioHistoryService.backfill_portfolio_history(
            portfolio, start_date, end_date, force_update=True
        )

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Successfully created {result['successful_snapshots']} snapshots"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Backfill failed: {result.get('error')}")
            )

        # 2. Verify the fix
        self.stdout.write("\n🔍 Verifying fix...")
        self.check_portfolio_values(portfolio)