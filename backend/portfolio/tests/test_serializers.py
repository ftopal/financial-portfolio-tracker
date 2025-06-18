from decimal import Decimal
from .test_base import BaseTestCase
from ..models import Transaction
from ..serializers_new import (
    SecuritySerializer, TransactionSerializer,
    PortfolioSerializer, PortfolioDetailSerializer
)


class SecuritySerializerTest(BaseTestCase):

    def test_security_serialization(self):
        """Test security serializer"""
        serializer = SecuritySerializer(self.stock_aapl)
        data = serializer.data

        self.assertEqual(data['symbol'], 'AAPL')
        self.assertEqual(data['name'], 'Apple Inc.')
        self.assertEqual(data['security_type'], 'STOCK')
        self.assertEqual(float(data['current_price']), 150.00)
        self.assertEqual(data['sector'], 'Technology')

    def test_security_list_serialization(self):
        """Test serializing multiple securities"""
        securities = [self.stock_aapl, self.stock_googl, self.etf_spy]
        serializer = SecuritySerializer(securities, many=True)
        data = serializer.data

        self.assertEqual(len(data), 3)
        symbols = [item['symbol'] for item in data]
        self.assertIn('AAPL', symbols)
        self.assertIn('GOOGL', symbols)
        self.assertIn('SPY', symbols)


class TransactionSerializerTest(BaseTestCase):

    def test_transaction_serialization(self):
        """Test transaction serializer"""
        transaction = Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        serializer = TransactionSerializer(transaction)
        data = serializer.data

        self.assertEqual(data['security_symbol'], 'AAPL')
        self.assertEqual(data['security_name'], 'Apple Inc.')
        self.assertEqual(data['portfolio_name'], 'Test Portfolio')
        self.assertEqual(data['transaction_type'], 'BUY')
        self.assertEqual(float(data['quantity']), 10.0)
        self.assertEqual(float(data['price']), 100.0)
        self.assertEqual(float(data['total_value']), 1010.0)

    def test_transaction_creation_through_serializer(self):
        """Test creating transaction through serializer"""
        data = {
            'portfolio': self.portfolio.id,
            'security': self.stock_googl.id,
            'transaction_type': 'BUY',
            'quantity': '5',
            'price': '2500',
            'fees': '25'
        }

        # Create a request-like context
        serializer = TransactionSerializer(
            data=data,
            context={'request': type('Request', (), {'user': self.user})()}
        )

        self.assertTrue(serializer.is_valid())
        transaction = serializer.save()

        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.security, self.stock_googl)
        self.assertEqual(transaction.quantity, Decimal('5'))


class PortfolioSerializerTest(BaseTestCase):

    def test_portfolio_serialization(self):
        """Test basic portfolio serialization"""
        serializer = PortfolioSerializer(self.portfolio)
        data = serializer.data

        self.assertEqual(data['name'], 'Test Portfolio')
        self.assertEqual(data['description'], 'Test portfolio for unit tests')
        self.assertTrue(data['is_default'])
        self.assertEqual(data['holdings_count'], 0)  # No transactions yet

    def test_portfolio_with_holdings(self):
        """Test portfolio serialization with holdings"""
        # Add some transactions
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        serializer = PortfolioSerializer(self.portfolio)
        data = serializer.data

        self.assertEqual(data['holdings_count'], 1)
        self.assertEqual(float(data['total_cost']), 1010.0)
        self.assertEqual(float(data['total_value']), 1500.0)  # 10 shares * $150 current

    def test_portfolio_detail_serialization(self):
        """Test detailed portfolio serialization"""
        # Add transaction
        Transaction.objects.create(
            portfolio=self.portfolio,
            security=self.stock_aapl,
            user=self.user,
            transaction_type='BUY',
            quantity=Decimal('10'),
            price=Decimal('100'),
            fees=Decimal('10')
        )

        serializer = PortfolioDetailSerializer(self.portfolio)
        data = serializer.data

        # Should include holdings
        self.assertIn('holdings', data)
        self.assertEqual(len(data['holdings']), 1)

        # Check holding details
        holding = data['holdings'][0]
        self.assertEqual(holding['security']['symbol'], 'AAPL')
        self.assertEqual(float(holding['quantity']), 10.0)
        self.assertEqual(float(holding['current_value']), 1500.0)

        # Should include summary
        self.assertIn('summary', data)
        self.assertEqual(float(data['summary']['total_value']), 1500.0)