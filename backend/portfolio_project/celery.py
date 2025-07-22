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
    'update-crypto-prices-hourly': {
        'task': 'portfolio.tasks.update_securities_by_type',
        'schedule': crontab(minute='0'),  # Every hour for crypto
        'args': ('CRYPTO',)
    },

    # ENHANCED: Global market-aware price updates
    # This replaces the need for the old update-security-prices-every-15-minutes
    # but we'll keep both for backward compatibility during transition
    'update-global-market-prices-every-15-minutes': {
        'task': 'portfolio.tasks.update_global_market_prices',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes, all day
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.global',
            'priority': 8
        }
    },

    # ENHANCED: Update UK/European markets during their hours
    #'update-uk-securities-during-uk-hours': {
    #    'task': 'portfolio.tasks.update_securities_by_country',
    #    'schedule': crontab(minute='*/20', hour='8-17', day_of_week='1-5'),  # Every 20 min, 8AM-4PM GMT
    #    'args': ('GB',),
    #    'options': {
    #        'queue': 'price_updates',
    #        'routing_key': 'price_updates.uk',
    #        'priority': 7
    #    }
    #},

    # ENHANCED: Update European securities during European hours
    'update-european-securities-morning': {
        'task': 'portfolio.tasks.update_securities_by_country',
        'schedule': crontab(minute='*/20', hour='9-17', day_of_week='1-5'),  # Every 20 min, 9AM-5PM CET
        'args': ('DE',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.europe',
            'priority': 7
        }
    },

    # ENHANCED: Update Asian markets during their hours (early morning UTC)
    'update-asian-securities-tokyo': {
        'task': 'portfolio.tasks.update_securities_by_country',
        'schedule': crontab(minute='*/30', hour='0-6', day_of_week='1-5'),  # Every 30 min, 12AM-6AM UTC (9AM-3PM JST)
        'args': ('JP',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.asia',
            'priority': 6
        }
    },

    'update-asian-securities-hongkong': {
        'task': 'portfolio.tasks.update_securities_by_country',
        'schedule': crontab(minute='*/30', hour='1-8', day_of_week='1-5'),  # Every 30 min, 1AM-8AM UTC (9AM-4PM HKT)
        'args': ('HK',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.asia',
            'priority': 6
        }
    },

    # ENHANCED: Specific exchange updates for major exchanges
    'update-lse-securities': {
        'task': 'portfolio.tasks.update_securities_by_exchange',
        'schedule': crontab(minute='*/15', hour='8-17', day_of_week='1-5'),  # Every 15 min during LSE hours
        'args': ('LSE',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.lse',
            'priority': 8
        }
    },

    'update-frankfurt-securities': {
        'task': 'portfolio.tasks.update_securities_by_exchange',
        'schedule': crontab(minute='*/20', hour='9-17', day_of_week='1-5'),  # Every 20 min during Frankfurt hours
        'args': ('FRA',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.frankfurt',
            'priority': 7
        }
    },

    'update-amsterdam-securities': {
        'task': 'portfolio.tasks.update_securities_by_exchange',
        'schedule': crontab(minute='*/15', hour='9-18', day_of_week='1-5'),  # Every 15 min during Amsterdam hours
        'args': ('AMS',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.frankfurt',
            'priority': 7
        }
    },

    # ENHANCED: Pre-market and after-hours updates for US securities
    'update-us-premarket': {
        'task': 'portfolio.tasks.update_securities_by_country',
        'schedule': crontab(minute='*/30', hour='8-9', day_of_week='1-5'),  # Every 30 min, 8-9AM ET (pre-market)
        'args': ('US',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.us_premarket',
            'priority': 6
        }
    },

    'update-us-afterhours': {
        'task': 'portfolio.tasks.update_securities_by_country',
        'schedule': crontab(minute='*/30', hour='16-20', day_of_week='1-5'),  # Every 30 min, 4-8PM ET (after-hours)
        'args': ('US',),
        'options': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.us_afterhours',
            'priority': 5
        }
    },

    # Exchange rate updates (ENHANCED)
    'sync-daily-historical-rates': {
        'task': 'portfolio.tasks.sync_daily_exchange_rates',
        'schedule': crontab(hour='7', minute='0', day_of_week='1-5'),  # 7 AM weekdays (after forex markets close)
    },
    'update-current-exchange-rates': {
        'task': 'portfolio.tasks.update_exchange_rates',
        'schedule': crontab(minute='0', hour='*/1'),  # Every 1 hours for current rates
        'args': (['USD', 'EUR', 'GBP'], ['USD', 'EUR', 'GBP'])
    },

    # Cleanup tasks
    # Enhanced price history cleanup (keep more data for portfolio calculations)
    'cleanup-old-price-history-enhanced': {
        'task': 'portfolio.tasks.cleanup_old_price_history',
        'schedule': crontab(hour='4', minute='30'),  # Daily at 4:30 AM
        'args': (7300,),  # Keep 20 years of price data instead of 1 year
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.price_cleanup',
            'priority': 1
        }
    },
    # Exchange rate cleanup
    'cleanup-old-exchange-rates-enhanced': {
        'task': 'portfolio.tasks.cleanup_old_exchange_rates',
        'schedule': crontab(hour='3', minute='30', day_of_week='0'),  # Weekly on Sunday at 3:30 AM
        'args': (7300,),  # Keep 20 years of exchange rate data
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.exchange_cleanup',
            'priority': 1
        }
    },
    'backfill-new-securities-daily': {
        'task': 'portfolio.tasks.backfill_all_securities_task',
        'schedule': crontab(hour='1', minute='0'),  # Daily at 1 AM
        'args': (30, 5, False)  # 30 days back, batch size 5, don't force update
    },
    'detect-and-fill-price-gaps-weekly': {
        'task': 'portfolio.tasks.detect_and_fill_price_gaps_task',
        'schedule': crontab(hour='2', minute='30', day_of_week='0'),  # Sunday 2:30 AM
        'args': (None, 7)  # All securities, max 7 day gaps
    },
    'validate-price-data-weekly': {
        'task': 'portfolio.tasks.validate_all_price_data_task',
        'schedule': crontab(hour='3', minute='0', day_of_week='1'),  # Monday 3 AM
    },

    # Daily portfolio value calculations
    'calculate-daily-portfolio-snapshots': {
        'task': 'portfolio.tasks.calculate_daily_portfolio_snapshots',
        'schedule': crontab(hour='6', minute='0'),  # Daily at 6 AM
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.daily_snapshots',
            'priority': 5
        }
    },

    # Evening portfolio snapshots (for end-of-day calculations)
    'calculate-evening-portfolio-snapshots': {
        'task': 'portfolio.tasks.calculate_daily_portfolio_snapshots',
        'schedule': crontab(hour='18', minute='0', day_of_week='1-5'),  # 6 PM weekdays
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.evening_snapshots',
            'priority': 3
        }
    },

    # Weekly bulk backfill to ensure data consistency
    'bulk-portfolio-backfill-weekly': {
        'task': 'portfolio.tasks.bulk_portfolio_backfill_task',
        'schedule': crontab(hour='2', minute='0', day_of_week='0'),  # Sunday 2 AM
        'args': (30, False),  # 30 days back, don't force update
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.bulk_backfill',
            'priority': 2
        }
    },

    # Monthly comprehensive backfill
    'bulk-portfolio-backfill-monthly': {
        'task': 'portfolio.tasks.bulk_portfolio_backfill_task',
        'schedule': crontab(hour='1', minute='0', day_of_month='1'),  # 1st of month at 1 AM
        'args': (90, False),  # 90 days back, don't force update
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.monthly_backfill',
            'priority': 1
        }
    },
    # Portfolio gap detection and filling
    'detect-and-fill-portfolio-gaps-weekly': {
        'task': 'portfolio.tasks.detect_and_fill_portfolio_gaps_task',
        'schedule': crontab(hour='1', minute='30', day_of_week='1'),  # Monday 1:30 AM
        'args': (None, 10),  # All portfolios, max 10 day gaps
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.gap_detection',
            'priority': 3
        }
    },
    # Portfolio history validation
    'validate-portfolio-history-weekly': {
        'task': 'portfolio.tasks.validate_portfolio_history_task',
        'schedule': crontab(hour='3', minute='0', day_of_week='1'),  # Monday 3 AM
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.validation',
            'priority': 2
        }
    },
    # Portfolio history cleanup (retention policy)
    'cleanup-old-portfolio-snapshots-weekly': {
        'task': 'portfolio.tasks.cleanup_old_portfolio_snapshots',
        'schedule': crontab(hour='4', minute='0', day_of_week='0'),  # Sunday 4 AM
        'args': (365,),  # Keep 1 year of data (can be overridden by user settings)
        'options': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.cleanup',
            'priority': 1
        }
    },

    # =====================
    # MONITORING AND HEALTH CHECKS
    # =====================

    # Test portfolio history service health
    'test-portfolio-history-service-daily': {
        'task': 'portfolio.tasks.test_portfolio_history_service',
        'schedule': crontab(hour='5', minute='0'),  # Daily at 5 AM
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring.health_check',
            'priority': 4
        }
    },

    # Generate system health report
    'generate-system-health-report': {
        'task': 'portfolio.tasks.generate_system_health_report',
        'schedule': crontab(hour='6', minute='30', day_of_week='1'),  # Monday 6:30 AM
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring.health_report',
            'priority': 2
        }
    },
}

