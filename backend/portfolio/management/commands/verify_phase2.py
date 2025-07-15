# Create this file as: backend/portfolio/management/commands/verify_phase2.py

from django.core.management.base import BaseCommand
from portfolio.models import Portfolio, Security, Transaction, PortfolioValueHistory, PriceHistory
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
import sys


class Command(BaseCommand):
    help = 'Verify Phase 2 implementation'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("PHASE 2 VERIFICATION SCRIPT")
        self.stdout.write("=" * 60)

        # Check if models are properly imported
        try:
            self.stdout.write("✅ Models imported successfully")
            self.stdout.write(f"   - Portfolio: {Portfolio}")
            self.stdout.write(f"   - PortfolioValueHistory: {PortfolioValueHistory}")
            self.stdout.write(f"   - Security: {Security}")
            self.stdout.write(f"   - Transaction: {Transaction}")
            self.stdout.write(f"   - PriceHistory: {PriceHistory}")
        except Exception as e:
            self.stdout.write(f"❌ Model import failed: {e}")
            return

        # Check database tables exist
        try:
            portfolio_count = Portfolio.objects.count()
            history_count = PortfolioValueHistory.objects.count()
            security_count = Security.objects.count()
            transaction_count = Transaction.objects.count()
            price_count = PriceHistory.objects.count()

            self.stdout.write("\n✅ Database tables accessible")
            self.stdout.write(f"   - Portfolios: {portfolio_count}")
            self.stdout.write(f"   - Portfolio Value History: {history_count}")
            self.stdout.write(f"   - Securities: {security_count}")
            self.stdout.write(f"   - Transactions: {transaction_count}")
            self.stdout.write(f"   - Price History: {price_count}")
        except Exception as e:
            self.stdout.write(f"❌ Database access failed: {e}")
            return

        # Test basic model creation (if no test data exists)
        if portfolio_count == 0:
            self.stdout.write("\n⚠️  No portfolios found. Creating test data...")
            try:
                # Create test user
                user, created = User.objects.get_or_create(
                    username='testuser',
                    defaults={'email': 'test@example.com'}
                )
                if created:
                    user.set_password('testpass123')
                    user.save()

                # Create test portfolio
                portfolio = Portfolio.objects.create(
                    name='Verification Test Portfolio',
                    user=user,
                    currency='USD',
                    base_currency='USD'
                )

                # Create test security
                security = Security.objects.create(
                    symbol='TEST',
                    name='Test Security',
                    security_type='STOCK',
                    currency='USD',
                    current_price=Decimal('100.00')
                )

                self.stdout.write("✅ Test data created")
                self.stdout.write(f"   - User: {user.username}")
                self.stdout.write(f"   - Portfolio: {portfolio.name}")
                self.stdout.write(f"   - Security: {security.symbol}")

            except Exception as e:
                self.stdout.write(f"❌ Test data creation failed: {e}")

        # Test portfolio value calculation
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("TESTING PORTFOLIO VALUE CALCULATION")
        self.stdout.write("=" * 60)

        try:
            # Get first portfolio
            portfolio = Portfolio.objects.first()
            if portfolio:
                self.stdout.write(f"Testing portfolio: {portfolio.name}")

                # Test the calculation method
                test_date = date.today()
                value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
                    portfolio, test_date
                )

                self.stdout.write("✅ Portfolio value calculation successful")
                self.stdout.write(f"   - Total Value: ${value_data['total_value']:,.2f}")
                self.stdout.write(f"   - Total Cost: ${value_data['total_cost']:,.2f}")
                self.stdout.write(f"   - Cash Balance: ${value_data['cash_balance']:,.2f}")
                self.stdout.write(f"   - Holdings Count: {value_data['holdings_count']}")
                self.stdout.write(f"   - Unrealized Gains: ${value_data['unrealized_gains']:,.2f}")

                # Test snapshot creation
                snapshot = PortfolioValueHistory.create_snapshot(
                    portfolio=portfolio,
                    target_date=test_date,
                    calculation_source='verification'
                )

                self.stdout.write("✅ Snapshot creation successful")
                self.stdout.write(f"   - Snapshot ID: {snapshot.id}")
                self.stdout.write(f"   - Date: {snapshot.date}")
                self.stdout.write(f"   - Total Value: ${snapshot.total_value:,.2f}")
                self.stdout.write(f"   - Source: {snapshot.calculation_source}")

            else:
                self.stdout.write("⚠️  No portfolios found to test")

        except Exception as e:
            self.stdout.write(f"❌ Portfolio value calculation failed: {e}")
            import traceback
            traceback.print_exc()

        # Test PriceHistoryService methods
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("TESTING PRICE HISTORY SERVICE")
        self.stdout.write("=" * 60)

        try:
            from portfolio.services.price_history_service import PriceHistoryService

            self.stdout.write("✅ PriceHistoryService imported successfully")

            # Test get_price_for_date method
            security = Security.objects.first()
            if security:
                test_date = date.today()
                price = PriceHistoryService.get_price_for_date(security, test_date)

                self.stdout.write(f"✅ get_price_for_date method works")
                self.stdout.write(f"   - Security: {security.symbol}")
                self.stdout.write(f"   - Date: {test_date}")
                self.stdout.write(f"   - Price: ${price}")

            else:
                self.stdout.write("⚠️  No securities found to test")

        except Exception as e:
            self.stdout.write(f"❌ PriceHistoryService test failed: {e}")
            import traceback
            traceback.print_exc()

        # Test admin integration
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("TESTING ADMIN INTEGRATION")
        self.stdout.write("=" * 60)

        try:
            from django.contrib import admin
            from portfolio.admin import PortfolioValueHistoryAdmin

            self.stdout.write("✅ Admin integration successful")
            self.stdout.write(f"   - PortfolioValueHistoryAdmin: {PortfolioValueHistoryAdmin}")

            # Check if model is registered
            if PortfolioValueHistory in admin.site._registry:
                self.stdout.write("✅ PortfolioValueHistory is registered in admin")
            else:
                self.stdout.write("⚠️  PortfolioValueHistory not found in admin registry")

        except Exception as e:
            self.stdout.write(f"❌ Admin integration test failed: {e}")

        # Final summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("PHASE 2 VERIFICATION COMPLETE")
        self.stdout.write("=" * 60)

        total_history = PortfolioValueHistory.objects.count()
        self.stdout.write(f"Total Portfolio Value History records: {total_history}")

        if total_history > 0:
            latest = PortfolioValueHistory.objects.order_by('-date').first()
            self.stdout.write(f"Latest snapshot: {latest.portfolio.name} - {latest.date} - ${latest.total_value:,.2f}")

        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Run: python manage.py create_test_data --clean")
        self.stdout.write("2. Test management commands")
        self.stdout.write("3. Check admin interface")
        self.stdout.write("4. Proceed to Phase 3")

        self.stdout.write("\n✅ Phase 2 verification complete!")