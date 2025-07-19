# backend/portfolio/management/commands/fix_currency_usage.py

from django.core.management.base import BaseCommand
from django.db import transaction
from portfolio.models import Portfolio


class Command(BaseCommand):
    help = 'Fix currency field usage - standardize on base_currency'

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Actually execute the fixes (default: dry run)'
        )

    def handle(self, *args, **options):
        execute = options['execute']

        if not execute:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - Use --execute to apply changes")
            )

        self.stdout.write(
            self.style.SUCCESS("🔧 Fixing Portfolio Currency Field Usage")
        )
        self.stdout.write("=" * 80)

        # Step 1: Analyze current state
        self.analyze_current_state()

        # Step 2: Fix database inconsistencies
        if execute:
            self.fix_database_currencies()
        else:
            self.preview_database_fixes()

        # Step 3: Show codebase changes needed
        self.show_codebase_changes()

    def analyze_current_state(self):
        """Analyze current portfolio currency state"""
        self.stdout.write(f"\n📊 Current Portfolio Currency Analysis:")

        portfolios = Portfolio.objects.all()

        for portfolio in portfolios:
            currency = portfolio.currency
            base_currency = portfolio.base_currency

            status = "✅ MATCH" if currency == base_currency else "❌ MISMATCH"

            self.stdout.write(f"   {portfolio.name}:")
            self.stdout.write(f"     currency: {currency}")
            self.stdout.write(f"     base_currency: {base_currency}")
            self.stdout.write(f"     Status: {status}")

            # Check cash account
            if hasattr(portfolio, 'cash_account'):
                cash_currency = portfolio.cash_account.currency
                self.stdout.write(f"     cash_account.currency: {cash_currency}")

    def fix_database_currencies(self):
        """Fix database currency inconsistencies"""
        self.stdout.write(f"\n🔧 Fixing Database Currency Fields:")

        with transaction.atomic():
            portfolios = Portfolio.objects.all()
            updated_count = 0

            for portfolio in portfolios:
                if portfolio.currency != portfolio.base_currency:
                    old_currency = portfolio.currency
                    portfolio.currency = portfolio.base_currency
                    portfolio.save()
                    updated_count += 1

                    self.stdout.write(f"   ✅ {portfolio.name}: {old_currency} → {portfolio.base_currency}")

                    # Also update cash account if needed
                    if hasattr(portfolio, 'cash_account'):
                        cash_account = portfolio.cash_account
                        if cash_account.currency != portfolio.base_currency:
                            old_cash_currency = cash_account.currency
                            cash_account.currency = portfolio.base_currency
                            cash_account.save()
                            self.stdout.write(f"      Cash account: {old_cash_currency} → {portfolio.base_currency}")

            self.stdout.write(f"\n✅ Updated {updated_count} portfolios")

    def preview_database_fixes(self):
        """Preview what database changes would be made"""
        self.stdout.write(f"\n👀 Database Changes Preview:")

        portfolios = Portfolio.objects.all()
        changes_needed = 0

        for portfolio in portfolios:
            if portfolio.currency != portfolio.base_currency:
                changes_needed += 1
                self.stdout.write(f"   Would update {portfolio.name}: {portfolio.currency} → {portfolio.base_currency}")

        if changes_needed == 0:
            self.stdout.write(f"   No database changes needed")
        else:
            self.stdout.write(f"\n📊 {changes_needed} portfolios need currency field updates")

    def show_codebase_changes(self):
        """Show what codebase changes are needed"""
        self.stdout.write(f"\n📝 Codebase Changes Needed:")

        changes = [
            {
                'file': 'backend/portfolio/models.py',
                'change': 'Update get_holdings() to use base_currency consistently',
                'details': 'portfolio_currency = self.base_currency or self.currency'
            },
            {
                'file': 'backend/portfolio/services/currency_service.py',
                'change': 'Replace portfolio.currency with portfolio.base_currency',
                'details': 'Multiple functions reference portfolio.currency'
            },
            {
                'file': 'backend/portfolio/views.py',
                'change': 'Update API responses to use base_currency',
                'details': 'Ensure consistent currency field usage'
            },
            {
                'file': 'backend/portfolio/serializers.py',
                'change': 'Update transaction serialization',
                'details': 'Use portfolio.base_currency for consistency'
            }
        ]

        for i, change in enumerate(changes, 1):
            self.stdout.write(f"\n   {i}. {change['file']}")
            self.stdout.write(f"      Change: {change['change']}")
            self.stdout.write(f"      Details: {change['details']}")

        # Show migration strategy
        self.stdout.write(f"\n🗺️  Migration Strategy:")
        self.stdout.write(f"   1. ✅ Fix portfolio_history_service.py (already done)")
        self.stdout.write(f"   2. Run this command with --execute to fix database")
        self.stdout.write(f"   3. Update other services to use base_currency")
        self.stdout.write(f"   4. Test thoroughly")
        self.stdout.write(f"   5. Consider removing currency field in future migration")

        self.stdout.write(f"\n⚠️  Safety Notes:")
        self.stdout.write(f"   - base_currency has correct values")
        self.stdout.write(f"   - currency field always shows USD (incorrect)")
        self.stdout.write(f"   - Frontend already uses base_currency")
        self.stdout.write(f"   - This fix aligns backend with frontend")

    def create_search_replace_script(self):
        """Create a script to help with find/replace operations"""
        script_content = '''
# Search and replace patterns for fixing currency usage:

# Pattern 1: portfolio.currency → portfolio.base_currency
find: portfolio.currency
replace: portfolio.base_currency

# Pattern 2: portfolio_currency = portfolio.currency
find: portfolio_currency = portfolio.currency
replace: portfolio_currency = portfolio.base_currency or portfolio.currency

# Pattern 3: cash_currency = portfolio.cash_account.currency or portfolio.currency  
find: cash_currency = portfolio.cash_account.currency or portfolio.currency
replace: cash_currency = portfolio.cash_account.currency or portfolio.base_currency

# Files to check:
- backend/portfolio/services/currency_service.py
- backend/portfolio/models.py  
- backend/portfolio/views.py
- backend/portfolio/serializers.py
- backend/portfolio/tasks.py
'''

        self.stdout.write(f"\n📋 Search/Replace Patterns:")
        self.stdout.write(script_content)