# backend/portfolio/management/commands/diagnose_currency.py

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import date

from portfolio.models import Portfolio, Security, Transaction
from portfolio.services.currency_service import CurrencyService
from portfolio.services.portfolio_history_service import PortfolioHistoryService


class Command(BaseCommand):
    help = 'Diagnose currency conversion issues in portfolio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio-name',
            type=str,
            default='Test 4',
            help='Name of the portfolio to diagnose'
        )

    def handle(self, *args, **options):
        portfolio_name = options['portfolio_name']

        try:
            portfolio = Portfolio.objects.get(name=portfolio_name)
        except Portfolio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Portfolio '{portfolio_name}' not found")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"🔍 Currency Diagnosis for Portfolio: {portfolio.name}")
        )
        self.stdout.write("=" * 80)

        # Show basic portfolio info
        self.show_portfolio_info(portfolio)

        # Analyze transactions
        self.analyze_transactions(portfolio)

        # Test currency conversions
        self.test_currency_conversions()

        # Compare calculation methods
        self.compare_calculation_methods(portfolio)

    def show_portfolio_info(self, portfolio):
        """Show basic portfolio information"""
        self.stdout.write(f"\n📊 Portfolio Information:")
        self.stdout.write(f"   Name: {portfolio.name}")
        self.stdout.write(f"   Currency: {portfolio.base_currency}")
        self.stdout.write(f"   Base Currency: {getattr(portfolio, 'base_currency', 'N/A')}")

        # Show cash account info
        if hasattr(portfolio, 'cash_account'):
            self.stdout.write(f"   Cash Account Currency: {portfolio.cash_account.currency}")
            self.stdout.write(f"   Cash Balance: {portfolio.cash_account.balance}")
        else:
            self.stdout.write(f"   Cash Account: Not found")

    def analyze_transactions(self, portfolio):
        """Analyze transaction currency details"""
        self.stdout.write(f"\n📈 Transaction Analysis:")

        transactions = portfolio.transactions.all().order_by('transaction_date')

        for tx in transactions:
            self.stdout.write(f"\n   Transaction ID: {tx.id}")
            self.stdout.write(f"   Date: {tx.transaction_date.date()}")
            self.stdout.write(f"   Type: {tx.transaction_type}")
            self.stdout.write(f"   Security: {tx.security.symbol} ({tx.security.currency})")
            self.stdout.write(f"   Quantity: {tx.quantity}")
            self.stdout.write(f"   Price: {tx.price} {tx.security.currency}")
            self.stdout.write(f"   Raw Cost: {tx.quantity * tx.price} {tx.security.currency}")

            # Show stored exchange rate and base amount
            self.stdout.write(f"   Stored Exchange Rate: {tx.exchange_rate}")
            self.stdout.write(f"   Stored Base Amount: {tx.base_amount}")

            # Calculate what the conversion should be
            if tx.security.currency == 'GBp' and portfolio.base_currency == 'USD':
                # GBp -> GBP -> USD conversion
                raw_cost_gbp = tx.quantity * tx.price

                # Step 1: GBp to GBP
                cost_in_gbp = raw_cost_gbp * Decimal('0.01')
                self.stdout.write(f"   Step 1 (GBp→GBP): {raw_cost_gbp} GBp = £{cost_in_gbp}")

                # Step 2: GBP to USD (if needed)
                try:
                    gbp_to_usd_rate = CurrencyService.get_exchange_rate('GBP', 'USD', tx.transaction_date.date())
                    if gbp_to_usd_rate:
                        cost_in_usd = cost_in_gbp * gbp_to_usd_rate
                        self.stdout.write(f"   Step 2 (GBP→USD): £{cost_in_gbp} × {gbp_to_usd_rate} = ${cost_in_usd}")
                    else:
                        self.stdout.write(f"   Step 2: No GBP→USD rate found")
                except Exception as e:
                    self.stdout.write(f"   Step 2 Error: {e}")

    def test_currency_conversions(self):
        """Test currency conversion functions"""
        self.stdout.write(f"\n🧪 Currency Conversion Tests:")

        # Test GBp to GBP
        test_amount = Decimal('98000')  # 98,000 GBp

        try:
            converted = CurrencyService.convert_amount_with_normalization(
                test_amount, 'GBp', 'GBP', date.today()
            )
            self.stdout.write(f"   GBp→GBP: {test_amount} GBp = £{converted}")
        except Exception as e:
            self.stdout.write(f"   GBp→GBP Error: {e}")

        # Test GBp to USD
        try:
            converted = CurrencyService.convert_amount_with_normalization(
                test_amount, 'GBp', 'USD', date.today()
            )
            self.stdout.write(f"   GBp→USD: {test_amount} GBp = ${converted}")
        except Exception as e:
            self.stdout.write(f"   GBp→USD Error: {e}")

        # Test current price conversion
        current_price = Decimal('1059.50')  # Current NG.L price in GBp
        quantity = Decimal('100')

        raw_value = quantity * current_price
        self.stdout.write(f"   Raw Value: {quantity} × {current_price} GBp = {raw_value} GBp")

        try:
            converted = CurrencyService.convert_amount_with_normalization(
                raw_value, 'GBp', 'USD', date.today()
            )
            self.stdout.write(f"   Converted Value (GBp→USD): ${converted}")
        except Exception as e:
            self.stdout.write(f"   Conversion Error: {e}")

    def compare_calculation_methods(self, portfolio):
        """Compare different calculation methods"""
        self.stdout.write(f"\n🔄 Calculation Method Comparison:")

        # Method 1: Portfolio.get_total_value()
        try:
            method1_value = portfolio.get_total_value()
            self.stdout.write(f"   Method 1 (Portfolio.get_total_value): ${method1_value}")
        except Exception as e:
            self.stdout.write(f"   Method 1 Error: {e}")

        # Method 2: Portfolio History Service
        try:
            result = PortfolioHistoryService.calculate_portfolio_value_on_date(
                portfolio, date.today()
            )
            if result['success']:
                self.stdout.write(f"   Method 2 (History Service): ${result['total_value']}")
                self.stdout.write(f"     Holdings Value: ${result['holdings_value']}")
                self.stdout.write(f"     Cash Balance: ${result['cash_balance']}")
                self.stdout.write(f"     Total Cost: ${result['total_cost']}")
            else:
                self.stdout.write(f"   Method 2 Error: {result.get('error')}")
        except Exception as e:
            self.stdout.write(f"   Method 2 Exception: {e}")

        # Method 3: Manual calculation
        self.manual_calculation(portfolio)

    def manual_calculation(self, portfolio):
        """Perform manual calculation for verification"""
        self.stdout.write(f"\n🧮 Manual Calculation:")

        holdings = portfolio.get_holdings()

        for holding in holdings.values():
            security = holding['security']
            quantity = holding['quantity']
            current_price = security.current_price

            self.stdout.write(f"   Security: {security.symbol}")
            self.stdout.write(f"   Quantity: {quantity}")
            self.stdout.write(f"   Current Price: {current_price} {security.currency}")

            # Raw value
            raw_value = quantity * current_price
            self.stdout.write(f"   Raw Value: {raw_value} {security.currency}")

            # Converted value
            try:
                if security.currency == 'GBp':
                    # First convert to GBP
                    value_gbp = raw_value * Decimal('0.01')
                    self.stdout.write(f"   Value in GBP: £{value_gbp}")

                    # Then convert to portfolio currency if needed
                    if portfolio.base_currency != 'GBP':
                        rate = CurrencyService.get_exchange_rate('GBP', portfolio.base_currency, date.today())
                        if rate:
                            final_value = value_gbp * rate
                            self.stdout.write(f"   Final Value: {final_value} {portfolio.base_currency}")
                        else:
                            self.stdout.write(f"   No exchange rate found for GBP→{portfolio.base_currency}")
            except Exception as e:
                self.stdout.write(f"   Conversion Error: {e}")

        # Add cash
        if hasattr(portfolio, 'cash_account'):
            cash = portfolio.cash_account.balance
            self.stdout.write(f"   Cash: {cash} {portfolio.base_currency}")

        self.stdout.write(f"\n💡 Expected Results:")
        self.stdout.write(f"   For NG.L: 100 × 1059.50 GBp = 105,950 GBp = £1,059.50")
        self.stdout.write(f"   If portfolio is USD: £1,059.50 × GBP/USD rate")
        self.stdout.write(f"   If portfolio is GBP: £1,059.50 + £20 cash = £1,079.50")
        self.stdout.write(f"   Current portfolio currency: {portfolio.base_currency}")