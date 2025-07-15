# Create this file as: backend/portfolio/management/commands/manage_portfolio_history.py

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import date, datetime, timedelta
from portfolio.models import Portfolio, PortfolioValueHistory
from portfolio.services.price_history_service import PriceHistoryService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage portfolio value history snapshots'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Create snapshot command
        create_parser = subparsers.add_parser('create', help='Create portfolio value snapshot')
        create_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID')
        create_parser.add_argument('--portfolio-name', help='Portfolio name')
        create_parser.add_argument('--date', help='Date for snapshot (YYYY-MM-DD), defaults to today')
        create_parser.add_argument('--source', default='manual_calc',
                                   choices=['daily_task', 'manual_calc', 'backfill', 'transaction_trigger'],
                                   help='Calculation source')

        # Backfill command
        backfill_parser = subparsers.add_parser('backfill', help='Backfill portfolio value history')
        backfill_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID')
        backfill_parser.add_argument('--portfolio-name', help='Portfolio name')
        backfill_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
        backfill_parser.add_argument('--end-date', help='End date (YYYY-MM-DD), defaults to today')
        backfill_parser.add_argument('--days', type=int, help='Number of days back from today')

        # List command
        list_parser = subparsers.add_parser('list', help='List portfolio value history')
        list_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID')
        list_parser.add_argument('--portfolio-name', help='Portfolio name')
        list_parser.add_argument('--limit', type=int, default=10, help='Number of records to show')

        # Stats command
        stats_parser = subparsers.add_parser('stats', help='Show portfolio value statistics')
        stats_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID')
        stats_parser.add_argument('--portfolio-name', help='Portfolio name')

        # Delete command
        delete_parser = subparsers.add_parser('delete', help='Delete portfolio value history')
        delete_parser.add_argument('--portfolio-id', type=int, help='Portfolio ID')
        delete_parser.add_argument('--portfolio-name', help='Portfolio name')
        delete_parser.add_argument('--date', help='Specific date to delete (YYYY-MM-DD)')
        delete_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')

    def handle(self, *args, **options):
        action = options['action']

        if not action:
            self.print_help('manage.py', 'manage_portfolio_history')
            return

        if action == 'create':
            self.handle_create(options)
        elif action == 'backfill':
            self.handle_backfill(options)
        elif action == 'list':
            self.handle_list(options)
        elif action == 'stats':
            self.handle_stats(options)
        elif action == 'delete':
            self.handle_delete(options)
        else:
            raise CommandError(f'Unknown action: {action}')

    def get_portfolio(self, options):
        """Get portfolio from options"""
        portfolio_id = options.get('portfolio_id')
        portfolio_name = options.get('portfolio_name')

        if not portfolio_id and not portfolio_name:
            raise CommandError('Either --portfolio-id or --portfolio-name is required')

        try:
            if portfolio_id:
                return Portfolio.objects.get(id=portfolio_id)
            else:
                return Portfolio.objects.get(name__iexact=portfolio_name)
        except Portfolio.DoesNotExist:
            raise CommandError(f'Portfolio not found')

    def handle_create(self, options):
        """Create a portfolio value snapshot"""
        portfolio = self.get_portfolio(options)

        # Parse date
        target_date = date.today()
        if options.get('date'):
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')

        source = options.get('source', 'manual_calc')

        self.stdout.write(f'Creating portfolio value snapshot for {portfolio.name} on {target_date}...')

        try:
            # Create snapshot
            snapshot = PortfolioValueHistory.create_snapshot(
                portfolio=portfolio,
                target_date=target_date,
                calculation_source=source
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Success! Created snapshot for {portfolio.name} on {target_date}\n'
                    f'Total Value: ${snapshot.total_value:,.2f}\n'
                    f'Total Cost: ${snapshot.total_cost:,.2f}\n'
                    f'Cash Balance: ${snapshot.cash_balance:,.2f}\n'
                    f'Holdings Count: {snapshot.holdings_count}\n'
                    f'Unrealized Gains: ${snapshot.unrealized_gains:,.2f}\n'
                    f'Total Return: {snapshot.total_return_pct:.2f}%'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating snapshot: {str(e)}')
            )
            logger.error(f'Error creating portfolio snapshot: {str(e)}', exc_info=True)

    def handle_backfill(self, options):
        """Backfill portfolio value history"""
        portfolio = self.get_portfolio(options)

        # Determine date range
        if options.get('days'):
            end_date = date.today()
            start_date = end_date - timedelta(days=options['days'])
        else:
            if not options.get('start_date'):
                raise CommandError('Either --days or --start-date is required')

            try:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid start date format. Use YYYY-MM-DD')

            end_date = date.today()
            if options.get('end_date'):
                try:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid end date format. Use YYYY-MM-DD')

        self.stdout.write(f'Backfilling portfolio value history for {portfolio.name}...')
        self.stdout.write(f'Date range: {start_date} to {end_date}')

        # Create snapshots for each day
        current_date = start_date
        created_count = 0
        updated_count = 0

        while current_date <= end_date:
            try:
                # Skip weekends for now (can be adjusted based on needs)
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    # Check if snapshot already exists
                    existing = PortfolioValueHistory.objects.filter(
                        portfolio=portfolio,
                        date=current_date
                    ).first()

                    if existing:
                        updated_count += 1
                        action = "Updated"
                    else:
                        created_count += 1
                        action = "Created"

                    snapshot = PortfolioValueHistory.create_snapshot(
                        portfolio=portfolio,
                        target_date=current_date,
                        calculation_source='backfill'
                    )

                    self.stdout.write(
                        f'{action} snapshot for {current_date}: '
                        f'${snapshot.total_value:,.2f} ({snapshot.holdings_count} holdings)'
                    )

                current_date += timedelta(days=1)

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error processing {current_date}: {str(e)}')
                )
                current_date += timedelta(days=1)
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f'Backfill complete! Created: {created_count}, Updated: {updated_count}'
            )
        )

    def handle_list(self, options):
        """List portfolio value history"""
        portfolio = self.get_portfolio(options)
        limit = options.get('limit', 10)

        snapshots = PortfolioValueHistory.objects.filter(
            portfolio=portfolio
        ).order_by('-date')[:limit]

        if not snapshots:
            self.stdout.write('No portfolio value history found.')
            return

        self.stdout.write(f'Portfolio value history for {portfolio.name} (last {limit} records):')
        self.stdout.write('-' * 80)

        for snapshot in snapshots:
            self.stdout.write(
                f'{snapshot.date} | ${snapshot.total_value:>12,.2f} | '
                f'${snapshot.total_cost:>12,.2f} | '
                f'${snapshot.unrealized_gains:>12,.2f} | '
                f'{snapshot.total_return_pct:>8.2f}% | '
                f'{snapshot.holdings_count:>3} holdings | '
                f'{snapshot.calculation_source}'
            )

    def handle_stats(self, options):
        """Show portfolio value statistics"""
        portfolio = self.get_portfolio(options)

        snapshots = PortfolioValueHistory.objects.filter(portfolio=portfolio)

        if not snapshots.exists():
            self.stdout.write('No portfolio value history found.')
            return

        # Basic statistics
        total_records = snapshots.count()
        latest_snapshot = snapshots.order_by('-date').first()
        earliest_snapshot = snapshots.order_by('date').first()

        self.stdout.write(f'Portfolio Value History Statistics for {portfolio.name}:')
        self.stdout.write('=' * 60)

        self.stdout.write(f'Total Records: {total_records}')
        self.stdout.write(f'Date Range: {earliest_snapshot.date} to {latest_snapshot.date}')
        self.stdout.write('')

        # Latest values
        self.stdout.write('Latest Snapshot:')
        self.stdout.write(f'  Date: {latest_snapshot.date}')
        self.stdout.write(f'  Total Value: ${latest_snapshot.total_value:,.2f}')
        self.stdout.write(f'  Total Cost: ${latest_snapshot.total_cost:,.2f}')
        self.stdout.write(f'  Cash Balance: ${latest_snapshot.cash_balance:,.2f}')
        self.stdout.write(f'  Holdings Count: {latest_snapshot.holdings_count}')
        self.stdout.write(f'  Unrealized Gains: ${latest_snapshot.unrealized_gains:,.2f}')
        self.stdout.write(f'  Total Return: {latest_snapshot.total_return_pct:.2f}%')
        self.stdout.write('')

        # Performance statistics
        if total_records > 1:
            value_changes = []
            previous_value = None

            for snapshot in snapshots.order_by('date'):
                if previous_value is not None:
                    daily_change = float(snapshot.total_value - previous_value)
                    value_changes.append(daily_change)
                previous_value = snapshot.total_value

            if value_changes:
                avg_daily_change = sum(value_changes) / len(value_changes)
                max_daily_gain = max(value_changes)
                max_daily_loss = min(value_changes)

                self.stdout.write('Performance Statistics:')
                self.stdout.write(f'  Average Daily Change: ${avg_daily_change:,.2f}')
                self.stdout.write(f'  Largest Daily Gain: ${max_daily_gain:,.2f}')
                self.stdout.write(f'  Largest Daily Loss: ${max_daily_loss:,.2f}')
                self.stdout.write('')

        # Calculation source breakdown
        source_stats = {}
        for snapshot in snapshots:
            source = snapshot.calculation_source
            if source not in source_stats:
                source_stats[source] = 0
            source_stats[source] += 1

        self.stdout.write('Calculation Source Breakdown:')
        for source, count in source_stats.items():
            percentage = (count / total_records) * 100
            self.stdout.write(f'  {source}: {count} records ({percentage:.1f}%)')

    def handle_delete(self, options):
        """Delete portfolio value history"""
        portfolio = self.get_portfolio(options)

        if not options.get('confirm'):
            self.stdout.write(
                self.style.WARNING(
                    'This will delete portfolio value history records. '
                    'Add --confirm to proceed.'
                )
            )
            return

        if options.get('date'):
            # Delete specific date
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')

            deleted_count = PortfolioValueHistory.objects.filter(
                portfolio=portfolio,
                date=target_date
            ).delete()[0]

            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted_count} records for {portfolio.name} on {target_date}'
                )
            )
        else:
            # Delete all records for portfolio
            deleted_count = PortfolioValueHistory.objects.filter(
                portfolio=portfolio
            ).delete()[0]

            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted_count} records for {portfolio.name}'
                )
            )

    def print_help(self, prog_name, subcommand):
        """Print help message"""
        self.stdout.write(f'Usage: {prog_name} {subcommand} [action] [options]')
        self.stdout.write('')
        self.stdout.write('Available actions:')
        self.stdout.write('  create      Create a portfolio value snapshot')
        self.stdout.write('  backfill    Backfill portfolio value history')
        self.stdout.write('  list        List portfolio value history')
        self.stdout.write('  stats       Show portfolio value statistics')
        self.stdout.write('  delete      Delete portfolio value history')
        self.stdout.write('')
        self.stdout.write('Examples:')
        self.stdout.write('  Create snapshot for today:')
        self.stdout.write('    python manage.py manage_portfolio_history create --portfolio-name "My Portfolio"')
        self.stdout.write('')
        self.stdout.write('  Backfill last 30 days:')
        self.stdout.write(
            '    python manage.py manage_portfolio_history backfill --portfolio-name "My Portfolio" --days 30')
        self.stdout.write('')
        self.stdout.write('  List last 10 records:')
        self.stdout.write(
            '    python manage.py manage_portfolio_history list --portfolio-name "My Portfolio" --limit 10')
        self.stdout.write('')
        self.stdout.write('  Show statistics:')
        self.stdout.write('    python manage.py manage_portfolio_history stats --portfolio-name "My Portfolio"')