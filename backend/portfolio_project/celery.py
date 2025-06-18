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
    'update-stock-prices-every-15-minutes': {
        'task': 'portfolio.tasks.update_all_stock_prices',
        'schedule': crontab(minute='*/15', hour='9-16', day_of_week='1-5'),  # Every 15 min, 9AM-4PM, Mon-Fri
    },
    'update-stock-prices-at-market-open': {
        'task': 'portfolio.tasks.update_all_stock_prices',
        'schedule': crontab(minute='30', hour='9', day_of_week='1-5'),  # 9:30 AM Mon-Fri
    },
    'update-stock-prices-at-market-close': {
        'task': 'portfolio.tasks.update_all_stock_prices',
        'schedule': crontab(minute='0', hour='16', day_of_week='1-5'),  # 4:00 PM Mon-Fri
    },
    'cleanup-old-price-history': {
        'task': 'portfolio.tasks.cleanup_old_price_history',
        'schedule': crontab(hour='2', minute='0'),  # Daily at 2 AM
    },
}