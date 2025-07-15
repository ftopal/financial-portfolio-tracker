# backend/portfolio/tests/test_portfolio_history_minimal.py
"""
Minimal Portfolio History Service Tests

Ultra-simplified test to just verify the service works with your actual models.
Only uses fields that definitely exist in your models.
"""

from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from ..models import Portfolio, Security, Transaction, PortfolioValueHistory, PriceHistory
from ..services.portfolio_history_service import PortfolioHistoryService


class MinimalPortfolioHistoryTestCase(TestCase):
    """
    Minimal test case to verify basic Portfolio History Service functionality
    """

    def setUp(self):
        """Set up minimal test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test portfolio (cash account auto-created by your model)
        self.portfolio = Portfolio.objects.create(
            name='Test Portfolio',
            user=self.user
        )

        # Create test security with only required fields
        self.security = Security.objects.create(
            symbol='AAPL',
            name='Apple Inc.',
            security_type='STOCK',
            current_price=Decimal('150.00')
        )

        # Create simple price history
        base_date = date.today() - timedelta(days=10)
        for i in range(11):  # 11 days of price data
            price_date = base_date + timedelta(days=i)
            PriceHistory.objects.create(
                security=self.security,
                date=timezone.make_aware(
                    timezone.datetime.combine(price_date, timezone.datetime.min.time())
                ),
                close_price=Decimal('150.00')  # Simple fixed price
            )

        # Create simple transaction with only required fields
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.security,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('145.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(date.today() - timedelta(days=5), timezone.datetime.min.time())
            )
        )

    def test_calculate_portfolio_value_basic(self):
        """Test basic portfolio value calculation"""
        target_date = date.today() - timedelta(days=2)

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, target_date
        )

        # Just verify it doesn't crash and returns basic structure
        self.assertTrue(result['success'])
        self.assertEqual(result['date'], target_date)
        self.assertIn('total_value', result)
        self.assertIn('total_cost', result)
        self.assertIn('cash_balance', result)
        self.assertIn('holdings_count', result)

    def test_save_daily_snapshot_basic(self):
        """Test basic daily snapshot creation"""
        target_date = date.today() - timedelta(days=1)

        result = PortfolioHistoryService.save_daily_snapshot(
            self.portfolio, target_date, 'test'
        )

        # Just verify it creates a snapshot without crashing
        self.assertTrue(result['success'])
        self.assertIn('created', result)
        self.assertIn('snapshot', result)

        # Verify snapshot exists in database
        snapshot_exists = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio,
            date=target_date
        ).exists()
        self.assertTrue(snapshot_exists)

    def test_backfill_basic(self):
        """Test basic backfill functionality"""
        start_date = date.today() - timedelta(days=5)
        end_date = date.today() - timedelta(days=3)

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date, force_update=False
        )

        # Just verify it completes without error
        self.assertTrue(result['success'])
        self.assertIn('successful_snapshots', result)
        self.assertIn('failed_snapshots', result)

    def test_invalid_date_range(self):
        """Test error handling for invalid date range"""
        start_date = date.today()
        end_date = date.today() - timedelta(days=5)  # End before start

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date
        )

        # Should return error for invalid range
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_empty_portfolio(self):
        """Test calculation with portfolio that has no transactions"""
        # Create empty portfolio
        empty_portfolio = Portfolio.objects.create(
            name='Empty Portfolio',
            user=self.user
        )

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            empty_portfolio, date.today()
        )

        # Should succeed with zero holdings
        self.assertTrue(result['success'])
        self.assertEqual(result['holdings_count'], 0)


# Just one simple integration test
class SimpleIntegrationTestCase(TestCase):
    """
    One simple integration test to verify end-to-end functionality
    """

    def setUp(self):
        """Set up integration test"""
        self.user = User.objects.create_user(
            username='intuser',
            email='int@example.com',
            password='testpass123'
        )

        self.portfolio = Portfolio.objects.create(
            name='Integration Portfolio',
            user=self.user
        )

    @patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date')
    def test_simple_workflow(self, mock_get_price):
        """Test simple portfolio workflow"""
        # Mock price service
        mock_get_price.return_value = Decimal('100.00')

        # Create security
        security = Security.objects.create(
            symbol='TEST',
            name='Test Stock',
            security_type='STOCK',
            current_price=Decimal('100.00')
        )

        # Create transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('5'),
            price=Decimal('100.00'),
            transaction_date=timezone.now()
        )

        # Test snapshot creation
        result = PortfolioHistoryService.save_daily_snapshot(self.portfolio)

        # Just verify it works
        self.assertTrue(result['success'])

        # Verify snapshot was created
        snapshot_exists = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio
        ).exists()
        self.assertTrue(snapshot_exists)


if __name__ == '__main__':
    import unittest

    unittest.main()