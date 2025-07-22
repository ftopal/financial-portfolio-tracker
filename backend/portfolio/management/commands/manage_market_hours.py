# backend/portfolio/management/commands/manage_market_hours.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from portfolio.models import Security
import pytz
from datetime import datetime, time


def is_market_open():
    """Check if US stock market is open"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)

    # Market is closed on weekends
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close


def get_market_timezone(exchange_or_country):
    """Get the timezone for a given exchange or country"""
    exchange_timezones = {
        # US Exchanges
        'NYSE': 'US/Eastern', 'NASDAQ': 'US/Eastern', 'AMEX': 'US/Eastern', 'US': 'US/Eastern',
        # UK Exchanges
        'LSE': 'Europe/London', 'LON': 'Europe/London', 'LONDON': 'Europe/London', 'GB': 'Europe/London',
        'UK': 'Europe/London',
        # European Exchanges
        'FRA': 'Europe/Berlin', 'XETRA': 'Europe/Berlin', 'PAR': 'Europe/Paris', 'AMS': 'Europe/Amsterdam',
        # Other
        'CRYPTO': 'UTC',
    }

    key = str(exchange_or_country).upper() if exchange_or_country else 'US'
    timezone_str = exchange_timezones.get(key, 'US/Eastern')

    try:
        return pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        return pytz.timezone('US/Eastern')


def get_market_hours(exchange_or_country):
    """Get the market opening and closing hours for a given exchange or country"""
    market_hours = {
        'NYSE': (time(9, 30), time(16, 0)), 'NASDAQ': (time(9, 30), time(16, 0)), 'US': (time(9, 30), time(16, 0)),
        'LSE': (time(8, 0), time(16, 30)), 'LON': (time(8, 0), time(16, 30)), 'GB': (time(8, 0), time(16, 30)),
        'FRA': (time(9, 0), time(17, 30)), 'XETRA': (time(9, 0), time(17, 30)),
        'CRYPTO': (time(0, 0), time(23, 59)),
    }

    key = str(exchange_or_country).upper() if exchange_or_country else 'US'
    return market_hours.get(key, (time(9, 30), time(16, 0)))


def is_market_open_for_security(security):
    """Check if the market is open for a specific security"""
    if security.security_type == 'CRYPTO':
        return True

    exchange_or_country = security.exchange or security.country or 'US'
    market_tz = get_market_timezone(exchange_or_country)
    open_time, close_time = get_market_hours(exchange_or_country)

    now = datetime.now(market_tz)

    if now.weekday() >= 5:  # Weekend
        return False

    current_time = now.time()
    return open_time <= current_time <= close_time


class Command(BaseCommand):
    help = 'Manage and test multi-exchange market hours functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['status', 'test', 'list-markets', 'update-now'],
            help='Action to perform'
        )
        parser.add_argument('--security-id', type=int, help='Specific security ID to check')
        parser.add_argument('--exchange', type=str, help='Specific exchange to check')
        parser.add_argument('--country', type=str, help='Specific country to check')

    def handle(self, *args, **options):
        action = options['action']

        if action == 'status':
            self.show_market_status()
        elif action == 'test':
            self.test_market_hours(options)
        elif action == 'list-markets':
            self.list_all_markets()
        elif action == 'update-now':
            self.trigger_updates(options)

    def show_market_status(self):
        """Show current market status"""
        self.stdout.write(self.style.SUCCESS('\n=== CURRENT MARKET STATUS ==='))

        now_utc = timezone.now()
        self.stdout.write(f"Current UTC time: {now_utc}")

        markets = [
            ('US', 'US/Eastern', ['NYSE', 'NASDAQ']),
            ('GB', 'Europe/London', ['LSE']),
            ('DE', 'Europe/Berlin', ['FRA']),
        ]

        for country, timezone_str, exchanges in markets:
            tz = pytz.timezone(timezone_str)
            local_time = now_utc.astimezone(tz)

            open_time, close_time = get_market_hours(country)

            is_weekend = local_time.weekday() >= 5
            is_open_hours = open_time <= local_time.time() <= close_time
            is_open = not is_weekend and is_open_hours

            security_count = Security.objects.filter(
                is_active=True,
                country__iexact=country
            ).count()

            status_icon = "🟢" if is_open else "🔴"
            weekend_note = " (Weekend)" if is_weekend else ""

            self.stdout.write(f"\n{status_icon} {country} ({timezone_str}){weekend_note}")
            self.stdout.write(f"  Local time: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            self.stdout.write(f"  Market hours: {open_time} - {close_time}")
            self.stdout.write(f"  Securities: {security_count}")
            self.stdout.write(f"  Status: {'OPEN' if is_open else 'CLOSED'}")

    def test_market_hours(self, options):
        """Test market hours for specific securities"""
        self.stdout.write(self.style.SUCCESS('\n=== TESTING MARKET HOURS ==='))

        if options.get('security_id'):
            try:
                security = Security.objects.get(id=options['security_id'])
                is_open = is_market_open_for_security(security)

                self.stdout.write(f"\nSecurity: {security.symbol} ({security.name})")
                self.stdout.write(f"Exchange: {security.exchange or 'N/A'}")
                self.stdout.write(f"Country: {security.country or 'N/A'}")
                self.stdout.write(f"Security Type: {security.security_type}")
                self.stdout.write(f"Market Status: {'OPEN' if is_open else 'CLOSED'}")

                exchange_or_country = security.exchange or security.country or 'US'
                market_tz = get_market_timezone(exchange_or_country)
                open_time, close_time = get_market_hours(exchange_or_country)

                local_time = datetime.now(market_tz)
                self.stdout.write(f"Market timezone: {market_tz}")
                self.stdout.write(f"Local time: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                self.stdout.write(f"Market hours: {open_time} - {close_time}")

            except Security.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Security with ID {options["security_id"]} not found'))
        else:
            # Test first few securities
            securities = Security.objects.filter(is_active=True)[:10]
            for security in securities:
                is_open = is_market_open_for_security(security)
                status_icon = "🟢" if is_open else "🔴"
                market = security.exchange or security.country or 'Unknown'
                self.stdout.write(f"{status_icon} {security.symbol} ({market}) - {'OPEN' if is_open else 'CLOSED'}")

    def list_all_markets(self):
        """List all unique exchanges and countries"""
        self.stdout.write(self.style.SUCCESS('\n=== ALL MARKETS IN DATABASE ==='))

        exchanges = Security.objects.filter(
            is_active=True,
            exchange__isnull=False
        ).exclude(exchange='').values_list('exchange', flat=True).distinct()

        countries = Security.objects.filter(
            is_active=True,
            country__isnull=False
        ).exclude(country='').values_list('country', flat=True).distinct()

        self.stdout.write(f"\nUNIQUE EXCHANGES ({len(exchanges)}):")
        for exchange in sorted(exchanges):
            count = Security.objects.filter(is_active=True, exchange=exchange).count()
            self.stdout.write(f"  {exchange}: {count} securities")

        self.stdout.write(f"\nUNIQUE COUNTRIES ({len(countries)}):")
        for country in sorted(countries):
            count = Security.objects.filter(is_active=True, country=country).count()
            self.stdout.write(f"  {country}: {count} securities")

    def trigger_updates(self, options):
        """Trigger price updates"""
        self.stdout.write(self.style.SUCCESS('\n=== WOULD TRIGGER UPDATES ==='))
        self.stdout.write("(This is a test command - no actual updates triggered)")

        if options.get('security_id'):
            try:
                security = Security.objects.get(id=options['security_id'])
                self.stdout.write(f"Would update: {security.symbol}")
            except Security.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Security with ID {options["security_id"]} not found'))
        else:
            securities = Security.objects.filter(is_active=True)
            self.stdout.write(f"Would update {securities.count()} securities")