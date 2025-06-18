from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from ..models import Portfolio, Security, Transaction, AssetCategory


class BaseTestCase(TestCase):
    """Base test case with common setup"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create API client with authentication
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Create test portfolio
        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name='Test Portfolio',
            description='Test portfolio for unit tests',
            is_default=True
        )

        # Create test securities
        self.stock_aapl = Security.objects.create(
            symbol='AAPL',
            name='Apple Inc.',
            security_type='STOCK',
            exchange='NASDAQ',
            currency='USD',
            current_price=Decimal('150.00'),
            sector='Technology',
            industry='Consumer Electronics'
        )

        self.stock_googl = Security.objects.create(
            symbol='GOOGL',
            name='Alphabet Inc.',
            security_type='STOCK',
            exchange='NASDAQ',
            currency='USD',
            current_price=Decimal('2800.00'),
            sector='Technology',
            industry='Internet Services'
        )

        self.etf_spy = Security.objects.create(
            symbol='SPY',
            name='SPDR S&P 500 ETF',
            security_type='ETF',
            exchange='NYSE',
            currency='USD',
            current_price=Decimal('450.00')
        )

        self.crypto_btc = Security.objects.create(
            symbol='BTC',
            name='Bitcoin',
            security_type='CRYPTO',
            exchange='Crypto',
            currency='USD',
            current_price=Decimal('45000.00')
        )

        # Create test category
        self.category = AssetCategory.objects.create(
            name='Technology',
            description='Technology stocks'
        )