import pytz
from datetime import datetime


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