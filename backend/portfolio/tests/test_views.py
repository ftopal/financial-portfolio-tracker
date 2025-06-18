from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from .test_base import BaseTestCase
from ..models import Portfolio, Security, Transaction


class PortfolioViewSetTest(BaseTestCase):

    def test_list_portfolios(self):
        """Test listing user's portfolios"""
        url = reverse('portfolio-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Portfolio')

    def test_create_portfolio(self):
        """Test creating a new portfolio"""
        url = reverse('portfolio-list')
        data = {
            'name': 'New Portfolio',
            'description': 'Test description',
            'currency': 'USD'
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Portfolio.objects.count(), 2)
        self.assertEqual(response.data['name'], 'New Portfolio')

    def test_portfolio_holdings(self):
        """Test getting portfolio holdings"""
        # Add a transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        url = reverse('portfolio-holdings', kwargs={'pk': self.portfolio.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['holdings']), 1)
        self.assertEqual(response.data['holdings'][0]['security']['symbol'], 'AAPL')

    def test_portfolio_transactions(self):
        """Test getting portfolio transactions"""
        # Add transactions
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        url = reverse('portfolio-transactions', kwargs={'pk': self.portfolio.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['transaction_type'], 'BUY')

    def test_unauthorized_access(self):
        """Test unauthorized access is blocked"""
        self.client.credentials()  # Remove auth
        url = reverse('portfolio-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SecurityViewSetTest(BaseTestCase):

    def test_list_securities(self):
        """Test listing securities"""
        url = reverse('security-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # We created 4 securities in setup

    def test_search_securities(self):
        """Test searching securities"""
        url = reverse('security-search')

        # Search for Apple
        response = self.client.get(url, {'q': 'AAPL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['symbol'], 'AAPL')

        # Search by name
        response = self.client.get(url, {'q': 'Apple'})
        self.assertEqual(len(response.data['results']), 1)

        # Search with no results
        response = self.client.get(url, {'q': 'XXXXX'})
        self.assertEqual(len(response.data['results']), 0)

    def test_update_security_price(self):
        """Test updating security price"""
        url = reverse('security-update-price', kwargs={'pk': self.stock_aapl.id})
        data = {'price': '155.00'}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.stock_aapl.refresh_from_db()
        self.assertEqual(self.stock_aapl.current_price, Decimal('155.00'))


class TransactionViewSetTest(BaseTestCase):

    def test_create_buy_transaction(self):
        """Test creating a buy transaction"""
        url = reverse('transaction-list')
        data = {
            'portfolio': self.portfolio.id,
            'security': self.stock_aapl.id,
            'transaction_type': 'BUY',
            'quantity': '10',
            'price': '100',
            'fees': '10'
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)

        transaction = Transaction.objects.first()
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.quantity, Decimal('10'))
        self.assertEqual(transaction.total_value, Decimal('1010'))

    def test_create_sell_transaction(self):
        """Test creating a sell transaction"""
        # First buy some shares
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        # Now sell some
        url = reverse('transaction-list')
        data = {
            'portfolio': self.portfolio.id,
            'security': self.stock_aapl.id,
            'transaction_type': 'SELL',
            'quantity': '5',
            'price': '150',
            'fees': '10'
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_create_dividend_transaction(self):
        """Test creating a dividend transaction"""
        url = reverse('transaction-list')
        data = {
            'portfolio': self.portfolio.id,
            'security': self.stock_aapl.id,
            'transaction_type': 'DIVIDEND',
            'quantity': '10',  # Number of shares
            'price': '0',
            'dividend_per_share': '0.88',
            'fees': '0'
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        transaction = Transaction.objects.last()
        self.assertEqual(transaction.dividend_per_share, Decimal('0.88'))
        self.assertEqual(transaction.total_value, Decimal('8.80'))

    def test_filter_transactions(self):
        """Test filtering transactions"""
        # Create multiple transactions
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
            quantity=Decimal('5'),
            price=Decimal('2500'),
            fees=Decimal('25')
        )

        url = reverse('transaction-list')

        # Filter by security
        response = self.client.get(url, {'security_id': self.stock_aapl.id})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['security'], self.stock_aapl.id)

        # Filter by portfolio
        response = self.client.get(url, {'portfolio_id': self.portfolio.id})
        self.assertEqual(len(response.data), 2)


class PortfolioSummaryTest(BaseTestCase):

    def test_portfolio_summary(self):
        """Test portfolio summary endpoint"""
        # Create transactions
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
            security=self.stock_aapl,
            user=self.user,
            transaction_type='DIVIDEND',
            quantity=Decimal('10'),
            price=Decimal('0'),
            dividend_per_share=Decimal('0.88'),
            fees=Decimal('0')
        )

        url = reverse('portfolio-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_cost']), 1010.0)
        self.assertEqual(float(response.data['total_dividends']), 8.80)
        self.assertIn('portfolios', response.data)