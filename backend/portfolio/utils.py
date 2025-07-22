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
    """
    Get the timezone for a given exchange or country

    Args:
        exchange_or_country: Exchange code (e.g., 'NYSE', 'LSE') or country (e.g., 'US', 'GB')

    Returns:
        pytz timezone object
    """
    # Exchange to timezone mapping
    exchange_timezones = {
        # US Exchanges
        'NYSE': 'US/Eastern',
        'NASDAQ': 'US/Eastern',
        'AMEX': 'US/Eastern',
        'NYSE': 'US/Eastern',
        'US': 'US/Eastern',

        # UK Exchanges
        'LSE': 'Europe/London',
        'LON': 'Europe/London',
        'LONDON': 'Europe/London',
        'GB': 'Europe/London',
        'UK': 'Europe/London',

        # European Exchanges
        'FRA': 'Europe/Berlin',  # Frankfurt
        'XETRA': 'Europe/Berlin',  # Xetra
        'PAR': 'Europe/Paris',  # Euronext Paris
        'AMS': 'Europe/Amsterdam',  # Euronext Amsterdam
        'MIL': 'Europe/Rome',  # Borsa Italiana
        'SWX': 'Europe/Zurich',  # SIX Swiss Exchange
        'DE': 'Europe/Berlin',  # Germany
        'FR': 'Europe/Paris',  # France
        'NL': 'Europe/Amsterdam',  # Netherlands
        'IT': 'Europe/Rome',  # Italy
        'CH': 'Europe/Zurich',  # Switzerland

        # Asian Exchanges  
        'TSE': 'Asia/Tokyo',  # Tokyo Stock Exchange
        'JPX': 'Asia/Tokyo',  # Japan Exchange Group
        'HKG': 'Asia/Hong_Kong',  # Hong Kong Stock Exchange
        'HKEX': 'Asia/Hong_Kong',
        'SSE': 'Asia/Shanghai',  # Shanghai Stock Exchange
        'SZSE': 'Asia/Shanghai',  # Shenzhen Stock Exchange
        'BSE': 'Asia/Kolkata',  # Bombay Stock Exchange
        'NSE': 'Asia/Kolkata',  # National Stock Exchange (India)
        'ASX': 'Australia/Sydney',  # Australian Securities Exchange
        'JP': 'Asia/Tokyo',  # Japan
        'HK': 'Asia/Hong_Kong',  # Hong Kong
        'CN': 'Asia/Shanghai',  # China
        'IN': 'Asia/Kolkata',  # India
        'AU': 'Australia/Sydney',  # Australia

        # Canadian Exchanges
        'TSX': 'America/Toronto',  # Toronto Stock Exchange
        'TSXV': 'America/Toronto',  # TSX Venture Exchange
        'CA': 'America/Toronto',  # Canada

        # Other exchanges
        'CRYPTO': 'UTC',  # Crypto markets are 24/7, use UTC
    }

    # Convert to uppercase for case-insensitive lookup
    key = str(exchange_or_country).upper() if exchange_or_country else 'US'

    timezone_str = exchange_timezones.get(key, 'US/Eastern')  # Default to US Eastern

    try:
        return pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        # Fallback to US Eastern if timezone not found
        return pytz.timezone('US/Eastern')


