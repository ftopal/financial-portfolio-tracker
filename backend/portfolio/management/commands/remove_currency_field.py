# backend/portfolio/management/commands/remove_currency_field.py

from django.core.management.base import BaseCommand
from django.db import transaction
from portfolio.models import Portfolio
import os
import re


class Command(BaseCommand):
    help = 'Remove portfolio.currency field and update all references to use base_currency'

    def add_arguments(self, parser):
        parser.add_argument(
            '--step',
            type=str,
            choices=['1', '2', '3', '4', 'all'],
            default='1',
            help='Which step to execute (1=analyze, 2=fix-code, 3=create-migration, 4=apply-migration, all=everything)'
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Actually execute the changes (default: dry run)'
        )

    def handle(self, *args, **options):
        step = options['step']
        execute = options['execute']

        if not execute and step != '1':
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - Use --execute to apply changes")
            )

        self.stdout.write(
            self.style.SUCCESS("🔧 Portfolio Currency Field Removal Plan")
        )
        self.stdout.write("=" * 80)

        if step == '1' or step == 'all':
            self.step1_analyze_usage()

        if step == '2' or step == 'all':
            self.step2_fix_code_references(execute)

        if step == '3' or step == 'all':
            self.step3_create_migration(execute)

        if step == '4' or step == 'all':
            self.step4_apply_migration()

    def step1_analyze_usage(self):
        """Step 1: Analyze all portfolio.currency usage"""
        self.stdout.write(f"\n📊 STEP 1: Analyzing portfolio.currency usage")
        self.stdout.write("-" * 50)

        files_to_check = [
            'backend/portfolio/models.py',
            'backend/portfolio/views.py',
            'backend/portfolio/services/currency_service.py',
            'backend/portfolio/serializers.py',
            'backend/portfolio/admin.py',
            'backend/portfolio/tasks.py',
            'backend/portfolio/services/portfolio_history_service.py',
        ]

        total_references = 0

        for file_path in files_to_check:
            if os.path.exists(file_path):
                references = self.find_currency_references(file_path)
                if references:
                    self.stdout.write(f"\n📁 {file_path}:")
                    for line_num, line in references:
                        self.stdout.write(f"   Line {line_num}: {line.strip()}")
                        total_references += 1
                else:
                    self.stdout.write(f"\n✅ {file_path}: No portfolio.currency references")

        self.stdout.write(f"\n📊 Total references found: {total_references}")

    def find_currency_references(self, file_path):
        """Find all portfolio.currency references in a file"""
        references = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Look for portfolio.currency but not portfolio.base_currency
                if 'portfolio.currency' in line and 'portfolio.base_currency' not in line:
                    references.append((line_num, line))
                elif 'portfolio_currency = portfolio.currency' in line:
                    references.append((line_num, line))
                elif 'cash_currency = portfolio.cash_account.currency or portfolio.currency' in line:
                    references.append((line_num, line))
        except Exception as e:
            self.stdout.write(f"Error reading {file_path}: {e}")

        return references

    def step2_fix_code_references(self, execute):
        """Step 2: Fix all code references"""
        self.stdout.write(f"\n🔧 STEP 2: Fixing code references")
        self.stdout.write("-" * 50)

        replacements = [
            {
                'file': 'backend/portfolio/models.py',
                'changes': [
                    {
                        'old': 'portfolio_currency = self.base_currency or self.currency',
                        'new': 'portfolio_currency = self.base_currency'
                    },
                    {
                        'old': 'currency=self.base_currency or self.currency',
                        'new': 'currency=self.base_currency'
                    }
                ]
            },
            {
                'file': 'backend/portfolio/services/currency_service.py',
                'changes': [
                    {
                        'old': 'cash_currency = portfolio.cash_account.currency or portfolio.currency',
                        'new': 'cash_currency = portfolio.cash_account.currency or portfolio.base_currency'
                    }
                ]
            },
            {
                'file': 'backend/portfolio/views.py',
                'changes': [
                    {
                        'old': "'base_currency': portfolio.currency,",
                        'new': "'base_currency': portfolio.base_currency,"
                    }
                ]
            }
        ]

        for file_info in replacements:
            file_path = file_info['file']
            changes = file_info['changes']

            if not os.path.exists(file_path):
                self.stdout.write(f"❌ File not found: {file_path}")
                continue

            self.stdout.write(f"\n📁 Processing {file_path}:")

            if execute:
                self.apply_file_changes(file_path, changes)
            else:
                self.preview_file_changes(file_path, changes)

    def apply_file_changes(self, file_path, changes):
        """Apply changes to a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            changes_made = 0

            for change in changes:
                old_text = change['old']
                new_text = change['new']

                if old_text in content:
                    content = content.replace(old_text, new_text)
                    changes_made += 1
                    self.stdout.write(f"   ✅ Applied: {old_text[:50]}... → {new_text[:50]}...")
                else:
                    self.stdout.write(f"   ⚠️  Not found: {old_text[:50]}...")

            if changes_made > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.stdout.write(f"   💾 Saved {changes_made} changes to {file_path}")
            else:
                self.stdout.write(f"   ℹ️  No changes needed for {file_path}")

        except Exception as e:
            self.stdout.write(f"   ❌ Error processing {file_path}: {e}")

    def preview_file_changes(self, file_path, changes):
        """Preview what changes would be made"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for change in changes:
                old_text = change['old']
                new_text = change['new']

                if old_text in content:
                    self.stdout.write(f"   📝 Would change: {old_text[:50]}...")
                    self.stdout.write(f"                    → {new_text[:50]}...")
                else:
                    self.stdout.write(f"   ⚠️  Not found: {old_text[:50]}...")

        except Exception as e:
            self.stdout.write(f"   ❌ Error reading {file_path}: {e}")

    def step3_create_migration(self, execute):
        """Step 3: Create Django migration to remove currency field"""
        self.stdout.write(f"\n📋 STEP 3: Creating migration to remove currency field")
        self.stdout.write("-" * 50)

        migration_content = '''# Generated by remove_currency_field command

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0002_portfoliovaluehistory'),  # Adjust this to your latest migration
    ]

    operations = [
        migrations.RemoveField(
            model_name='portfolio',
            name='currency',
        ),
    ]
'''

        if execute:
            # Find the next migration number
            migration_dir = 'backend/portfolio/migrations'
            if os.path.exists(migration_dir):
                existing_migrations = [f for f in os.listdir(migration_dir) if f.startswith('0') and f.endswith('.py')]
                if existing_migrations:
                    latest_num = max([int(f[:4]) for f in existing_migrations])
                    next_num = f"{latest_num + 1:04d}"
                else:
                    next_num = "0003"

                migration_file = f"{migration_dir}/{next_num}_remove_portfolio_currency.py"

                with open(migration_file, 'w') as f:
                    f.write(migration_content)

                self.stdout.write(f"✅ Created migration: {migration_file}")
            else:
                self.stdout.write(f"❌ Migration directory not found: {migration_dir}")
        else:
            self.stdout.write(f"📝 Would create migration with content:")
            self.stdout.write(migration_content)

    def step4_apply_migration(self):
        """Step 4: Apply the migration"""
        self.stdout.write(f"\n🚀 STEP 4: Apply migration")
        self.stdout.write("-" * 50)

        self.stdout.write(f"To apply the migration, run:")
        self.stdout.write(f"   python manage.py makemigrations")
        self.stdout.write(f"   python manage.py migrate")

        self.stdout.write(f"\n⚠️  IMPORTANT: Before applying migration:")
        self.stdout.write(f"   1. Test all code changes thoroughly")
        self.stdout.write(f"   2. Backup your database")
        self.stdout.write(f"   3. Verify all portfolio.currency references are fixed")
        self.stdout.write(f"   4. Run your test suite")

    def show_final_summary(self):
        """Show final summary and next steps"""
        self.stdout.write(f"\n🎯 REMOVAL PLAN SUMMARY")
        self.stdout.write("=" * 50)

        self.stdout.write(f"\n✅ What will be removed:")
        self.stdout.write(f"   - Portfolio.currency field from model")
        self.stdout.write(f"   - All references updated to use base_currency")

        self.stdout.write(f"\n✅ What will remain:")
        self.stdout.write(f"   - Portfolio.base_currency (renamed to primary currency)")
        self.stdout.write(f"   - All existing functionality preserved")

        self.stdout.write(f"\n📋 Execution order:")
        self.stdout.write(f"   1. python manage.py remove_currency_field --step=1")
        self.stdout.write(f"   2. python manage.py remove_currency_field --step=2 --execute")
        self.stdout.write(f"   3. Test thoroughly")
        self.stdout.write(f"   4. python manage.py remove_currency_field --step=3 --execute")
        self.stdout.write(f"   5. python manage.py migrate")

        self.stdout.write(f"\n⚠️  Safety checklist:")
        self.stdout.write(f"   □ All tests pass")
        self.stdout.write(f"   □ Currency conversion still works")
        self.stdout.write(f"   □ Portfolio calculations correct")
        self.stdout.write(f"   □ Database backup created")