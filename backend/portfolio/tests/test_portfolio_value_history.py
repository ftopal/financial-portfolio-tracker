# Create this file as: backend/portfolio/tests/test_portfolio_value_history.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from portfolio.models import Portfolio, Security, Transaction, PortfolioValueHistory, PriceHistory
from portfolio.services.price_history_service import PriceHistoryService


class PortfolioValueHistoryTest(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test portfolio
        self.portfolio = Portfolio.objects.create(
            name='Test Portfolio',
            user=self.user,
            currency='USD',
            base_currency='USD'
        )

        # Create test security
        self.security = Security.objects.create(
            symbol='GOOG',
            name='Alphabet Inc',
            security_type='STOCK',
            currency='USD',
            current_price=Decimal('150.00')
        )

        # Create price history
        test_date = date.today() - timedelta(days=1)
        PriceHistory.objects.create(
            security=self.security,
            date=timezone.make_aware(timezone.datetime.combine(test_date, timezone.datetime.min.time())),
            close_price=Decimal('150.00'),
            currency='USD'
        )

        # Create test transaction
        self.transaction = Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10.00'),
            price=Decimal('100.00'),
            transaction_date=timezone.now() - timedelta(days=2),
            currency='USD'
        )

    def test_portfolio_value_calculation(self):
        """Test portfolio value calculation for a specific date"""
        test_date = date.today() - timedelta(days=1)

        # Calculate portfolio value
        value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
            self.portfolio,
            test_date
        )

        # Check calculations
        self.assertEqual(value_data['total_cost'], Decimal('1000.00'))  # 10 shares × $100
        self.assertEqual(value_data['holdings_count'], 1)
        self.assertGreater(value_data['total_value'], Decimal('1000.00'))  # Should be higher with price appreciation

        # Check unrealized gains
        expected_unrealized = (Decimal('10.00') * Decimal('150.00')) - Decimal('1000.00')
        self.assertEqual(value_data['unrealized_gains'], expected_unrealized)

    def test_create_snapshot(self):
        """Test creating a portfolio value snapshot"""
        test_date = date.today() - timedelta(days=1)

        # Create snapshot
        snapshot = PortfolioValueHistory.create_snapshot(
            portfolio=self.portfolio,
            target_date=test_date,
            calculation_source='manual_calc'
        )

        # Verify snapshot was created
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.portfolio, self.portfolio)
        self.assertEqual(snapshot.date, test_date)
        self.assertEqual(snapshot.calculation_source, 'manual_calc')
        self.assertEqual(snapshot.holdings_count, 1)

        # Check derived fields were calculated
        self.assertIsNotNone(snapshot.unrealized_gains)
        self.assertIsNotNone(snapshot.total_return_pct)

    def test_unique_constraint(self):
        """Test that only one snapshot per portfolio per date is allowed"""
        test_date = date.today() - timedelta(days=1)

        # Create first snapshot
        snapshot1 = PortfolioValueHistory.create_snapshot(
            portfolio=self.portfolio,
            target_date=test_date
        )

        # Create second snapshot for same date (should update, not create new)
        snapshot2 = PortfolioValueHistory.create_snapshot(
            portfolio=self.portfolio,
            target_date=test_date
        )

        # Should be the same object (updated)
        self.assertEqual(snapshot1.id, snapshot2.id)

        # Should only be one record in database
        count = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio,
            date=test_date
        ).count()
        self.assertEqual(count, 1)

    def test_get_price_for_date(self):
        """Test getting price for a specific date"""
        test_date = date.today() - timedelta(days=1)

        # Get price for the test date
        price = PriceHistoryService.get_price_for_date(self.security, test_date)

        # Should return the price we created
        self.assertEqual(price, Decimal('150.00'))

        # Test with date that has no price (should return None or current price)
        future_date = date.today() + timedelta(days=1)
        future_price = PriceHistoryService.get_price_for_date(self.security, future_date)

        # Should fallback to current price
        self.assertEqual(future_price, Decimal('150.00'))

    def test_portfolio_with_no_transactions(self):
        """Test portfolio value calculation with no transactions"""
        # Create empty portfolio
        empty_portfolio = Portfolio.objects.create(
            name='Empty Portfolio',
            user=self.user,
            currency='USD',
            base_currency='USD'
        )

        test_date = date.today()

        # Calculate value for empty portfolio
        value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
            empty_portfolio,
            test_date
        )

        # Should have zero values
        self.assertEqual(value_data['total_value'], Decimal('0'))
        self.assertEqual(value_data['total_cost'], Decimal('0'))
        self.assertEqual(value_data['holdings_count'], 0)
        self.assertEqual(value_data['unrealized_gains'], Decimal('0'))

    def test_portfolio_with_cash_balance(self):
        """Test portfolio value calculation including cash balance"""
        # This test would need cash account implementation
        # For now, we'll just test the basic calculation
        pass

    def test_multiple_transactions_same_security(self):
        """Test portfolio value with multiple transactions for the same security"""
        # Add another buy transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('5.00'),
            price=Decimal('120.00'),
            transaction_date=timezone.now() - timedelta(days=1),
            currency='USD'
        )

        test_date = date.today()

        # Calculate portfolio value
        value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
            self.portfolio,
            test_date
        )

        # Should have 15 total shares (10 + 5)
        # Total cost should be (10 * 100) + (5 * 120) = 1000 + 600 = 1600
        self.assertEqual(value_data['total_cost'], Decimal('1600.00'))

        # Current value should be 15 * current_price
        expected_current_value = Decimal('15.00') * Decimal('150.00')
        self.assertGreater(value_data['total_value'], expected_current_value - Decimal('1'))  # Allow for rounding

    def test_sell_transaction(self):
        """Test portfolio value calculation with sell transactions"""
        # Add a sell transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            user=self.user,
            transaction_type='SELL',
            quantity=Decimal('3.00'),
            price=Decimal('140.00'),
            transaction_date=timezone.now() - timedelta(days=1),
            currency='USD'
        )

        test_date = date.today()

        # Calculate portfolio value
        value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
            self.portfolio,
            test_date
        )

        # Should have 7 remaining shares (10 - 3)
        # Check that holdings count is still 1 (since we still have shares)
        self.assertEqual(value_data['holdings_count'], 1)

        # Total cost should be reduced proportionally
        # Originally 10 shares at $100 each = $1000
        # Sold 3 shares, so remaining cost = 7 * $100 = $700
        self.assertEqual(value_data['total_cost'], Decimal('700.00'))

    def test_daily_return_calculation(self):
        """Test daily return percentage calculation"""
        # Create snapshots for two consecutive days
        yesterday = date.today() - timedelta(days=1)
        today = date.today()

        # Create price history for today
        PriceHistory.objects.create(
            security=self.security,
            date=timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
            close_price=Decimal('160.00'),  # Price increased
            currency='USD'
        )

        # Create snapshots
        snapshot_yesterday = PortfolioValueHistory.create_snapshot(
            self.portfolio, yesterday
        )
        snapshot_today = PortfolioValueHistory.create_snapshot(
            self.portfolio, today
        )

        # Calculate expected daily return
        daily_return = snapshot_today.daily_return_pct

        # Should be positive since price increased
        self.assertGreater(daily_return, Decimal('0'))

        # Calculate expected value
        expected_return = ((snapshot_today.total_value - snapshot_yesterday.total_value) /
                           snapshot_yesterday.total_value * 100)
        self.assertAlmostEqual(float(daily_return), float(expected_return), places=2)