def get_market_hours(exchange_or_country):
    """
    Get the market opening and closing hours for a given exchange or country

    Args:
        exchange_or_country: Exchange code or country

    Returns:
        tuple: (open_time, close_time) as time objects in local market timezone
    """
    # Market hours mapping (in local time)
    market_hours = {
        # US Markets
        'NYSE': (time(9, 30), time(16, 0)),  # 9:30 AM - 4:00 PM ET
        'NASDAQ': (time(9, 30), time(16, 0)),
        'AMEX': (time(9, 30), time(16, 0)),
        'NYSE': (time(9, 30), time(16, 0)),
        'US': (time(9, 30), time(16, 0)),

        # UK Markets
        'LSE': (time(8, 0), time(16, 30)),  # 8:00 AM - 4:30 PM GMT/BST
        'LON': (time(8, 0), time(16, 30)),
        'LONDON': (time(8, 0), time(16, 30)),
        'GB': (time(8, 0), time(16, 30)),
        'UK': (time(8, 0), time(16, 30)),

        # European Markets
        'FRA': (time(9, 0), time(17, 30)),  # 9:00 AM - 5:30 PM CET/CEST
        'XETRA': (time(9, 0), time(17, 30)),
        'PAR': (time(9, 0), time(17, 30)),  # 9:00 AM - 5:30 PM CET/CEST
        'AMS': (time(9, 0), time(17, 30)),  # 9:00 AM - 5:30 PM CET/CEST
        'MIL': (time(9, 0), time(17, 30)),  # 9:00 AM - 5:30 PM CET/CEST
        'SWX': (time(9, 0), time(17, 30)),  # 9:00 AM - 5:30 PM CET/CEST
        'DE': (time(9, 0), time(17, 30)),
        'FR': (time(9, 0), time(17, 30)),
        'NL': (time(9, 0), time(17, 30)),
        'IT': (time(9, 0), time(17, 30)),
        'CH': (time(9, 0), time(17, 30)),

        # Asian Markets
        'TSE': (time(9, 0), time(15, 0)),  # 9:00 AM - 3:00 PM JST
        'JPX': (time(9, 0), time(15, 0)),
        'HKG': (time(9, 30), time(16, 0)),  # 9:30 AM - 4:00 PM HKT
        'HKEX': (time(9, 30), time(16, 0)),
        'SSE': (time(9, 30), time(15, 0)),  # 9:30 AM - 3:00 PM CST
        'SZSE': (time(9, 30), time(15, 0)),
        'BSE': (time(9, 15), time(15, 30)),  # 9:15 AM - 3:30 PM IST
        'NSE': (time(9, 15), time(15, 30)),
        'ASX': (time(10, 0), time(16, 0)),  # 10:00 AM - 4:00 PM AEST/AEDT
        'JP': (time(9, 0), time(15, 0)),
        'HK': (time(9, 30), time(16, 0)),
        'CN': (time(9, 30), time(15, 0)),
        'IN': (time(9, 15), time(15, 30)),
        'AU': (time(10, 0), time(16, 0)),

        # Canadian Markets
        'TSX': (time(9, 30), time(16, 0)),  # 9:30 AM - 4:00 PM ET
        'TSXV': (time(9, 30), time(16, 0)),
        'CA': (time(9, 30), time(16, 0)),

        # Crypto is 24/7
        'CRYPTO': (time(0, 0), time(23, 59)),
    }

    # Convert to uppercase for case-insensitive lookup
    key = str(exchange_or_country).upper() if exchange_or_country else 'US'

    return market_hours.get(key, (time(9, 30), time(16, 0)))  # Default to US hours


def is_market_open_for_security(security):
    """
    Check if the market is open for a specific security

    Args:
        security: Security model instance

    Returns:
        bool: True if market is open for this security
    """
    # For crypto, markets are always open
    if security.security_type == 'CRYPTO':
        return True

    # Get market info for this security
    exchange_or_country = security.exchange or security.country or 'US'

    # Get timezone and market hours
    market_tz = get_market_timezone(exchange_or_country)
    open_time, close_time = get_market_hours(exchange_or_country)

    # Get current time in market timezone
    now = datetime.now(market_tz)

    # Check if it's a weekday (markets typically closed on weekends)
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Check if current time is within market hours
    current_time = now.time()

    # Handle markets that close after midnight (rare, but possible)
    if open_time <= close_time:
        return open_time <= current_time <= close_time
    else:
        # Market crosses midnight
        return current_time >= open_time or current_time <= close_time


def should_update_security_prices(security_filter=None):
    """
    Determine which securities should have their prices updated based on market hours

    Args:
        security_filter: Optional queryset filter for securities

    Returns:
        QuerySet: Securities that should be updated now
    """
    from .models import Security

    if security_filter is None:
        securities = Security.objects.filter(is_active=True)
    else:
        securities = security_filter.filter(is_active=True)

    # Group securities by their market timezone and hours
    securities_to_update = []

    for security in securities:
        if is_market_open_for_security(security):
            securities_to_update.append(security.id)

    return Security.objects.filter(id__in=securities_to_update)