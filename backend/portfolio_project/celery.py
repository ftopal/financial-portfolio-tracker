import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

# Create the Celery app
app = Celery('portfolio_project')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    # Security price updates
    'update-security-prices-every-15-minutes': {
        'task': 'portfolio.tasks.update_all_security_prices',
        'schedule': crontab(minute='*/15', hour='9-16', day_of_week='1-5'),  # Every 15 min, 9AM-4PM, Mon-Fri
    },
    'update-security-prices-at-market-open': {
        'task': 'portfolio.tasks.update_all_security_prices',
        'schedule': crontab(minute='30', hour='9', day_of_week='1-5'),  # 9:30 AM Mon-Fri
    },
    'update-security-prices-at-market-close': {
        'task': 'portfolio.tasks.update_all_security_prices',
        'schedule': crontab(minute='0', hour='16', day_of_week='1-5'),  # 4:00 PM Mon-Fri
    },
    'update-crypto-prices-hourly': {
        'task': 'portfolio.tasks.update_securities_by_type',
        'schedule': crontab(minute='0'),  # Every hour for crypto
        'args': ('CRYPTO',)
    },

    # Exchange rate updates (ENHANCED)
    'sync-daily-historical-rates': {
        'task': 'portfolio.tasks.sync_daily_exchange_rates',
        'schedule': crontab(hour='7', minute='0', day_of_week='1-5'),  # 7 AM weekdays (after forex markets close)
    },
    'update-current-exchange-rates': {
        'task': 'portfolio.tasks.update_exchange_rates',
        'schedule': crontab(minute='0', hour='*/4'),  # Every 4 hours for current rates
        'args': (['USD', 'EUR', 'GBP'], ['USD', 'EUR', 'GBP'])
    },

    # Cleanup tasks
    'cleanup-old-price-history': {
        'task': 'portfolio.tasks.cleanup_old_price_history',
        'schedule': crontab(hour='2', minute='0'),  # Daily at 2 AM
    },
    'cleanup-old-exchange-rates': {
        'task': 'portfolio.tasks.cleanup_old_exchange_rates',
        'schedule': crontab(hour='3', minute='0', day_of_week='0'),  # Weekly on Sunday at 3 AM
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')