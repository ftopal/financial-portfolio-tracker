# backend/portfolio/tests/test_portfolio_history_service_fixed.py
"""
Fixed Portfolio History Service Tests

Simplified test suite that works with your existing model structure.
This addresses the cash account creation and field name issues.
"""

from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from ..models import Portfolio, Security, Transaction, PortfolioValueHistory, PriceHistory
from ..services.portfolio_history_service import PortfolioHistoryService


class PortfolioHistoryServiceBasicTestCase(TestCase):
    """
    Basic test cases for Portfolio History Service functionality
    """

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test portfolio (cash account is auto-created)
        self.portfolio = Portfolio.objects.create(
            name='Test Portfolio',
            user=self.user,
            description='Test portfolio for history service'
        )

        # Create test security
        self.security = Security.objects.create(
            symbol='AAPL',
            name='Apple Inc.',
            security_type='STOCK',
            exchange='NASDAQ',
            currency='USD',
            current_price=Decimal('150.00')
        )

        # Create price history for the security
        self.create_price_history()

        # Create test transactions
        self.create_test_transactions()

    def create_price_history(self):
        """Create price history for testing"""
        base_date = date.today() - timedelta(days=30)
        base_price = Decimal('150.00')

        for i in range(31):  # 31 days of price data
            price_date = base_date + timedelta(days=i)
            # Simulate some price movement
            price_variation = Decimal(str(i * 0.5 - 5))  # -5 to +10 variation
            price = max(base_price + price_variation, Decimal('100.00'))

            PriceHistory.objects.create(
                security=self.security,
                date=timezone.make_aware(
                    timezone.datetime.combine(price_date, timezone.datetime.min.time())
                ),
                open_price=price,
                high_price=price + Decimal('2.00'),
                low_price=price - Decimal('1.50'),
                close_price=price,
                volume=1000000 + i * 10000
            )

    def create_test_transactions(self):
        """Create test transactions"""
        base_date = date.today() - timedelta(days=20)

        # Buy transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('145.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date, timezone.datetime.min.time())
            ),
            description='Test buy transaction'
        )

        # Another buy transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            transaction_type='BUY',
            quantity=Decimal('5'),
            price=Decimal('148.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date + timedelta(days=5), timezone.datetime.min.time())
            ),
            description='Test buy transaction 2'
        )

        # Sell transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            transaction_type='SELL',
            quantity=Decimal('3'),
            price=Decimal('152.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date + timedelta(days=10), timezone.datetime.min.time())
            ),
            description='Test sell transaction'
        )

    def test_calculate_portfolio_value_on_date(self):
        """Test portfolio value calculation for a specific date"""
        target_date = date.today() - timedelta(days=5)

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, target_date
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['date'], target_date)
        self.assertIsInstance(result['total_value'], Decimal)
        self.assertIsInstance(result['total_cost'], Decimal)
        self.assertIsInstance(result['cash_balance'], Decimal)
        self.assertGreaterEqual(result['holdings_count'], 0)

    def test_save_daily_snapshot(self):
        """Test saving daily portfolio snapshot"""
        target_date = date.today() - timedelta(days=3)

        result = PortfolioHistoryService.save_daily_snapshot(
            self.portfolio, target_date, 'test'
        )

        self.assertTrue(result['success'])
        self.assertTrue(result['created'])
        self.assertIsInstance(result['snapshot'], PortfolioValueHistory)

        # Verify snapshot was saved
        snapshot = PortfolioValueHistory.objects.get(
            portfolio=self.portfolio, date=target_date
        )
        self.assertEqual(snapshot.calculation_source, 'test')
        self.assertGreater(snapshot.total_value, 0)

    def test_save_daily_snapshot_update_existing(self):
        """Test updating existing daily snapshot"""
        target_date = date.today() - timedelta(days=3)

        # Create initial snapshot
        result1 = PortfolioHistoryService.save_daily_snapshot(
            self.portfolio, target_date, 'test'
        )
        self.assertTrue(result1['created'])

        # Update the same snapshot
        result2 = PortfolioHistoryService.save_daily_snapshot(
            self.portfolio, target_date, 'updated_test'
        )
        self.assertFalse(result2['created'])  # Should be updated, not created

        # Verify only one snapshot exists
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio, date=target_date
        )
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.first().calculation_source, 'updated_test')

    def test_calculate_daily_snapshots_all_portfolios(self):
        """Test calculating daily snapshots for all portfolios"""
        target_date = date.today() - timedelta(days=2)

        # Create another portfolio (cash account auto-created)
        portfolio2 = Portfolio.objects.create(
            name='Test Portfolio 2',
            user=self.user,
            description='Second test portfolio'
        )

        result = PortfolioHistoryService.calculate_daily_snapshots(target_date)

        self.assertTrue(result['success'])
        self.assertEqual(result['total_portfolios'], 2)
        self.assertEqual(result['successful_snapshots'], 2)
        self.assertEqual(result['failed_snapshots'], 0)

        # Verify snapshots were created
        snapshots = PortfolioValueHistory.objects.filter(date=target_date)
        self.assertEqual(snapshots.count(), 2)

    def test_backfill_portfolio_history(self):
        """Test backfilling portfolio history"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=5)

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date, force_update=False
        )

        self.assertTrue(result['success'])
        self.assertGreater(result['successful_snapshots'], 0)
        self.assertEqual(result['failed_snapshots'], 0)

        # Verify snapshots were created for business days
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio,
            date__gte=start_date,
            date__lte=end_date
        )
        self.assertGreater(snapshots.count(), 0)

    def test_backfill_with_existing_data(self):
        """Test backfilling when some data already exists"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=5)

        # Create some existing snapshots
        mid_date = date.today() - timedelta(days=7)
        existing_snapshot = PortfolioValueHistory.objects.create(
            portfolio=self.portfolio,
            date=mid_date,
            total_value=Decimal('1000.00'),
            total_cost=Decimal('900.00'),
            cash_balance=Decimal('100.00'),
            holdings_count=1,
            unrealized_gains=Decimal('100.00'),
            total_return_pct=Decimal('11.11'),
            calculation_source='existing'
        )

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date, force_update=False
        )

        self.assertTrue(result['success'])
        self.assertGreater(result['skipped_snapshots'], 0)

        # Verify existing snapshot wasn't changed
        existing_snapshot.refresh_from_db()
        self.assertEqual(existing_snapshot.calculation_source, 'existing')

    def test_get_portfolio_performance(self):
        """Test getting portfolio performance data"""
        start_date = date.today() - timedelta(days=15)
        end_date = date.today() - timedelta(days=5)

        # Create some test snapshots
        self.create_test_snapshots(start_date, end_date)

        result = PortfolioHistoryService.get_portfolio_performance(
            self.portfolio, start_date, end_date
        )

        self.assertTrue(result['success'])
        self.assertIn('chart_data', result)
        self.assertIn('performance_summary', result)
        self.assertIn('daily_returns', result)

        # Verify chart data structure
        chart_data = result['chart_data']
        self.assertGreater(len(chart_data), 0)

        for data_point in chart_data:
            self.assertIn('date', data_point)
            self.assertIn('total_value', data_point)
            self.assertIn('total_cost', data_point)
            self.assertIn('unrealized_gains', data_point)

    def test_get_portfolio_performance_no_data(self):
        """Test getting performance data when no snapshots exist"""
        start_date = date.today() - timedelta(days=15)
        end_date = date.today() - timedelta(days=5)

        result = PortfolioHistoryService.get_portfolio_performance(
            self.portfolio, start_date, end_date
        )

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_get_portfolio_gaps(self):
        """Test detecting gaps in portfolio history"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=5)

        # Create some snapshots with gaps
        snapshot_dates = [
            start_date,
            start_date + timedelta(days=2),
            start_date + timedelta(days=5),  # Gap between day 2 and 5
        ]

        for snapshot_date in snapshot_dates:
            if snapshot_date.weekday() < 5:  # Only business days
                PortfolioValueHistory.objects.create(
                    portfolio=self.portfolio,
                    date=snapshot_date,
                    total_value=Decimal('1000.00'),
                    total_cost=Decimal('900.00'),
                    cash_balance=Decimal('100.00'),
                    holdings_count=1,
                    unrealized_gains=Decimal('100.00'),
                    total_return_pct=Decimal('11.11'),
                    calculation_source='test'
                )

        result = PortfolioHistoryService.get_portfolio_gaps(
            self.portfolio, start_date, end_date
        )

        self.assertTrue(result['success'])
        self.assertGreater(result['total_missing'], 0)
        self.assertLess(result['coverage_percentage'], 100)
        self.assertIsInstance(result['missing_dates'], list)

    def test_bulk_portfolio_processing(self):
        """Test bulk portfolio processing for daily snapshots"""
        # Create additional portfolios (cash accounts auto-created)
        portfolios = [self.portfolio]
        for i in range(2):
            portfolio = Portfolio.objects.create(
                name=f'Bulk Test Portfolio {i + 1}',
                user=self.user,
                description=f'Bulk test portfolio {i + 1}'
            )
            portfolios.append(portfolio)

        target_date = date.today() - timedelta(days=1)

        result = PortfolioHistoryService.bulk_portfolio_processing(
            portfolios, 'daily_snapshot', target_date=target_date
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['total_portfolios'], 3)
        self.assertEqual(result['successful_operations'], 3)
        self.assertEqual(result['failed_operations'], 0)

        # Verify snapshots were created
        for portfolio in portfolios:
            snapshot = PortfolioValueHistory.objects.filter(
                portfolio=portfolio, date=target_date
            ).first()
            self.assertIsNotNone(snapshot)

    def test_portfolio_value_with_empty_portfolio(self):
        """Test portfolio value calculation with empty portfolio"""
        # Create empty portfolio
        empty_portfolio = Portfolio.objects.create(
            name='Empty Portfolio',
            user=self.user,
            description='Empty test portfolio'
        )

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            empty_portfolio, date.today()
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['holdings_count'], 0)
        # Should have some value from cash account (auto-created with 0 balance)
        self.assertGreaterEqual(result['total_value'], Decimal('0.00'))

    def test_invalid_date_range(self):
        """Test backfill with invalid date ranges"""
        # Start date after end date
        start_date = date.today()
        end_date = date.today() - timedelta(days=10)

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date
        )

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def create_test_snapshots(self, start_date, end_date):
        """Helper method to create test snapshots"""
        current_date = start_date
        base_value = Decimal('1000.00')

        while current_date <= end_date:
            if current_date.weekday() < 5:  # Business days only
                # Simulate some value changes
                days_elapsed = (current_date - start_date).days
                value_change = Decimal(str(days_elapsed * 10))  # $10 increase per day
                total_value = base_value + value_change

                PortfolioValueHistory.objects.create(
                    portfolio=self.portfolio,
                    date=current_date,
                    total_value=total_value,
                    total_cost=Decimal('900.00'),
                    cash_balance=Decimal('100.00'),
                    holdings_count=1,
                    unrealized_gains=total_value - Decimal('900.00'),
                    total_return_pct=(total_value - Decimal('900.00')) / Decimal('900.00') * 100,
                    calculation_source='test'
                )

            current_date += timedelta(days=1)


class PortfolioHistoryServiceIntegrationTestCase(TestCase):
    """
    Integration tests for real workflow scenarios
    """

    def setUp(self):
        """Set up integration test data"""
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpass123'
        )

        # Create portfolio (cash account auto-created)
        self.portfolio = Portfolio.objects.create(
            name='Integration Test Portfolio',
            user=self.user,
            description='Portfolio for integration testing'
        )

    @patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date')
    def test_full_portfolio_lifecycle(self, mock_get_price):
        """Test complete portfolio lifecycle with history tracking"""
        # Mock price service to return consistent prices
        mock_get_price.return_value = Decimal('150.00')

        # Create security
        security = Security.objects.create(
            symbol='MSFT',
            name='Microsoft Corporation',
            security_type='STOCK',
            exchange='NASDAQ',
            currency='USD',
            current_price=Decimal('150.00')
        )

        # Day 1: Initial purchase
        day1 = date.today() - timedelta(days=10)
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='BUY',
            quantity=Decimal('50'),
            price=Decimal('145.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(day1, timezone.datetime.min.time())
            ),
            description='Initial purchase'
        )

        # Calculate day 1 snapshot
        result1 = PortfolioHistoryService.save_daily_snapshot(self.portfolio, day1)
        self.assertTrue(result1['success'])

        # Day 5: Additional purchase
        day5 = date.today() - timedelta(days=6)
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='BUY',
            quantity=Decimal('25'),
            price=Decimal('148.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(day5, timezone.datetime.min.time())
            ),
            description='Additional purchase'
        )

        # Calculate day 5 snapshot
        result5 = PortfolioHistoryService.save_daily_snapshot(self.portfolio, day5)
        self.assertTrue(result5['success'])

        # Verify portfolio evolution
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio
        ).order_by('date')

        self.assertEqual(snapshots.count(), 2)

        # Verify holdings count changes
        self.assertEqual(snapshots[0].holdings_count, 1)  # Day 1: Has holdings
        self.assertEqual(snapshots[1].holdings_count, 1)  # Day 5: Still has holdings


if __name__ == '__main__':
    import unittest

    unittest.main()