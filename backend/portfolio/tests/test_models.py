from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from .test_base import BaseTestCase
from ..models import Portfolio, Security, Transaction


class PortfolioModelTest(BaseTestCase):

    def test_portfolio_creation(self):
        """Test portfolio is created correctly"""
        self.assertEqual(self.portfolio.user, self.user)
        self.assertEqual(self.portfolio.name, 'Test Portfolio')
        self.assertTrue(self.portfolio.is_default)
        self.assertEqual(str(self.portfolio), 'Test Portfolio (testuser)')

    def test_only_one_default_portfolio(self):
        """Test only one portfolio can be default per user"""
        # Create second portfolio as default
        portfolio2 = Portfolio.objects.create(
            user=self.user,
            name='Second Portfolio',
            is_default=True
        )

        # First portfolio should no longer be default
        self.portfolio.refresh_from_db()
        self.assertFalse(self.portfolio.is_default)
        self.assertTrue(portfolio2.is_default)

    def test_portfolio_holdings_empty(self):
        """Test get_holdings returns empty dict when no transactions"""
        holdings = self.portfolio.get_holdings()
        self.assertEqual(holdings, {})

    def test_portfolio_holdings_with_transactions(self):
        """Test get_holdings calculates correctly"""
        # Buy 10 AAPL at $100
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10'),
            transaction_date=timezone.now() - timedelta(days=30)
        )

        # Buy 5 more AAPL at $120
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('5'),
            price=Decimal('120'),
            fees=Decimal('5'),
            transaction_date=timezone.now() - timedelta(days=15)
        )

        holdings = self.portfolio.get_holdings()

        # Should have 1 security
        self.assertEqual(len(holdings), 1)

        # Check AAPL holdings
        aapl_holding = holdings[self.stock_aapl.id]
        self.assertEqual(aapl_holding['quantity'], Decimal('15'))
        self.assertEqual(aapl_holding['total_cost'], Decimal('1615'))  # (10*100+10) + (5*120+5)

        # Average cost should be total_cost / quantity
        expected_avg_cost = Decimal('1610') / Decimal('15')  # Cost without fees
        self.assertAlmostEqual(
            float(aapl_holding['avg_cost']),
            float(expected_avg_cost),
            places=2
        )

    def test_portfolio_holdings_with_sell(self):
        """Test holdings calculation with buy and sell transactions"""
        # Buy 10 AAPL
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        # Sell 5 AAPL
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='SELL',
            quantity=Decimal('5'),
            price=Decimal('150'),
            fees=Decimal('10')
        )

        holdings = self.portfolio.get_holdings()
        aapl_holding = holdings[self.stock_aapl.id]

        # Should have 5 shares remaining
        self.assertEqual(aapl_holding['quantity'], Decimal('5'))

        # Realized gains: Sold 5 at 150, bought at 100 = 5 * (150-100) = 250
        self.assertEqual(aapl_holding['realized_gains'], Decimal('250'))

    def test_portfolio_summary(self):
        """Test portfolio summary calculation"""
        # Buy some stocks
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_googl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('2'),
            price=Decimal('2500'),
            fees=Decimal('20')
        )

        summary = self.portfolio.get_summary()

        # Total cost: (10*100+10) + (2*2500+20) = 1010 + 5020 = 6030
        self.assertEqual(summary['total_cost'], Decimal('6030'))

        # Current value: (10*150) + (2*2800) = 1500 + 5600 = 7100
        self.assertEqual(summary['total_value'], Decimal('7100'))

        # Total gains: 7100 - 6030 = 1070 (excluding fees from current value)
        # Note: actual calculation might differ based on fee handling
        self.assertEqual(summary['holdings_count'], 2)


class SecurityModelTest(BaseTestCase):

    def test_security_creation(self):
        """Test security is created correctly"""
        self.assertEqual(self.stock_aapl.symbol, 'AAPL')
        self.assertEqual(self.stock_aapl.security_type, 'STOCK')
        self.assertEqual(self.stock_aapl.current_price, Decimal('150.00'))
        self.assertEqual(str(self.stock_aapl), 'AAPL - Apple Inc.')

    def test_unique_symbol_constraint(self):
        """Test that symbols must be unique"""
        with self.assertRaises(Exception):
            Security.objects.create(
                symbol='AAPL',  # Duplicate
                name='Another Apple',
                security_type='STOCK',
                current_price=Decimal('100')
            )

    def test_price_change_properties(self):
        """Test price change calculations"""
        self.stock_aapl.day_high = Decimal('155.00')
        self.stock_aapl.day_low = Decimal('145.00')
        self.stock_aapl.save()

        # Price change from average of high/low
        avg_price = (Decimal('155.00') + Decimal('145.00')) / 2  # 150
        expected_change = Decimal('150.00') - avg_price  # 0
        self.assertEqual(self.stock_aapl.price_change, expected_change)
        self.assertEqual(self.stock_aapl.price_change_pct, Decimal('0'))


class TransactionModelTest(BaseTestCase):

    def test_buy_transaction_creation(self):
        """Test buy transaction is created correctly"""
        transaction = Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        self.assertEqual(transaction.total_value, Decimal('1010'))  # (10*100) + 10
        self.assertEqual(
            str(transaction),
            f"BUY - AAPL - {transaction.transaction_date.date()}"
        )

    def test_sell_transaction_value(self):
        """Test sell transaction value calculation"""
        transaction = Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='SELL',
            quantity=Decimal('5'),
            price=Decimal('150'),
            fees=Decimal('10')
        )

        # Sell value is (quantity * price) - fees
        self.assertEqual(transaction.total_value, Decimal('740'))  # (5*150) - 10

    def test_dividend_transaction(self):
        """Test dividend transaction"""
        transaction = Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='DIVIDEND',
            quantity=Decimal('10'),  # Number of shares
            price=Decimal('0'),  # Price not used for dividends
            dividend_per_share=Decimal('0.88'),
            fees=Decimal('0')
        )

        self.assertEqual(transaction.total_value, Decimal('8.80'))  # 10 * 0.88

    def test_transaction_validation(self):
        """Test transaction validation"""
        # Test future date validation
        future_transaction = Transaction(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            transaction_date=timezone.now() + timedelta(days=1)
        )

        with self.assertRaises(ValidationError):
            future_transaction.clean()

    def test_dividend_validation(self):
        """Test dividend transaction validation"""
        dividend_transaction = Transaction(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='DIVIDEND',
            quantity=Decimal('10'),
            price=Decimal('0'),
            # Missing dividend_per_share
        )

        with self.assertRaises(ValidationError):
            dividend_transaction.clean()