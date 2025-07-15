# backend/portfolio/management/commands/manage_portfolio_history_service.py
"""
Enhanced Portfolio History Management Command for Phase 3

This command provides comprehensive management of the portfolio history service,
including daily calculations, backfill operations, gap detection, and performance
analysis.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import logging
import sys

from portfolio.models import Portfolio, PortfolioValueHistory, Transaction
from portfolio.services.portfolio_history_service import PortfolioHistoryService
from portfolio.tasks import (
    calculate_daily_portfolio_snapshots,
    backfill_portfolio_history_task,
    bulk_portfolio_backfill_task,
    detect_and_fill_portfolio_gaps_task,
    validate_portfolio_history_task,
    generate_portfolio_performance_report,
    test_portfolio_history_service
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage portfolio history service operations'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Daily snapshot command
        daily_parser = subparsers.add_parser('daily', help='Calculate daily portfolio snapshots')
        daily_parser.add_argument('--date', type=str, help='Date for snapshots (YYYY-MM-DD), defaults to today')
        daily_parser.add_argument('--portfolio-id', type=int, help='Process specific portfolio only')
        daily_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Backfill command
        backfill_parser = subparsers.add_parser('backfill', help='Backfill historical portfolio data')
        backfill_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID to backfill')
        backfill_parser.add_argument('--portfolio-name', type=str, help='Portfolio name to backfill')
        backfill_parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
        backfill_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), defaults to today')
        backfill_parser.add_argument('--days', type=int, help='Days back from today (alternative to start-date)')
        backfill_parser.add_argument('--force', action='store_true', help='Force update existing data')
        backfill_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Bulk backfill command
        bulk_parser = subparsers.add_parser('bulk-backfill', help='Bulk backfill all portfolios')
        bulk_parser.add_argument('--days', type=int, default=30, help='Days back to backfill (default: 30)')
        bulk_parser.add_argument('--force', action='store_true', help='Force update existing data')
        bulk_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Gap detection command
        gaps_parser = subparsers.add_parser('gaps', help='Detect and fill gaps in portfolio history')
        gaps_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID to check')
        gaps_parser.add_argument('--portfolio-name', type=str, help='Portfolio name to check')
        gaps_parser.add_argument('--fill', action='store_true', help='Fill detected gaps')
        gaps_parser.add_argument('--max-gap-days', type=int, default=30, help='Maximum gap size to fill (default: 30)')
        gaps_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Validation command
        validate_parser = subparsers.add_parser('validate', help='Validate portfolio history data')
        validate_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID to validate')
        validate_parser.add_argument('--portfolio-name', type=str, help='Portfolio name to validate')
        validate_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Performance report command
        performance_parser = subparsers.add_parser('performance', help='Generate portfolio performance report')
        performance_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID for report')
        performance_parser.add_argument('--portfolio-name', type=str, help='Portfolio name for report')
        performance_parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
        performance_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), defaults to today')
        performance_parser.add_argument('--days', type=int, help='Days back from today (alternative to start-date)')
        performance_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Output format')
        performance_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Statistics command
        stats_parser = subparsers.add_parser('stats', help='Show portfolio history statistics')
        stats_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID for stats')
        stats_parser.add_argument('--portfolio-name', type=str, help='Portfolio name for stats')

        # List command
        list_parser = subparsers.add_parser('list', help='List portfolio history records')
        list_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID to list')
        list_parser.add_argument('--portfolio-name', type=str, help='Portfolio name to list')
        list_parser.add_argument('--limit', type=int, default=10, help='Number of records to show (default: 10)')
        list_parser.add_argument('--start-date', type=str, help='Start date filter (YYYY-MM-DD)')
        list_parser.add_argument('--end-date', type=str, help='End date filter (YYYY-MM-DD)')

        # Test command
        test_parser = subparsers.add_parser('test', help='Test portfolio history service')
        test_parser.add_argument('--async', action='store_true', help='Run as Celery task')

        # Cleanup command
        cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old portfolio snapshots')
        cleanup_parser.add_argument('--retention-days', type=int, default=365, help='Days to retain (default: 365)')
        cleanup_parser.add_argument('--dry-run', action='store_true',
                                    help='Show what would be deleted without deleting')

    def handle(self, *args, **options):
        action = options.get('action')

        if not action:
            self.print_help()
            return

        # Map actions to methods
        action_map = {
            'daily': self.handle_daily,
            'backfill': self.handle_backfill,
            'bulk-backfill': self.handle_bulk_backfill,
            'gaps': self.handle_gaps,
            'validate': self.handle_validate,
            'performance': self.handle_performance,
            'stats': self.handle_stats,
            'list': self.handle_list,
            'test': self.handle_test,
            'cleanup': self.handle_cleanup
        }

        if action in action_map:
            action_map[action](options)
        else:
            raise CommandError(f"Unknown action: {action}")

    def print_help(self):
        self.stdout.write(
            self.style.SUCCESS("Portfolio History Service Management Commands\n")
        )
        self.stdout.write("Available actions:")
        self.stdout.write("  daily           - Calculate daily portfolio snapshots")
        self.stdout.write("  backfill        - Backfill historical portfolio data")
        self.stdout.write("  bulk-backfill   - Bulk backfill all portfolios")
        self.stdout.write("  gaps            - Detect and fill gaps in portfolio history")
        self.stdout.write("  validate        - Validate portfolio history data")
        self.stdout.write("  performance     - Generate portfolio performance report")
        self.stdout.write("  stats           - Show portfolio history statistics")
        self.stdout.write("  list            - List portfolio history records")
        self.stdout.write("  test            - Test portfolio history service")
        self.stdout.write("  cleanup         - Cleanup old portfolio snapshots")
        self.stdout.write("\nUse --help with any action for detailed options.")

    def get_portfolio(self, portfolio_id=None, portfolio_name=None):
        """Get portfolio by ID or name"""
        if portfolio_id:
            try:
                return Portfolio.objects.get(id=portfolio_id)
            except Portfolio.DoesNotExist:
                raise CommandError(f"Portfolio with ID {portfolio_id} not found")
        elif portfolio_name:
            try:
                return Portfolio.objects.get(name=portfolio_name)
            except Portfolio.DoesNotExist:
                raise CommandError(f"Portfolio with name '{portfolio_name}' not found")
        else:
            return None

    def handle_daily(self, options):
        """Handle daily snapshot calculation"""
        target_date = options.get('date')
        portfolio_id = options.get('portfolio_id')
        run_async = options.get('async', False)

        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
            except ValueError:
                raise CommandError(f"Invalid date format: {target_date}. Use YYYY-MM-DD")
        else:
            parsed_date = date.today()

        self.stdout.write(
            self.style.SUCCESS(f"Calculating daily portfolio snapshots for {parsed_date}...")
        )

        if run_async:
            task = calculate_daily_portfolio_snapshots.delay(target_date)
            self.stdout.write(f"Task started: {task.id}")
            return

        if portfolio_id:
            # Process single portfolio
            portfolio = self.get_portfolio(portfolio_id=portfolio_id)
            result = PortfolioHistoryService.save_daily_snapshot(
                portfolio, parsed_date, 'manual'
            )

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Snapshot created for {portfolio.name}: "
                                       f"${result['calculation_result']['total_value']:,.2f}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to create snapshot for {portfolio.name}: "
                                     f"{result['error']}")
                )
        else:
            # Process all portfolios
            result = PortfolioHistoryService.calculate_daily_snapshots(parsed_date)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Daily snapshots complete: "
                                       f"{result['successful_snapshots']}/{result['total_portfolios']} successful")
                )

                # Show details
                for detail in result['details']:
                    status = "✅" if detail['success'] else "❌"
                    self.stdout.write(f"  {status} {detail['portfolio_name']}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Daily snapshots failed: {result['error']}")
                )

    def handle_backfill(self, options):
        """Handle portfolio backfill"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        days = options.get('days')
        force = options.get('force', False)
        run_async = options.get('async', False)

        # Get portfolio
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)
        if not portfolio:
            raise CommandError("Must specify either --portfolio-id or --portfolio-name")

        # Parse dates
        if days:
            parsed_end = date.today()
            parsed_start = parsed_end - timedelta(days=days)
        else:
            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date) if end_date else date.today()
            except ValueError as e:
                raise CommandError(f"Invalid date format: {e}")

        self.stdout.write(
            self.style.SUCCESS(f"Backfilling {portfolio.name} from {parsed_start} to {parsed_end}...")
        )

        if run_async:
            task = backfill_portfolio_history_task.delay(
                portfolio.id, parsed_start.isoformat(), parsed_end.isoformat(), force
            )
            self.stdout.write(f"Task started: {task.id}")
            return

        # Run synchronously
        result = PortfolioHistoryService.backfill_portfolio_history(
            portfolio, parsed_start, parsed_end, force
        )

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Backfill complete for {portfolio.name}: "
                                   f"{result['successful_snapshots']}/{result['total_dates']} snapshots created")
            )

            if result['skipped_snapshots'] > 0:
                self.stdout.write(f"  📝 {result['skipped_snapshots']} snapshots skipped (already exist)")

            if result['failed_snapshots'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠️  {result['failed_snapshots']} snapshots failed")
                )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Backfill failed for {portfolio.name}: {result['error']}")
            )

    def handle_bulk_backfill(self, options):
        """Handle bulk backfill for all portfolios"""
        days = options.get('days', 30)
        force = options.get('force', False)
        run_async = options.get('async', False)

        self.stdout.write(
            self.style.SUCCESS(f"Starting bulk backfill for all portfolios ({days} days back)...")
        )

        if run_async:
            task = bulk_portfolio_backfill_task.delay(days, force)
            self.stdout.write(f"Task started: {task.id}")
            return

        # Get all active portfolios
        portfolios = Portfolio.objects.filter(is_active=True)

        if not portfolios.exists():
            self.stdout.write(self.style.WARNING("No active portfolios found"))
            return

        # Run bulk processing
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        result = PortfolioHistoryService.bulk_portfolio_processing(
            list(portfolios), 'backfill',
            start_date=start_date, end_date=end_date, force_update=force
        )

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Bulk backfill complete: "
                                   f"{result['successful_operations']}/{result['total_portfolios']} portfolios processed")
            )

            # Show details
            for detail in result['details']:
                status = "✅" if detail['success'] else "❌"
                error_msg = f" - {detail['error']}" if detail.get('error') else ""
                self.stdout.write(f"  {status} {detail['portfolio_name']}{error_msg}")
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Bulk backfill failed: {result['error']}")
            )

    def handle_gaps(self, options):
        """Handle gap detection and filling"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')
        fill_gaps = options.get('fill', False)
        max_gap_days = options.get('max_gap_days', 30)
        run_async = options.get('async', False)

        if run_async:
            task = detect_and_fill_portfolio_gaps_task.delay(
                portfolio_id, max_gap_days
            )
            self.stdout.write(f"Task started: {task.id}")
            return

        # Get portfolio or process all
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)

        if portfolio:
            self.stdout.write(
                self.style.SUCCESS(f"Checking gaps for {portfolio.name}...")
            )

            # Get gaps
            gap_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)

            if gap_result['success']:
                if gap_result['total_missing'] == 0:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ No gaps found for {portfolio.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Found {gap_result['total_missing']} missing dates "
                                           f"({gap_result['coverage_percentage']:.1f}% coverage)")
                    )

                    # Show some missing dates
                    missing_dates = gap_result['missing_dates'][:10]
                    for missing_date in missing_dates:
                        self.stdout.write(f"  📅 Missing: {missing_date}")

                    if len(gap_result['missing_dates']) > 10:
                        self.stdout.write(f"  ... and {len(gap_result['missing_dates']) - 10} more")

                    # Fill gaps if requested
                    if fill_gaps:
                        self.stdout.write("Filling gaps...")
                        fill_result = PortfolioHistoryService.backfill_portfolio_history(
                            portfolio,
                            min(gap_result['missing_dates']),
                            max(gap_result['missing_dates']),
                            force_update=False
                        )

                        if fill_result['success']:
                            self.stdout.write(
                                self.style.SUCCESS(f"✅ Filled {fill_result['successful_snapshots']} gaps")
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"❌ Gap filling failed: {fill_result['error']}")
                            )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Gap detection failed: {gap_result['error']}")
                )
        else:
            # Process all portfolios
            self.stdout.write(
                self.style.SUCCESS("Checking gaps for all portfolios...")
            )

            portfolios = Portfolio.objects.filter(is_active=True)

            for portfolio in portfolios:
                gap_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)

                if gap_result['success']:
                    if gap_result['total_missing'] == 0:
                        self.stdout.write(f"✅ {portfolio.name}: No gaps")
                    else:
                        self.stdout.write(
                            f"⚠️  {portfolio.name}: {gap_result['total_missing']} missing dates "
                            f"({gap_result['coverage_percentage']:.1f}% coverage)"
                        )
                else:
                    self.stdout.write(f"❌ {portfolio.name}: Gap detection failed")

    def handle_validate(self, options):
        """Handle portfolio history validation"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')
        run_async = options.get('async', False)

        if run_async:
            task = validate_portfolio_history_task.delay(portfolio_id)
            self.stdout.write(f"Task started: {task.id}")
            return

        # Get portfolio or process all
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)

        if portfolio:
            portfolios = [portfolio]
            self.stdout.write(
                self.style.SUCCESS(f"Validating {portfolio.name}...")
            )
        else:
            portfolios = Portfolio.objects.filter(is_active=True)
            self.stdout.write(
                self.style.SUCCESS("Validating all portfolios...")
            )

        for portfolio in portfolios:
            # Check basic metrics
            history_count = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).count()

            if history_count == 0:
                self.stdout.write(f"❌ {portfolio.name}: No historical data")
                continue

            # Check for gaps
            gap_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)

            # Check latest snapshot
            latest_snapshot = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).order_by('-date').first()

            issues = []

            if gap_result['success'] and gap_result['total_missing'] > 0:
                issues.append(f"{gap_result['total_missing']} missing dates")

            if latest_snapshot and latest_snapshot.date < date.today() - timedelta(days=7):
                issues.append(f"Latest snapshot is {latest_snapshot.date} (over 7 days old)")

            # Check for negative values
            negative_values = PortfolioValueHistory.objects.filter(
                portfolio=portfolio,
                total_value__lt=0
            ).count()

            if negative_values > 0:
                issues.append(f"{negative_values} negative values")

            if issues:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {portfolio.name}: {', '.join(issues)}")
                )
            else:
                self.stdout.write(f"✅ {portfolio.name}: Valid ({history_count} records)")

    def handle_performance(self, options):
        """Handle performance report generation"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        days = options.get('days')
        output_format = options.get('format', 'table')
        run_async = options.get('async', False)

        # Get portfolio
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)
        if not portfolio:
            raise CommandError("Must specify either --portfolio-id or --portfolio-name")

        # Parse dates
        if days:
            parsed_end = date.today()
            parsed_start = parsed_end - timedelta(days=days)
        else:
            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date) if end_date else date.today()
            except ValueError as e:
                raise CommandError(f"Invalid date format: {e}")

        if run_async:
            task = generate_portfolio_performance_report.delay(
                portfolio.id, parsed_start.isoformat(), parsed_end.isoformat()
            )
            self.stdout.write(f"Task started: {task.id}")
            return

        # Generate performance report
        self.stdout.write(
            self.style.SUCCESS(f"Generating performance report for {portfolio.name}...")
        )

        result = PortfolioHistoryService.get_portfolio_performance(
            portfolio, parsed_start, parsed_end
        )

        if not result['success']:
            self.stdout.write(
                self.style.ERROR(f"❌ Performance report failed: {result['error']}")
            )
            return

        # Display results
        if output_format == 'json':
            import json
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            # Table format
            summary = result['performance_summary']

            self.stdout.write(f"\n📊 Performance Report for {portfolio.name}")
            self.stdout.write(f"📅 Period: {parsed_start} to {parsed_end}")
            self.stdout.write(f"📈 Total Days: {summary['total_days']}")
            self.stdout.write("-" * 50)

            self.stdout.write(f"💰 Start Value: ${summary['start_value']:,.2f}")
            self.stdout.write(f"💰 End Value: ${summary['end_value']:,.2f}")
            self.stdout.write(f"📊 Total Return: {summary['total_return_pct']:.2f}%")
            self.stdout.write(f"💸 Unrealized Gains: ${summary['unrealized_gains']:,.2f}")
            self.stdout.write(f"💵 Cash Balance: ${summary['cash_balance']:,.2f}")
            self.stdout.write(f"📈 Best Day: {summary['best_day']:.2f}%")
            self.stdout.write(f"📉 Worst Day: {summary['worst_day']:.2f}%")
            self.stdout.write(f"📊 Volatility: {summary['volatility']:.2f}%")

            # Show recent data points
            chart_data = result['chart_data']
            if chart_data:
                self.stdout.write(f"\n📈 Recent Performance (last 5 days):")
                for data_point in chart_data[-5:]:
                    self.stdout.write(
                        f"  {data_point['date']}: ${data_point['total_value']:,.2f} "
                        f"({data_point['total_return_pct']:.2f}%)"
                    )

    def handle_stats(self, options):
        """Handle portfolio statistics"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')

        # Get portfolio or show all
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)

        if portfolio:
            portfolios = [portfolio]
        else:
            portfolios = Portfolio.objects.filter(is_active=True)

        self.stdout.write(
            self.style.SUCCESS("📊 Portfolio History Statistics")
        )
        self.stdout.write("=" * 60)

        for portfolio in portfolios:
            # Get basic stats
            history_count = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).count()

            if history_count == 0:
                self.stdout.write(f"❌ {portfolio.name}: No historical data")
                continue

            # Get date range
            oldest = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).order_by('date').first()

            newest = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).order_by('-date').first()

            # Get latest value
            latest_value = newest.total_value if newest else Decimal('0')

            # Get gaps
            gap_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)

            self.stdout.write(f"\n📈 {portfolio.name}")
            self.stdout.write(f"  📅 Date Range: {oldest.date} to {newest.date}")
            self.stdout.write(f"  📊 Total Records: {history_count}")
            self.stdout.write(f"  💰 Latest Value: ${latest_value:,.2f}")
            self.stdout.write(f"  📊 Coverage: {gap_result.get('coverage_percentage', 0):.1f}%")
            self.stdout.write(f"  ⚠️  Missing Dates: {gap_result.get('total_missing', 0)}")

    def handle_list(self, options):
        """Handle portfolio history listing"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')
        limit = options.get('limit', 10)
        start_date = options.get('start_date')
        end_date = options.get('end_date')

        # Get portfolio
        portfolio = self.get_portfolio(portfolio_id, portfolio_name)
        if not portfolio:
            raise CommandError("Must specify either --portfolio-id or --portfolio-name")

        # Build query
        query = PortfolioValueHistory.objects.filter(portfolio=portfolio)

        if start_date:
            try:
                query = query.filter(date__gte=date.fromisoformat(start_date))
            except ValueError:
                raise CommandError(f"Invalid start date format: {start_date}")

        if end_date:
            try:
                query = query.filter(date__lte=date.fromisoformat(end_date))
            except ValueError:
                raise CommandError(f"Invalid end date format: {end_date}")

        # Get records
        records = query.order_by('-date')[:limit]

        if not records:
            self.stdout.write(f"No records found for {portfolio.name}")
            return

        self.stdout.write(
            self.style.SUCCESS(f"📈 Portfolio History for {portfolio.name}")
        )
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"{'Date':<12} {'Value':<15} {'Cost':<15} {'Gain/Loss':<15} {'Return %':<10}"
        )
        self.stdout.write("-" * 80)

        for record in records:
            gain_loss = record.total_value - record.total_cost
            self.stdout.write(
                f"{record.date:<12} ${record.total_value:<14,.2f} "
                f"${record.total_cost:<14,.2f} ${gain_loss:<14,.2f} "
                f"{record.total_return_pct:<9.2f}%"
            )

    def handle_test(self, options):
        """Handle service testing"""
        run_async = options.get('async', False)

        if run_async:
            task = test_portfolio_history_service.delay()
            self.stdout.write(f"Task started: {task.id}")
            return

        self.stdout.write(
            self.style.SUCCESS("🧪 Testing Portfolio History Service...")
        )

        # Test with first active portfolio
        portfolio = Portfolio.objects.filter(is_active=True).first()

        if not portfolio:
            self.stdout.write(
                self.style.ERROR("❌ No active portfolios found for testing")
            )
            return

        # Test daily snapshot
        result = PortfolioHistoryService.save_daily_snapshot(
            portfolio, date.today(), 'test'
        )

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Test successful with {portfolio.name}")
            )
            self.stdout.write(f"  💰 Portfolio Value: ${result['calculation_result']['total_value']:,.2f}")
            self.stdout.write(f"  📊 Holdings Count: {result['calculation_result']['holdings_count']}")
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Test failed: {result['error']}")
            )

    def handle_cleanup(self, options):
        """Handle cleanup of old snapshots"""
        retention_days = options.get('retention_days', 365)
        dry_run = options.get('dry_run', False)

        cutoff_date = date.today() - timedelta(days=retention_days)

        # Count records to be deleted
        old_records = PortfolioValueHistory.objects.filter(
            date__lt=cutoff_date
        )

        record_count = old_records.count()

        if record_count == 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ No old records to cleanup (older than {cutoff_date})")
            )
            return

        self.stdout.write(
            self.style.WARNING(f"Found {record_count} records older than {cutoff_date}")
        )

        if dry_run:
            self.stdout.write("🔍 DRY RUN - No records will be deleted")

            # Show breakdown by portfolio
            from django.db.models import Count
            portfolio_counts = old_records.values('portfolio__name').annotate(
                count=Count('id')
            ).order_by('-count')

            self.stdout.write("\n📊 Records by portfolio:")
            for item in portfolio_counts:
                self.stdout.write(f"  {item['portfolio__name']}: {item['count']} records")
        else:
            # Confirm deletion
            confirm = input(f"Delete {record_count} old records? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Operation cancelled")
                return

            # Delete records
            deleted_count, _ = old_records.delete()

            self.stdout.write(
                self.style.SUCCESS(f"✅ Deleted {deleted_count} old portfolio snapshots")
            )