app.conf.timezone = 'UTC'

# =====================
# CELERY CONFIGURATION
# =====================

# Enhanced Celery configuration for Phase 3
app.conf.update(
    # Timezone settings
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'portfolio.tasks.calculate_daily_portfolio_snapshots': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.daily',
        },
        'portfolio.tasks.backfill_portfolio_history_task': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.backfill',
        },
        'portfolio.tasks.bulk_portfolio_backfill_task': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.bulk',
        },
        'portfolio.tasks.portfolio_transaction_trigger_task': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.trigger',
        },
        'portfolio.tasks.detect_and_fill_portfolio_gaps_task': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.gaps',
        },
        'portfolio.tasks.validate_portfolio_history_task': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.validate',
        },
        'portfolio.tasks.generate_portfolio_performance_report': {
            'queue': 'portfolio_history',
            'routing_key': 'portfolio_history.reports',
        },
        # Price history tasks
        'portfolio.tasks.update_all_security_prices': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.all',
        },
        'portfolio.tasks.backfill_security_prices_task': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.backfill',
        },
        'portfolio.tasks.update_global_market_prices': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.global',
        },
        'portfolio.tasks.update_securities_by_exchange': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.exchange',
        },
        'portfolio.tasks.update_securities_by_country': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.country',
        },
        # Keep existing routes for backward compatibility
        'portfolio.tasks.update_security_price': {
            'queue': 'price_updates',
            'routing_key': 'price_updates.individual',
        },
        # Maintenance tasks
        'portfolio.tasks.cleanup_old_portfolio_snapshots': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.cleanup',
        },
        'portfolio.tasks.cleanup_old_price_history': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.price_cleanup',
        },
    },

    # Task priorities
    task_default_priority=5,
    task_inherit_parent_priority=True,

    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,

    # Monitoring
    task_send_sent_event=True,
    task_track_started=True,

    # Queue settings
    task_default_queue='celery',
    task_create_missing_queues=True,

    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)

