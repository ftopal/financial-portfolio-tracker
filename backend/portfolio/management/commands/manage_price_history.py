from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from portfolio.models import Security, PriceHistory
from portfolio.services.price_history_service import PriceHistoryService
from portfolio.tasks import (
    fetch_historical_prices_task,
    backfill_all_securities_task,
    detect_and_fill_price_gaps_task,
    validate_all_price_data_task
)
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage historical price data for securities'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['backfill', 'validate', 'gaps', 'fetch', 'stats', 'cleanup'],
            help='Action to perform'
        )

        parser.add_argument(
            '--symbol',
            type=str,
            help='Security symbol (for single security operations)'
        )

        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days to go back (default: 365)'
        )

        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD)'
        )

        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD)'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing data'
        )

        parser.add_argument(
            '--async',
            action='store_true',
            help='Run as async Celery task'
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Batch size for bulk operations (default: 10)'
        )

    def handle(self, *args, **options):
        action = options['action']

        try:
            if action == 'backfill':
                self.handle_backfill(options)
            elif action == 'validate':
                self.handle_validate(options)
            elif action == 'gaps':
                self.handle_gaps(options)
            elif action == 'fetch':
                self.handle_fetch(options)
            elif action == 'stats':
                self.handle_stats(options)
            elif action == 'cleanup':
                self.handle_cleanup(options)

        except Exception as e:
            raise CommandError(f'Error executing {action}: {str(e)}')

    def handle_backfill(self, options):
        """Handle backfill operations"""
        symbol = options.get('symbol')
        days = options.get('days', 365)
        force = options.get('force', False)
        use_async = options.get('async', False)
        batch_size = options.get('batch_size', 10)

        if symbol:
            # Backfill single security
            try:
                security = Security.objects.get(symbol__iexact=symbol)

                self.stdout.write(f'Backfilling {days} days of price data for {security.symbol}...')

                if use_async:
                    from portfolio.tasks import backfill_security_prices_task
                    task = backfill_security_prices_task.delay(security.id, days, force)
                    self.stdout.write(f'Task submitted: {task.id}')
                else:
                    result = PriceHistoryService.backfill_security_prices(security, days, force)
                    if result['success']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Success: {result["records_created"]} records created, '
                                f'{result["records_updated"]} updated'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'Failed: {result.get("error", "Unknown error")}')
                        )

            except Security.DoesNotExist:
                raise CommandError(f'Security with symbol {symbol} not found')
        else:
            # Backfill all securities
            self.stdout.write(f'Backfilling {days} days for all active securities...')

            if use_async:
                task = backfill_all_securities_task.delay(days, batch_size, force)
                self.stdout.write(f'Task submitted: {task.id}')
            else:
                # Run synchronously (not recommended for large datasets)
                securities = Security.objects.filter(is_active=True)
                total = securities.count()
                success_count = 0

                for i, security in enumerate(securities, 1):
                    self.stdout.write(f'Processing {security.symbol} ({i}/{total})...')
                    result = PriceHistoryService.backfill_security_prices(security, days, force)
                    if result['success']:
                        success_count += 1

                self.stdout.write(
                    self.style.SUCCESS(f'Completed: {success_count}/{total} securities processed')
                )

    def handle_validate(self, options):
        """Handle validation operations"""
        symbol = options.get('symbol')

        if symbol:
            # Validate single security
            try:
                security = Security.objects.get(symbol__iexact=symbol)
                result = PriceHistoryService.validate_price_data(security)

                self.stdout.write(f'Validation results for {security.symbol}:')
                self.stdout.write(f'  Valid: {result["valid"]}')
                self.stdout.write(f'  Total records: {result["total_records"]}')
                self.stdout.write(f'  Invalid prices: {result["invalid_prices"]}')
                self.stdout.write(f'  Recent records (30 days): {result["recent_records"]}')
                self.stdout.write(f'  Gaps detected: {result["gaps"]}')

                if result['date_range']['min_date']:
                    self.stdout.write(
                        f'  Date range: {result["date_range"]["min_date"].date()} to {result["date_range"]["max_date"].date()}')

            except Security.DoesNotExist:
                raise CommandError(f'Security with symbol {symbol} not found')
        else:
            # Validate all securities
            if options.get('async'):
                task = validate_all_price_data_task.delay()
                self.stdout.write(f'Validation task submitted: {task.id}')
            else:
                securities = Security.objects.filter(is_active=True)
                total = securities.count()
                valid_count = 0

                for security in securities:
                    result = PriceHistoryService.validate_price_data(security)
                    if result['valid']:
                        valid_count += 1

                self.stdout.write(
                    self.style.SUCCESS(f'Validation complete: {valid_count}/{total} securities have valid data')
                )

    def handle_gaps(self, options):
        """Handle gap detection and filling"""
        symbol = options.get('symbol')
        use_async = options.get('async', False)

        if symbol:
            try:
                security = Security.objects.get(symbol__iexact=symbol)

                # Detect gaps
                gaps = PriceHistoryService.detect_price_gaps(security)

                if gaps:
                    self.stdout.write(f'Found {len(gaps)} gaps in {security.symbol}:')
                    for gap in gaps:
                        self.stdout.write(f'  {gap["start_date"]} to {gap["end_date"]} ({gap["gap_days"]} days)')

                    # Fill gaps
                    self.stdout.write('Filling gaps...')
                    result = PriceHistoryService.fill_price_gaps(security)

                    if result['success']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Filled {result["gaps_filled"]} gaps, {result["records_created"]} records created')
                        )
                    else:
                        self.stdout.write(self.style.ERROR('Failed to fill gaps'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'No gaps found in {security.symbol}'))

            except Security.DoesNotExist:
                raise CommandError(f'Security with symbol {symbol} not found')
        else:
            # Process all securities
            if use_async:
                task = detect_and_fill_price_gaps_task.delay()
                self.stdout.write(f'Gap filling task submitted: {task.id}')
            else:
                securities = Security.objects.filter(is_active=True)
                total_gaps = 0

                for security in securities:
                    gaps = PriceHistoryService.detect_price_gaps(security)
                    if gaps:
                        total_gaps += len(gaps)
                        self.stdout.write(f'{security.symbol}: {len(gaps)} gaps')

                self.stdout.write(f'Total gaps found across all securities: {total_gaps}')

    def handle_fetch(self, options):
        """Handle specific date range fetching"""
        symbol = options.get('symbol')
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        force = options.get('force', False)

        if not symbol:
            raise CommandError('Symbol is required for fetch operation')

        if not start_date or not end_date:
            raise CommandError('Both start-date and end-date are required for fetch operation')

        try:
            security = Security.objects.get(symbol__iexact=symbol)
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()

            self.stdout.write(f'Fetching price data for {security.symbol} from {start} to {end}...')

            result = PriceHistoryService.bulk_fetch_historical_prices(security, start, end, force)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Success: {result["records_created"]} records created, '
                        f'{result["records_updated"]} updated'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed: {result.get("error", "Unknown error")}')
                )

        except Security.DoesNotExist:
            raise CommandError(f'Security with symbol {symbol} not found')
        except ValueError:
            raise CommandError('Invalid date format. Use YYYY-MM-DD')

    def handle_stats(self, options):
        """Show price history statistics"""
        # Overall statistics
        total_securities = Security.objects.filter(is_active=True).count()
        securities_with_prices = Security.objects.filter(
            is_active=True,
            price_history__isnull=False
        ).distinct().count()

        total_price_records = PriceHistory.objects.count()

        # Recent data statistics
        week_ago = timezone.now() - timedelta(days=7)
        recent_records = PriceHistory.objects.filter(date__gte=week_ago).count()

        self.stdout.write('Price History Statistics:')
        self.stdout.write(f'  Total active securities: {total_securities}')
        self.stdout.write(f'  Securities with price data: {securities_with_prices}')
        self.stdout.write(f'  Total price records: {total_price_records:,}')
        self.stdout.write(f'  Records from last 7 days: {recent_records:,}')

        if total_securities > 0:
            coverage = (securities_with_prices / total_securities) * 100
            self.stdout.write(f'  Coverage: {coverage:.1f}%')

    def handle_cleanup(self, options):
        """Clean up old price data"""
        days = options.get('days', 365)

        cutoff_date = timezone.now() - timedelta(days=days)

        # Count records to be deleted
        old_records = PriceHistory.objects.filter(date__lt=cutoff_date)
        count = old_records.count()

        if count == 0:
            self.stdout.write('No old records found to clean up')
            return

        self.stdout.write(f'Found {count:,} records older than {days} days ({cutoff_date.date()})')

        # Confirm deletion
        confirm = input('Are you sure you want to delete these records? (yes/no): ')

        if confirm.lower() == 'yes':
            deleted_count = old_records.delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f'Deleted {deleted_count:,} old price records')
            )
        else:
            self.stdout.write('Cleanup cancelled')


# Usage examples:
"""
# Backfill 1 year of data for AAPL
python manage.py manage_price_history backfill --symbol AAPL --days 365

# Backfill all securities (async)
python manage.py manage_price_history backfill --async --batch-size 5

# Validate specific security
python manage.py manage_price_history validate --symbol TSLA

# Find and fill gaps for all securities
python manage.py manage_price_history gaps --async

# Fetch specific date range
python manage.py manage_price_history fetch --symbol MSFT --start-date 2023-01-01 --end-date 2023-12-31

# Show statistics
python manage.py manage_price_history stats

# Clean up old data (keep only 2 years)
python manage.py manage_price_history cleanup --days 730
"""