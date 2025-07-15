# backend/portfolio/tests/test_portfolio_history_service.py
"""
Comprehensive Tests for Portfolio History Service - Phase 3

This test suite covers all functionality of the Portfolio History Service,
including daily calculations, backfill operations, performance metrics,
and edge cases.
"""

from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import json

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from ..models import (
    Portfolio, Security, Transaction, PortfolioValueHistory,
    PriceHistory, PortfolioCashAccount
)
from ..services.portfolio_history_service import PortfolioHistoryService
from ..services.price_history_service import PriceHistoryService


class PortfolioHistoryServiceTestCase(TestCase):
    """
    Test cases for Portfolio History Service functionality
    """

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
            description='Test portfolio for history service'
        )

        # Create cash account for portfolio
        PortfolioCashAccount.objects.create(
            portfolio=self.portfolio,
            balance=Decimal('1000.00'),
            currency='USD'
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
        self.buy_transaction = Transaction.objects.create(
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
        self.buy_transaction2 = Transaction.objects.create(
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
        self.sell_transaction = Transaction.objects.create(
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

        # Verify calculations make sense
        self.assertGreater(result['total_value'], 0)
        self.assertNotEqual(result['total_cost'], 0)

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

        # Create another portfolio
        portfolio2 = Portfolio.objects.create(
            name='Test Portfolio 2',
            user=self.user,
            description='Second test portfolio'
        )

        # Create cash account for second portfolio
        PortfolioCashAccount.objects.create(
            portfolio=portfolio2,
            balance=Decimal('2000.00'),
            currency='USD'
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

        # Verify chronological order
        ordered_snapshots = list(snapshots.order_by('date'))
        for i in range(1, len(ordered_snapshots)):
            self.assertGreater(ordered_snapshots[i].date, ordered_snapshots[i - 1].date)

    def test_backfill_portfolio_history_with_existing_data(self):
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

    def test_backfill_portfolio_history_force_update(self):
        """Test backfilling with force update"""
        start_date = date.today() - timedelta(days=8)
        end_date = date.today() - timedelta(days=6)

        # Create existing snapshot
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
            self.portfolio, start_date, end_date, force_update=True
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['skipped_snapshots'], 0)  # No skips with force update

        # Verify existing snapshot was updated
        existing_snapshot.refresh_from_db()
        self.assertEqual(existing_snapshot.calculation_source, 'backfill')

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

        # Verify performance summary
        summary = result['performance_summary']
        self.assertIn('total_return_pct', summary)
        self.assertIn('start_value', summary)
        self.assertIn('end_value', summary)
        self.assertIn('volatility', summary)
        self.assertIn('best_day', summary)
        self.assertIn('worst_day', summary)

    def test_get_portfolio_performance_no_data(self):
        """Test getting performance data when no snapshots exist"""
        start_date = date.today() - timedelta(days=15)
        end_date = date.today() - timedelta(days=5)

        result = PortfolioHistoryService.get_portfolio_performance(
            self.portfolio, start_date, end_date
        )

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_trigger_portfolio_recalculation(self):
        """Test triggering portfolio recalculation"""
        transaction_date = date.today() - timedelta(days=5)

        result = PortfolioHistoryService.trigger_portfolio_recalculation(
            self.portfolio, transaction_date
        )

        self.assertTrue(result['success'])
        self.assertGreater(result.get('successful_snapshots', 0), 0)

    def test_trigger_portfolio_recalculation_full(self):
        """Test triggering full portfolio recalculation"""
        result = PortfolioHistoryService.trigger_portfolio_recalculation(
            self.portfolio, None
        )

        self.assertTrue(result['success'])
        self.assertGreater(result.get('successful_snapshots', 0), 0)

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

    def test_bulk_portfolio_processing_daily_snapshot(self):
        """Test bulk portfolio processing for daily snapshots"""
        # Create additional portfolios
        portfolios = [self.portfolio]
        for i in range(2):
            portfolio = Portfolio.objects.create(
                name=f'Bulk Test Portfolio {i + 1}',
                user=self.user,
                description=f'Bulk test portfolio {i + 1}'
            )
            # Create cash account for each portfolio
            PortfolioCashAccount.objects.create(
                portfolio=portfolio,
                balance=Decimal('1000.00'),
                currency='USD'
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

    def test_bulk_portfolio_processing_performance(self):
        """Test bulk portfolio processing for performance data"""
        portfolios = [self.portfolio]
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=5)

        # Create test snapshots for the portfolio
        self.create_test_snapshots(start_date, end_date)

        result = PortfolioHistoryService.bulk_portfolio_processing(
            portfolios, 'performance',
            start_date=start_date, end_date=end_date
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['successful_operations'], 1)

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

    def test_portfolio_value_calculation_edge_cases(self):
        """Test portfolio value calculation edge cases"""
        # Test with empty portfolio
        empty_portfolio = Portfolio.objects.create(
            name='Empty Portfolio',
            user=self.user,
            description='Empty test portfolio'
        )

        # Create cash account with zero balance
        PortfolioCashAccount.objects.create(
            portfolio=empty_portfolio,
            balance=Decimal('0.00'),
            currency='USD'
        )

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            empty_portfolio, date.today()
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['total_value'], Decimal('0.00'))
        self.assertEqual(result['holdings_count'], 0)

    def test_portfolio_value_with_multiple_securities(self):
        """Test portfolio value calculation with multiple securities"""
        # Create another security
        security2 = Security.objects.create(
            symbol='GOOGL',
            name='Alphabet Inc.',
            security_type='STOCK',
            exchange='NASDAQ',
            currency='USD',
            current_price=Decimal('2500.00')
        )

        # Create price history for second security
        base_date = date.today() - timedelta(days=30)
        for i in range(31):
            price_date = base_date + timedelta(days=i)
            PriceHistory.objects.create(
                security=security2,
                date=timezone.make_aware(
                    timezone.datetime.combine(price_date, timezone.datetime.min.time())
                ),
                open_price=Decimal('2500.00'),
                high_price=Decimal('2520.00'),
                low_price=Decimal('2480.00'),
                close_price=Decimal('2500.00'),
                volume=500000
            )

        # Create transaction for second security
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security2,
            transaction_type='BUY',
            quantity=Decimal('2'),
            price=Decimal('2500.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(date.today() - timedelta(days=15), timezone.datetime.min.time())
            ),
            description='Test buy GOOGL'
        )

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, date.today()
        )

        self.assertTrue(result['success'])
        self.assertGreater(result['holdings_count'], 1)
        self.assertGreater(result['total_value'], Decimal('5000.00'))  # Should include both securities

    def test_portfolio_value_calculation_date_without_price_data(self):
        """Test calculation when price data is missing for a date"""
        # Try to calculate for a date far in the future
        future_date = date.today() + timedelta(days=365)

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, future_date
        )

        # Should still succeed by using latest available price
        self.assertTrue(result['success'])
        self.assertGreater(result['total_value'], 0)

    def test_performance_metrics_calculation(self):
        """Test detailed performance metrics calculation"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=1)

        # Create snapshots with varying returns
        snapshots_data = [
            (start_date, Decimal('1000.00')),
            (start_date + timedelta(days=1), Decimal('1050.00')),  # +5%
            (start_date + timedelta(days=2), Decimal('1020.00')),  # -2.86%
            (start_date + timedelta(days=3), Decimal('1100.00')),  # +7.84%
            (start_date + timedelta(days=4), Decimal('1080.00')),  # -1.82%
        ]

        for snapshot_date, value in snapshots_data:
            if snapshot_date.weekday() < 5:  # Business days only
                PortfolioValueHistory.objects.create(
                    portfolio=self.portfolio,
                    date=snapshot_date,
                    total_value=value,
                    total_cost=Decimal('900.00'),
                    cash_balance=Decimal('100.00'),
                    holdings_count=1,
                    unrealized_gains=value - Decimal('900.00'),
                    total_return_pct=(value - Decimal('900.00')) / Decimal('900.00') * 100,
                    calculation_source='test'
                )

        result = PortfolioHistoryService.get_portfolio_performance(
            self.portfolio, start_date, end_date
        )

        self.assertTrue(result['success'])

        summary = result['performance_summary']
        daily_returns = result['daily_returns']

        # Verify we have daily returns
        self.assertGreater(len(daily_returns), 0)

        # Verify volatility calculation
        self.assertGreater(summary['volatility'], 0)

        # Verify best and worst day identification
        self.assertGreater(summary['best_day'], 0)  # Should be positive
        self.assertLess(summary['worst_day'], 0)  # Should be negative


class PortfolioHistoryServiceIntegrationTestCase(TestCase):
    """
    Integration tests for Portfolio History Service with real workflow scenarios
    """

    def setUp(self):
        """Set up integration test data"""
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpass123'
        )

        self.portfolio = Portfolio.objects.create(
            name='Integration Test Portfolio',
            user=self.user,
            description='Portfolio for integration testing'
        )

        # Create cash account for integration test portfolio
        PortfolioCashAccount.objects.create(
            portfolio=self.portfolio,
            balance=Decimal('10000.00'),
            currency='USD'
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

        # Day 8: Partial sale
        day8 = date.today() - timedelta(days=3)
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='SELL',
            quantity=Decimal('20'),
            price=Decimal('152.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(day8, timezone.datetime.min.time())
            ),
            description='Partial sale'
        )

        # Calculate day 8 snapshot
        result8 = PortfolioHistoryService.save_daily_snapshot(self.portfolio, day8)
        self.assertTrue(result8['success'])

        # Verify portfolio evolution
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio
        ).order_by('date')

        self.assertEqual(snapshots.count(), 3)

        # Verify holdings count changes
        self.assertEqual(snapshots[0].holdings_count, 1)  # Day 1: Has holdings
        self.assertEqual(snapshots[1].holdings_count, 1)  # Day 5: Still has holdings
        self.assertEqual(snapshots[2].holdings_count, 1)  # Day 8: Still has holdings (partial sale)

        # Verify total value increases over time (due to mock price increase)
        self.assertLess(snapshots[0].total_value, snapshots[2].total_value)

    def test_backfill_after_bulk_transaction_import(self):
        """Test backfill operation after importing multiple transactions"""
        # Simulate bulk import of historical transactions
        securities = []
        for i in range(3):
            security = Security.objects.create(
                symbol=f'STOCK{i}',
                name=f'Test Stock {i}',
                security_type='STOCK',
                exchange='NYSE',
                currency='USD',
                current_price=Decimal('100.00')
            )
            securities.append(security)

        # Create transactions across multiple dates
        base_date = date.today() - timedelta(days=30)
        for i in range(15):  # 15 days of transactions
            transaction_date = base_date + timedelta(days=i * 2)  # Every other day

            for j, security in enumerate(securities):
                Transaction.objects.create(
                    portfolio=self.portfolio,
                    security=security,
                    transaction_type='BUY',
                    quantity=Decimal('10'),
                    price=Decimal(f'{100 + j * 10}.00'),
                    transaction_date=timezone.make_aware(
                        timezone.datetime.combine(transaction_date, timezone.datetime.min.time())
                    ),
                    description=f'Bulk import transaction {i}-{j}'
                )

        # Mock price service for backfill
        with patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date') as mock_price:
            mock_price.return_value = Decimal('150.00')

            # Perform backfill
            result = PortfolioHistoryService.backfill_portfolio_history(
                self.portfolio, base_date, date.today()
            )

            self.assertTrue(result['success'])
            self.assertGreater(result['successful_snapshots'], 0)

        # Verify snapshots were created
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio
        )
        self.assertGreater(snapshots.count(), 10)  # Should have multiple snapshots

    def test_performance_analysis_workflow(self):
        """Test complete performance analysis workflow"""
        # Create historical snapshots with realistic data
        start_date = date.today() - timedelta(days=60)

        for i in range(60):
            snapshot_date = start_date + timedelta(days=i)

            if snapshot_date.weekday() < 5:  # Business days only
                # Simulate portfolio growth with some volatility
                base_value = Decimal('10000.00')
                growth_factor = Decimal('1.0') + (Decimal(str(i)) / Decimal('365'))  # Annual growth
                volatility = Decimal(str((i % 10 - 5) * 0.02))  # ±10% volatility

                total_value = base_value * growth_factor * (Decimal('1.0') + volatility)

                PortfolioValueHistory.objects.create(
                    portfolio=self.portfolio,
                    date=snapshot_date,
                    total_value=total_value,
                    total_cost=Decimal('9500.00'),
                    cash_balance=Decimal('500.00'),
                    holdings_count=5,
                    unrealized_gains=total_value - Decimal('9500.00'),
                    total_return_pct=(total_value - Decimal('9500.00')) / Decimal('9500.00') * 100,
                    calculation_source='test'
                )

        # Test different time period analyses
        periods = [
            (date.today() - timedelta(days=7), 'weekly'),
            (date.today() - timedelta(days=30), 'monthly'),
            (date.today() - timedelta(days=60), 'full_period'),
        ]

        for period_start, period_name in periods:
            result = PortfolioHistoryService.get_portfolio_performance(
                self.portfolio, period_start, date.today()
            )

            self.assertTrue(result['success'], f"Failed for {period_name} period")
            self.assertIn('performance_summary', result)
            self.assertIn('chart_data', result)

            # Verify we have data for the period
            chart_data = result['chart_data']
            self.assertGreater(len(chart_data), 0, f"No chart data for {period_name}")

            # Verify performance metrics
            summary = result['performance_summary']
            self.assertIn('total_return_pct', summary)
            self.assertIn('volatility', summary)
            self.assertIsInstance(summary['start_value'], float)
            self.assertIsInstance(summary['end_value'], float)


class PortfolioHistoryServiceErrorHandlingTestCase(TestCase):
    """
    Test error handling and edge cases for Portfolio History Service
    """

    def setUp(self):
        """Set up error handling test data"""
        self.user = User.objects.create_user(
            username='erroruser',
            email='error@example.com',
            password='testpass123'
        )

        self.portfolio = Portfolio.objects.create(
            name='Error Test Portfolio',
            user=self.user,
            description='Portfolio for error testing'
        )

        # Create cash account for error test portfolio
        PortfolioCashAccount.objects.create(
            portfolio=self.portfolio,
            balance=Decimal('1000.00'),
            currency='USD'
        )

    def test_calculate_portfolio_value_with_invalid_date(self):
        """Test portfolio value calculation with invalid date scenarios"""
        # Test with very old date (before any transactions)
        old_date = date(2000, 1, 1)

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, old_date
        )

        self.assertTrue(result['success'])
        # Should equal the cash account balance, not the portfolio's non-existent cash_balance
        expected_cash = self.portfolio.cash_account.balance
        self.assertEqual(result['total_value'], expected_cash)
        self.assertEqual(result['holdings_count'], 0)

    def test_portfolio_value_calculation_with_missing_price_data(self):
        """Test calculation when security has no price data"""
        # Create security without price history
        security = Security.objects.create(
            symbol='NOPRICE',
            name='No Price Security',
            security_type='STOCK',
            exchange='NYSE',
            currency='USD',
            current_price=Decimal('100.00')
        )

        # Create transaction for security without prices
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(date.today() - timedelta(days=5), timezone.datetime.min.time())
            ),
            description='Test transaction without price data'
        )

        result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            self.portfolio, date.today()
        )

        # Should still succeed, but may have limitations
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['holdings_count'], 0)

    def test_save_daily_snapshot_with_calculation_error(self):
        """Test snapshot saving when portfolio calculation fails"""
        # Mock the calculation to fail
        with patch.object(PortfolioHistoryService, 'calculate_portfolio_value_on_date') as mock_calc:
            mock_calc.return_value = {
                'success': False,
                'error': 'Test calculation error'
            }

            result = PortfolioHistoryService.save_daily_snapshot(self.portfolio)

            self.assertFalse(result['success'])
            self.assertIn('error', result)

    def test_backfill_with_invalid_date_range(self):
        """Test backfill with invalid date ranges"""
        # Start date after end date
        start_date = date.today()
        end_date = date.today() - timedelta(days=10)

        result = PortfolioHistoryService.backfill_portfolio_history(
            self.portfolio, start_date, end_date
        )

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_get_portfolio_performance_with_insufficient_data(self):
        """Test performance calculation with insufficient data"""
        # Create only one snapshot
        PortfolioValueHistory.objects.create(
            portfolio=self.portfolio,
            date=date.today() - timedelta(days=1),
            total_value=Decimal('1000.00'),
            total_cost=Decimal('900.00'),
            cash_balance=Decimal('100.00'),
            holdings_count=1,
            unrealized_gains=Decimal('100.00'),
            total_return_pct=Decimal('11.11'),
            calculation_source='test'
        )

        result = PortfolioHistoryService.get_portfolio_performance(
            self.portfolio,
            date.today() - timedelta(days=10),
            date.today()
        )

        # Should succeed with limited data
        self.assertTrue(result['success'])
        self.assertEqual(len(result['chart_data']), 1)
        self.assertEqual(len(result['daily_returns']), 0)  # No daily returns with single point

    def test_bulk_processing_with_mixed_success_failure(self):
        """Test bulk processing when some operations fail"""
        # Create portfolios, some with valid data, some that will fail
        portfolios = [self.portfolio]

        # Create a portfolio that will cause errors (no transactions, etc.)
        error_portfolio = Portfolio.objects.create(
            name='Error Portfolio',
            user=self.user,
            description='Portfolio designed to cause errors'
        )

        # Create cash account with zero balance
        PortfolioCashAccount.objects.create(
            portfolio=error_portfolio,
            balance=Decimal('0.00'),
            currency='USD'
        )
        portfolios.append(error_portfolio)

        # Mock one portfolio calculation to fail
        original_method = PortfolioHistoryService.save_daily_snapshot

        def mock_save_snapshot(portfolio, target_date=None, calculation_source='bulk_task'):
            if portfolio.name == 'Error Portfolio':
                return {
                    'success': False,
                    'error': 'Simulated error for testing'
                }
            return original_method(portfolio, target_date, calculation_source)

        with patch.object(PortfolioHistoryService, 'save_daily_snapshot', side_effect=mock_save_snapshot):
            result = PortfolioHistoryService.bulk_portfolio_processing(
                portfolios, 'daily_snapshot'
            )

            self.assertTrue(result['success'])  # Overall operation succeeds
            self.assertEqual(result['successful_operations'], 1)
            self.assertEqual(result['failed_operations'], 1)

            # Verify details
            details = result['details']
            self.assertEqual(len(details), 2)

            # Find the failed operation
            failed_detail = next(d for d in details if not d['success'])
            self.assertEqual(failed_detail['portfolio_name'], 'Error Portfolio')
            self.assertIn('error', failed_detail)


class PortfolioHistoryServicePerformanceTestCase(TestCase):
    """
    Performance tests for Portfolio History Service
    """

    def setUp(self):
        """Set up performance test data"""
        self.user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com',
            password='testpass123'
        )

    def test_large_portfolio_calculation_performance(self):
        """Test performance with large number of transactions"""
        portfolio = Portfolio.objects.create(
            name='Large Portfolio',
            user=self.user,
            description='Portfolio with many transactions'
        )

        # Create cash account for large portfolio
        PortfolioCashAccount.objects.create(
            portfolio=portfolio,
            balance=Decimal('100000.00'),
            currency='USD'
        )

        # Create multiple securities
        securities = []
        for i in range(10):
            security = Security.objects.create(
                symbol=f'PERF{i:02d}',
                name=f'Performance Test Stock {i}',
                security_type='STOCK',
                exchange='NYSE',
                currency='USD',
                current_price=Decimal('150.00')
            )
            securities.append(security)

        # Create many transactions
        base_date = date.today() - timedelta(days=180)
        for i in range(500):  # 500 transactions
            transaction_date = base_date + timedelta(days=i // 3)  # Spread over time
            security = securities[i % len(securities)]

            Transaction.objects.create(
                portfolio=portfolio,
                security=security,
                transaction_type='BUY' if i % 4 != 0 else 'SELL',
                quantity=Decimal('10'),
                price=Decimal(f'{100 + (i % 50)}.00'),
                transaction_date=timezone.make_aware(
                    timezone.datetime.combine(transaction_date, timezone.datetime.min.time())
                ),
                description=f'Performance test transaction {i}'
            )

        # Mock price service for consistent results
        with patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date') as mock_price:
            mock_price.return_value = Decimal('150.00')

            import time
            start_time = time.time()

            result = PortfolioHistoryService.calculate_portfolio_value_on_date(
                portfolio, date.today()
            )

            end_time = time.time()
            calculation_time = end_time - start_time

            self.assertTrue(result['success'])
            self.assertLess(calculation_time, 5.0)  # Should complete in under 5 seconds

            print(f"Large portfolio calculation took: {calculation_time:.2f} seconds")

    def test_bulk_backfill_performance(self):
        """Test performance of bulk backfill operations"""
        # Create multiple portfolios
        portfolios = []
        for i in range(5):
            portfolio = Portfolio.objects.create(
                name=f'Bulk Perf Portfolio {i}',
                user=self.user,
                description=f'Bulk performance test portfolio {i}'
            )
            # Create cash account for each portfolio
            PortfolioCashAccount.objects.create(
                portfolio=portfolio,
                balance=Decimal('10000.00'),
                currency='USD'
            )
            portfolios.append(portfolio)

        # Mock price service
        with patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date') as mock_price:
            mock_price.return_value = Decimal('150.00')

            start_date = date.today() - timedelta(days=30)
            end_date = date.today() - timedelta(days=1)

            import time
            start_time = time.time()

            result = PortfolioHistoryService.bulk_portfolio_processing(
                portfolios, 'backfill',
                start_date=start_date, end_date=end_date, force_update=False
            )

            end_time = time.time()
            processing_time = end_time - start_time

            self.assertTrue(result['success'])
            self.assertLess(processing_time, 10.0)  # Should complete in under 10 seconds

            print(f"Bulk backfill took: {processing_time:.2f} seconds for {len(portfolios)} portfolios")


class PortfolioHistoryServiceConcurrencyTestCase(TestCase):
    """
    Test concurrent operations on Portfolio History Service
    """

    def setUp(self):
        """Set up concurrency test data"""
        self.user = User.objects.create_user(
            username='concurrencyuser',
            email='concurrency@example.com',
            password='testpass123'
        )

        self.portfolio = Portfolio.objects.create(
            name='Concurrency Test Portfolio',
            user=self.user,
            description='Portfolio for concurrency testing'
        )

        # Create cash account for concurrency test portfolio
        PortfolioCashAccount.objects.create(
            portfolio=self.portfolio,
            balance=Decimal('10000.00'),
            currency='USD'
        )

    def test_concurrent_snapshot_creation(self):
        """Test concurrent snapshot creation for same date"""
        from threading import Thread
        import threading

        target_date = date.today() - timedelta(days=1)
        results = []
        lock = threading.Lock()

        def create_snapshot():
            result = PortfolioHistoryService.save_daily_snapshot(
                self.portfolio, target_date, 'concurrent_test'
            )
            with lock:
                results.append(result)

        # Create multiple threads trying to create same snapshot
        threads = []
        for i in range(3):
            thread = Thread(target=create_snapshot)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        self.assertEqual(len(results), 3)

        # At least one should succeed
        successful_results = [r for r in results if r['success']]
        self.assertGreaterEqual(len(successful_results), 1)

        # Only one snapshot should exist in database
        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio, date=target_date
        )
        self.assertEqual(snapshots.count(), 1)

    def test_concurrent_backfill_operations(self):
        """Test concurrent backfill operations on same portfolio"""
        from threading import Thread
        import threading

        results = []
        lock = threading.Lock()

        def backfill_operation(days_offset):
            start_date = date.today() - timedelta(days=10 + days_offset)
            end_date = date.today() - timedelta(days=5 + days_offset)

            with patch('portfolio.services.price_history_service.PriceHistoryService.get_price_for_date') as mock_price:
                mock_price.return_value = Decimal('150.00')

                result = PortfolioHistoryService.backfill_portfolio_history(
                    self.portfolio, start_date, end_date, force_update=False
                )

                with lock:
                    results.append(result)

        # Create multiple threads with different date ranges
        threads = []
        for i in range(3):
            thread = Thread(target=backfill_operation, args=(i * 2,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all operations succeeded
        for result in results:
            self.assertTrue(result['success'])

        # Verify no duplicate snapshots were created
        all_snapshots = PortfolioValueHistory.objects.filter(
            portfolio=self.portfolio
        )

        # Count unique dates
        unique_dates = set(snapshot.date for snapshot in all_snapshots)
        self.assertEqual(len(unique_dates), all_snapshots.count())


if __name__ == '__main__':
    import unittest

    unittest.main()