# =====================
# QUEUE DEFINITIONS
# =====================

# Define queue configurations
app.conf.task_queues = {
    # High priority portfolio history queue
    'portfolio_history': {
        'exchange': 'portfolio_history',
        'exchange_type': 'direct',
        'routing_key': 'portfolio_history',
        'queue_arguments': {
            'x-max-priority': 10,
            'x-message-ttl': 3600000,  # 1 hour TTL
        }
    },

    # Price updates queue
    'price_updates': {
        'exchange': 'price_updates',
        'exchange_type': 'direct',
        'routing_key': 'price_updates',
        'queue_arguments': {
            'x-max-priority': 8,
            'x-message-ttl': 1800000,  # 30 minutes TTL
        }
    },

    # Maintenance queue
    'maintenance': {
        'exchange': 'maintenance',
        'exchange_type': 'direct',
        'routing_key': 'maintenance',
        'queue_arguments': {
            'x-max-priority': 3,
            'x-message-ttl': 7200000,  # 2 hours TTL
        }
    },

    # Monitoring queue
    'monitoring': {
        'exchange': 'monitoring',
        'exchange_type': 'direct',
        'routing_key': 'monitoring',
        'queue_arguments': {
            'x-max-priority': 5,
            'x-message-ttl': 3600000,  # 1 hour TTL
        }
    },
}


