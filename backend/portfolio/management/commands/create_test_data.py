# Create this file as: backend/portfolio/management/commands/create_test_data.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from portfolio.models import Portfolio, Security, Transaction, PriceHistory, PortfolioValueHistory
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create test data for portfolio value history testing'

    def add_arguments(self, parser):
        parser.add_argument('--user', default='testuser', help='Username for test user')
        parser.add_argument('--portfolio', default='Test Portfolio', help='Name for test portfolio')
        parser.add_argument('--clean', action='store_true', help='Clean existing test data first')

    def handle(self, *args, **options):
        username = options['user']
        portfolio_name = options['portfolio']
        clean = options['clean']

        if clean:
            self.stdout.write('Cleaning existing test data...')
            # Clean up test data
            PortfolioValueHistory.objects.filter(portfolio__name=portfolio_name).delete()
            Transaction.objects.filter(portfolio__name=portfolio_name).delete()
            Portfolio.objects.filter(name=portfolio_name).delete()
            PriceHistory.objects.filter(security__symbol='GOOG').delete()
            Security.objects.filter(symbol='GOOG').delete()
            if User.objects.filter(username=username).exists():
                User.objects.get(username=username).delete()
            self.stdout.write(self.style.SUCCESS('Test data cleaned'))

        # Create test user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created test user: {username}')
        else:
            self.stdout.write(f'Test user already exists: {username}')

        # Create test portfolio
        portfolio, created = Portfolio.objects.get_or_create(
            name=portfolio_name,
            user=user,
            defaults={
                'currency': 'USD',
                'base_currency': 'USD',
                'description': 'Test portfolio for portfolio value history testing'
            }
        )
        if created:
            self.stdout.write(f'Created test portfolio: {portfolio_name}')
        else:
            self.stdout.write(f'Test portfolio already exists: {portfolio_name}')

        # Create test security
        security, created = Security.objects.get_or_create(
            symbol='GOOG',
            defaults={
                'name': 'Alphabet Inc',
                'security_type': 'STOCK',
                'currency': 'USD',
                'current_price': Decimal('150.00'),
                'exchange': 'NASDAQ'
            }
        )
        if created:
            self.stdout.write('Created test security: GOOG')
        else:
            self.stdout.write('Test security already exists: GOOG')

        # Create historical price data for the last 30 days
        self.stdout.write('Creating historical price data...')
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        current_date = start_date
        base_price = Decimal('100.00')

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                # Simulate price movement (small random changes)
                import random
                change_pct = Decimal(str(random.uniform(-0.05, 0.05)))  # -5% to +5%
                price = base_price * (1 + change_pct)

                # Create price history record
                price_history, created = PriceHistory.objects.get_or_create(
                    security=security,
                    date=timezone.make_aware(
                        timezone.datetime.combine(current_date, timezone.datetime.min.time())
                    ),
                    defaults={
                        'close_price': price,
                        'open_price': price * Decimal('0.995'),
                        'high_price': price * Decimal('1.02'),
                        'low_price': price * Decimal('0.98'),
                        'volume': 1000000,
                        'currency': 'USD',
                        'data_source': 'test'
                    }
                )

                if created:
                    base_price = price  # Use this as base for next day

            current_date += timedelta(days=1)

        self.stdout.write('Historical price data created')

        # Create test transactions
        self.stdout.write('Creating test transactions...')

        # Buy transaction 1 - 20 days ago
        buy_date1 = timezone.now() - timedelta(days=20)
        Transaction.objects.get_or_create(
            portfolio=portfolio,
            security=security,
            user=user,
            transaction_type='BUY',
            transaction_date=buy_date1,
            defaults={
                'quantity': Decimal('10.00'),
                'price': Decimal('105.00'),
                'fees': Decimal('5.00'),
                'currency': 'USD'
            }
        )

        # Buy transaction 2 - 15 days ago
        buy_date2 = timezone.now() - timedelta(days=15)
        Transaction.objects.get_or_create(
            portfolio=portfolio,
            security=security,
            user=user,
            transaction_type='BUY',
            transaction_date=buy_date2,
            defaults={
                'quantity': Decimal('5.00'),
                'price': Decimal('110.00'),
                'fees': Decimal('2.50'),
                'currency': 'USD'
            }
        )

        # Sell transaction - 10 days ago
        sell_date = timezone.now() - timedelta(days=10)
        Transaction.objects.get_or_create(
            portfolio=portfolio,
            security=security,
            user=user,
            transaction_type='SELL',
            transaction_date=sell_date,
            defaults={
                'quantity': Decimal('3.00'),
                'price': Decimal('115.00'),
                'fees': Decimal('1.50'),
                'currency': 'USD'
            }
        )

        # Dividend transaction - 5 days ago
        dividend_date = timezone.now() - timedelta(days=5)
        Transaction.objects.get_or_create(
            portfolio=portfolio,
            security=security,
            user=user,
            transaction_type='DIVIDEND',
            transaction_date=dividend_date,
            defaults={
                'quantity': Decimal('12.00'),  # 12 shares held at time of dividend
                'price': Decimal('2.00'),  # $2 per share dividend
                'dividend_per_share': Decimal('2.00'),
                'currency': 'USD'
            }
        )

        self.stdout.write('Test transactions created')

        # Create sample portfolio value history
        self.stdout.write('Creating sample portfolio value history...')

        # Create snapshots for the last 10 days
        for i in range(10):
            snapshot_date = date.today() - timedelta(days=i)

            # Skip weekends
            if snapshot_date.weekday() < 5:
                try:
                    snapshot = PortfolioValueHistory.create_snapshot(
                        portfolio=portfolio,
                        target_date=snapshot_date,
                        calculation_source='test_data'
                    )

                    self.stdout.write(
                        f'Created snapshot for {snapshot_date}: '
                        f'${snapshot.total_value:,.2f} '
                        f'({snapshot.holdings_count} holdings)'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Error creating snapshot for {snapshot_date}: {str(e)}')
                    )

        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== TEST DATA CREATED SUCCESSFULLY ==='))
        self.stdout.write(f'User: {user.username}')
        self.stdout.write(f'Portfolio: {portfolio.name}')
        self.stdout.write(f'Security: {security.symbol}')
        self.stdout.write(f'Transactions: {Transaction.objects.filter(portfolio=portfolio).count()}')
        self.stdout.write(f'Price History Records: {PriceHistory.objects.filter(security=security).count()}')
        self.stdout.write(
            f'Portfolio Value History: {PortfolioValueHistory.objects.filter(portfolio=portfolio).count()}')

        # Show how to test
        self.stdout.write('\n=== HOW TO TEST ===')
        self.stdout.write('1. Test portfolio value calculation:')
        self.stdout.write(f'   python manage.py manage_portfolio_history create --portfolio-name "{portfolio_name}"')
        self.stdout.write('')
        self.stdout.write('2. List portfolio history:')
        self.stdout.write(f'   python manage.py manage_portfolio_history list --portfolio-name "{portfolio_name}"')
        self.stdout.write('')
        self.stdout.write('3. Show statistics:')
        self.stdout.write(f'   python manage.py manage_portfolio_history stats --portfolio-name "{portfolio_name}"')
        self.stdout.write('')
        self.stdout.write('4. Backfill more history:')
        self.stdout.write(
            f'   python manage.py manage_portfolio_history backfill --portfolio-name "{portfolio_name}" --days 30')
        self.stdout.write('')
        self.stdout.write('5. Run tests:')
        self.stdout.write('   python manage.py test portfolio.tests.test_portfolio_value_history')
        self.stdout.write('')
        self.stdout.write('6. View in admin:')
        self.stdout.write('   http://localhost:8000/admin/ (login with your admin account)')
        self.stdout.write('   Go to Portfolio -> Portfolio Value History')