# backend/portfolio/management/commands/verify_phase4.py
"""
Phase 4 Verification Command - API Endpoints Testing (FIXED)

This command verifies that all Phase 4 API endpoints are working correctly
by testing them programmatically.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
import json

from portfolio.models import Portfolio, Security, Transaction, PortfolioValueHistory
from portfolio.services.portfolio_history_service import PortfolioHistoryService


class Command(BaseCommand):
    help = 'Verify Phase 4 API endpoints implementation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed test results'
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test data if none exists'
        )

    def handle(self, *args, **options):
        self.detailed = options.get('detailed', False)
        self.create_test_data = options.get('create_test_data', False)

        self.stdout.write(self.style.SUCCESS('🚀 Phase 4 API Endpoints Verification'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Setup test environment
        if not self._setup_test_environment():
            return

        # Run API tests
        self._test_performance_endpoint()
        self._test_performance_summary_endpoint()
        self._test_recalculate_endpoint()
        self._test_retention_policy()
        self._test_period_calculations()
        self._test_error_handling()

        self.stdout.write(self.style.SUCCESS('\n🎉 Phase 4 API Endpoints Verification Complete!'))

    def _setup_test_environment(self):
        """Setup test user, portfolio, and data"""
        try:
            # Create or get test user
            self.user, created = User.objects.get_or_create(
                username='api_test_user',
                defaults={
                    'email': 'apitest@example.com',
                    'first_name': 'API',
                    'last_name': 'Test'
                }
            )

            # Create API client
            self.client = APIClient()
            self.client.force_authenticate(user=self.user)

            # Create or get test portfolio
            self.portfolio, created = Portfolio.objects.get_or_create(
                name='API Test Portfolio',
                user=self.user,
                defaults={
                    'description': 'Test portfolio for API endpoints',
                    'currency': 'USD'
                }
            )

            # Create test data if requested or none exists
            if self.create_test_data or not Transaction.objects.filter(portfolio=self.portfolio).exists():
                self._create_test_data()

            self.stdout.write(self.style.SUCCESS(f'✅ Test environment ready'))
            self.stdout.write(f'   User: {self.user.username}')
            self.stdout.write(f'   Portfolio: {self.portfolio.name} (ID: {self.portfolio.id})')

            return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to setup test environment: {str(e)}'))
            return False

    def _create_test_data(self):
        """Create test securities, transactions, and portfolio history"""
        # Create test security
        security, created = Security.objects.get_or_create(
            symbol='TSLA',
            defaults={
                'name': 'Tesla Inc',
                'security_type': 'STOCK',
                'exchange': 'NASDAQ',
                'currency': 'USD',
                'current_price': Decimal('250.00')
            }
        )

        # Create test transactions
        base_date = date.today() - timedelta(days=90)

        # Buy transaction
        Transaction.objects.get_or_create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='BUY',
            quantity=Decimal('100'),
            price=Decimal('200.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date, timezone.datetime.min.time())
            ),
            user=self.user,
            defaults={'notes': 'API test buy'}
        )

        # Another buy transaction
        Transaction.objects.get_or_create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='BUY',
            quantity=Decimal('50'),
            price=Decimal('220.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date + timedelta(days=30), timezone.datetime.min.time())
            ),
            user=self.user,
            defaults={'notes': 'API test buy 2'}
        )

        # Sell transaction
        Transaction.objects.get_or_create(
            portfolio=self.portfolio,
            security=security,
            transaction_type='SELL',
            quantity=Decimal('25'),
            price=Decimal('240.00'),
            transaction_date=timezone.make_aware(
                timezone.datetime.combine(base_date + timedelta(days=60), timezone.datetime.min.time())
            ),
            user=self.user,
            defaults={'notes': 'API test sell'}
        )

        # Create portfolio history snapshots
        try:
            PortfolioHistoryService.backfill_portfolio_history(
                self.portfolio, base_date, date.today()
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Portfolio history backfill failed: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'✅ Test data created'))

    def _test_performance_endpoint(self):
        """Test GET /api/portfolios/{id}/performance/"""
        self.stdout.write(self.style.WARNING('\n📊 Testing Performance Endpoint'))

        url = f'/api/portfolios/{self.portfolio.id}/performance/'

        # Test with default parameters
        response = self.client.get(url)
        self._check_response(response, 'Performance endpoint (default)')

        if response.status_code == 200:
            data = response.json()
            required_fields = ['portfolio_id', 'portfolio_name', 'period', 'start_date', 'end_date', 'chart_data',
                               'summary']
            self._check_response_fields(data, required_fields, 'Performance data')

            # Check chart data format
            chart_data = data.get('chart_data', {})
            if 'series' in chart_data and len(chart_data['series']) > 0:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Chart data format correct'))
                if self.detailed:
                    series_data = chart_data['series'][0]['data']
                    self.stdout.write(f'      Data points: {len(series_data)}')
                    if series_data:
                        self.stdout.write(f'      Sample point: {series_data[0]}')
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Chart data format may be incorrect'))
                if self.detailed:
                    self.stdout.write(f'      Chart data keys: {list(chart_data.keys())}')

            # Check summary data
            summary = data.get('summary', {})
            if summary:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Summary data present'))
                if self.detailed:
                    self.stdout.write(f'      Summary keys: {list(summary.keys())}')
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Summary data missing'))

        # Test with specific period
        response = self.client.get(url + '?period=3M')
        self._check_response(response, 'Performance endpoint (3M period)')

        # Test with date range
        start_date = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')
        response = self.client.get(url + f'?start_date={start_date}&end_date={end_date}')
        self._check_response(response, 'Performance endpoint (date range)')

    def _test_performance_summary_endpoint(self):
        """Test GET /api/portfolios/{id}/performance_summary/"""
        self.stdout.write(self.style.WARNING('\n📈 Testing Performance Summary Endpoint'))

        url = f'/api/portfolios/{self.portfolio.id}/performance_summary/'

        response = self.client.get(url)
        self._check_response(response, 'Performance summary endpoint')

        if response.status_code == 200:
            data = response.json()
            required_fields = ['portfolio_id', 'portfolio_name', 'period', 'start_date', 'end_date', 'summary']
            self._check_response_fields(data, required_fields, 'Performance summary data')

            # Should NOT have chart_data
            if 'chart_data' not in data:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Chart data correctly excluded from summary'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Chart data should not be in summary endpoint'))

    def _test_recalculate_endpoint(self):
        """Test POST /api/portfolios/{id}/recalculate_performance/"""
        self.stdout.write(self.style.WARNING('\n🔄 Testing Recalculate Endpoint'))

        url = f'/api/portfolios/{self.portfolio.id}/recalculate_performance/'

        # Test with default parameters
        response = self.client.post(url)
        self._check_response(response, 'Recalculate endpoint (default)')

        if response.status_code == 200:
            data = response.json()
            required_fields = ['success', 'message', 'portfolio_id', 'portfolio_name', 'start_date', 'end_date']
            self._check_response_fields(data, required_fields, 'Recalculate response')

        # Test with specific parameters
        response = self.client.post(url, {
            'days': 7,
            'force': True
        })
        self._check_response(response, 'Recalculate endpoint (custom params)')

    def _test_retention_policy(self):
        """Test retention policy enforcement"""
        self.stdout.write(self.style.WARNING('\n🔐 Testing Retention Policy'))

        url = f'/api/portfolios/{self.portfolio.id}/performance/'

        # Test with period that exceeds retention limit
        response = self.client.get(url + '?period=ALL')
        self._check_response(response, 'Retention policy test')

        if response.status_code == 200:
            data = response.json()
            if 'retention_applied' in data:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Retention policy field present'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Retention policy field missing'))

    def _test_period_calculations(self):
        """Test different period calculations"""
        self.stdout.write(self.style.WARNING('\n📅 Testing Period Calculations'))

        url = f'/api/portfolios/{self.portfolio.id}/performance/'
        periods = ['1M', '3M', '6M', '1Y', 'YTD', 'ALL']

        for period in periods:
            response = self.client.get(url + f'?period={period}')
            if response.status_code == 200:
                data = response.json()
                if data.get('period') == period:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Period {period} working'))
                else:
                    self.stdout.write(self.style.WARNING(f'   ⚠️  Period {period} may have issues'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Period {period} failed'))

    def _test_error_handling(self):
        """Test error handling scenarios"""
        self.stdout.write(self.style.WARNING('\n🚨 Testing Error Handling'))

        # Test invalid portfolio ID
        url = f'/api/portfolios/99999/performance/'
        response = self.client.get(url)
        if response.status_code == 404:
            self.stdout.write(self.style.SUCCESS(f'   ✅ Invalid portfolio ID handled correctly'))
        else:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Invalid portfolio ID response: {response.status_code}'))

        # Test invalid date format
        url = f'/api/portfolios/{self.portfolio.id}/performance/'
        response = self.client.get(url + '?start_date=invalid-date')
        if response.status_code == 400:
            self.stdout.write(self.style.SUCCESS(f'   ✅ Invalid date format handled correctly'))
        else:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Invalid date format response: {response.status_code}'))

        # Test invalid recalculate parameters
        url = f'/api/portfolios/{self.portfolio.id}/recalculate_performance/'
        response = self.client.post(url, {'days': 500})  # Exceeds maximum
        if response.status_code == 400:
            self.stdout.write(self.style.SUCCESS(f'   ✅ Invalid recalculate params handled correctly'))
        else:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Invalid recalculate params response: {response.status_code}'))

    def _check_response(self, response, test_name):
        """Check API response status and log results"""
        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS(f'   ✅ {test_name}: SUCCESS'))
            if self.detailed:
                self.stdout.write(f'      Response: {response.json()}')
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ {test_name}: FAILED (Status: {response.status_code})'))
            if self.detailed:
                self.stdout.write(f'      Response: {response.content}')

    def _check_response_fields(self, data, required_fields, data_type):
        """Check if response contains required fields"""
        missing_fields = [field for field in required_fields if field not in data]
        if not missing_fields:
            self.stdout.write(self.style.SUCCESS(f'   ✅ {data_type} contains all required fields'))
        else:
            self.stdout.write(self.style.WARNING(f'   ⚠️  {data_type} missing fields: {missing_fields}'))

        if self.detailed:
            self.stdout.write(f'      Available fields: {list(data.keys())}')