# =====================
# DEBUGGING AND TESTING
# =====================

@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    print(f'Request: {self.request!r}')
    return f'Celery is working! Task ID: {self.request.id}'


# =====================
# PERIODIC TASK MANAGEMENT
# =====================

def enable_portfolio_history_tasks():
    """Enable portfolio history periodic tasks"""
    from django_celery_beat.models import PeriodicTask

    # Enable portfolio history tasks
    portfolio_tasks = [
        'calculate-daily-portfolio-snapshots',
        'calculate-evening-portfolio-snapshots',
        'bulk-portfolio-backfill-weekly',
        'detect-and-fill-portfolio-gaps-weekly',
        'validate-portfolio-history-weekly',
        'cleanup-old-portfolio-snapshots-weekly',
    ]

    for task_name in portfolio_tasks:
        try:
            task = PeriodicTask.objects.get(name=task_name)
            task.enabled = True
            task.save()
            print(f"Enabled task: {task_name}")
        except PeriodicTask.DoesNotExist:
            print(f"Task not found: {task_name}")


def disable_portfolio_history_tasks():
    """Disable portfolio history periodic tasks"""
    from django_celery_beat.models import PeriodicTask

    # Disable portfolio history tasks
    portfolio_tasks = [
        'calculate-daily-portfolio-snapshots',
        'calculate-evening-portfolio-snapshots',
        'bulk-portfolio-backfill-weekly',
        'detect-and-fill-portfolio-gaps-weekly',
        'validate-portfolio-history-weekly',
        'cleanup-old-portfolio-snapshots-weekly',
    ]

    for task_name in portfolio_tasks:
        try:
            task = PeriodicTask.objects.get(name=task_name)
            task.enabled = False
            task.save()
            print(f"Disabled task: {task_name}")
        except PeriodicTask.DoesNotExist:
            print(f"Task not found: {task_name}")

# =====================
# CELERY BEAT CUSTOMIZATION
# =====================

# Custom beat scheduler for development
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('settings_dev'):
    # Reduce frequency for development
    app.conf.beat_schedule.update({
        'calculate-daily-portfolio-snapshots': {
            'task': 'portfolio.tasks.calculate_daily_portfolio_snapshots',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes in dev
        },
        'bulk-portfolio-backfill-weekly': {
            'task': 'portfolio.tasks.bulk_portfolio_backfill_task',
            'schedule': crontab(hour='*/6'),  # Every 6 hours in dev
            'args': (7, False),  # Only 7 days back in dev
        },
    })

# =====================
# INITIALIZATION
# =====================

# Initialize Celery app
if __name__ == '__main__':
    app.start()