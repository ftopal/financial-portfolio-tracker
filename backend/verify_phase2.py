# Create this file as: backend/verify_phase2.py
# Run it with: python manage.py shell < verify_phase2.py

from portfolio.models import Portfolio, Security, Transaction, PortfolioValueHistory, PriceHistory
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
import sys

print("=" * 60)
print("PHASE 2 VERIFICATION SCRIPT")
print("=" * 60)

# Check if models are properly imported
try:
    print("✅ Models imported successfully")
    print(f"   - Portfolio: {Portfolio}")
    print(f"   - PortfolioValueHistory: {PortfolioValueHistory}")
    print(f"   - Security: {Security}")
    print(f"   - Transaction: {Transaction}")
    print(f"   - PriceHistory: {PriceHistory}")
except Exception as e:
    print(f"❌ Model import failed: {e}")
    sys.exit(1)

# Check database tables exist
try:
    portfolio_count = Portfolio.objects.count()
    history_count = PortfolioValueHistory.objects.count()
    security_count = Security.objects.count()
    transaction_count = Transaction.objects.count()
    price_count = PriceHistory.objects.count()

    print("\n✅ Database tables accessible")
    print(f"   - Portfolios: {portfolio_count}")
    print(f"   - Portfolio Value History: {history_count}")
    print(f"   - Securities: {security_count}")
    print(f"   - Transactions: {transaction_count}")
    print(f"   - Price History: {price_count}")
except Exception as e:
    print(f"❌ Database access failed: {e}")
    sys.exit(1)

# Test basic model creation (if no test data exists)
if portfolio_count == 0:
    print("\n⚠️  No portfolios found. Creating test data...")
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

        print("✅ Test data created")
        print(f"   - User: {user.username}")
        print(f"   - Portfolio: {portfolio.name}")
        print(f"   - Security: {security.symbol}")

    except Exception as e:
        print(f"❌ Test data creation failed: {e}")

# Test portfolio value calculation
print("\n" + "=" * 60)
print("TESTING PORTFOLIO VALUE CALCULATION")
print("=" * 60)

try:
    # Get first portfolio
    portfolio = Portfolio.objects.first()
    if portfolio:
        print(f"Testing portfolio: {portfolio.name}")

        # Test the calculation method
        test_date = date.today()
        value_data = PortfolioValueHistory.calculate_portfolio_value_for_date(
            portfolio, test_date
        )

        print("✅ Portfolio value calculation successful")
        print(f"   - Total Value: ${value_data['total_value']:,.2f}")
        print(f"   - Total Cost: ${value_data['total_cost']:,.2f}")
        print(f"   - Cash Balance: ${value_data['cash_balance']:,.2f}")
        print(f"   - Holdings Count: {value_data['holdings_count']}")
        print(f"   - Unrealized Gains: ${value_data['unrealized_gains']:,.2f}")

        # Test snapshot creation
        snapshot = PortfolioValueHistory.create_snapshot(
            portfolio=portfolio,
            target_date=test_date,
            calculation_source='verification'
        )

        print("✅ Snapshot creation successful")
        print(f"   - Snapshot ID: {snapshot.id}")
        print(f"   - Date: {snapshot.date}")
        print(f"   - Total Value: ${snapshot.total_value:,.2f}")
        print(f"   - Source: {snapshot.calculation_source}")

    else:
        print("⚠️  No portfolios found to test")

except Exception as e:
    print(f"❌ Portfolio value calculation failed: {e}")
    import traceback

    traceback.print_exc()

# Test PriceHistoryService methods
print("\n" + "=" * 60)
print("TESTING PRICE HISTORY SERVICE")
print("=" * 60)

try:
    from portfolio.services.price_history_service import PriceHistoryService

    print("✅ PriceHistoryService imported successfully")

    # Test get_price_for_date method
    security = Security.objects.first()
    if security:
        test_date = date.today()
        price = PriceHistoryService.get_price_for_date(security, test_date)

        print(f"✅ get_price_for_date method works")
        print(f"   - Security: {security.symbol}")
        print(f"   - Date: {test_date}")
        print(f"   - Price: ${price}")

    else:
        print("⚠️  No securities found to test")

except Exception as e:
    print(f"❌ PriceHistoryService test failed: {e}")
    import traceback

    traceback.print_exc()

# Test admin integration
print("\n" + "=" * 60)
print("TESTING ADMIN INTEGRATION")
print("=" * 60)

try:
    from django.contrib import admin
    from portfolio.admin import PortfolioValueHistoryAdmin

    print("✅ Admin integration successful")
    print(f"   - PortfolioValueHistoryAdmin: {PortfolioValueHistoryAdmin}")

    # Check if model is registered
    if PortfolioValueHistory in admin.site._registry:
        print("✅ PortfolioValueHistory is registered in admin")
    else:
        print("⚠️  PortfolioValueHistory not found in admin registry")

except Exception as e:
    print(f"❌ Admin integration test failed: {e}")

# Final summary
print("\n" + "=" * 60)
print("PHASE 2 VERIFICATION COMPLETE")
print("=" * 60)

total_history = PortfolioValueHistory.objects.count()
print(f"Total Portfolio Value History records: {total_history}")

if total_history > 0:
    latest = PortfolioValueHistory.objects.order_by('-date').first()
    print(f"Latest snapshot: {latest.portfolio.name} - {latest.date} - ${latest.total_value:,.2f}")

print("\nNext steps:")
print("1. Run: python manage.py create_test_data --clean")
print("2. Test management commands")
print("3. Check admin interface")
print("4. Proceed to Phase 3")

print("\n✅ Phase 2 verification complete!")