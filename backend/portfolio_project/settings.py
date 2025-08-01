from pathlib import Path
from dotenv import load_dotenv
import os


load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-omexlcwwa4-c8l9jd9=s)v$p*okc9-l$o4jfp_06y(txquqs79')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_celery_beat',  # For periodic tasks
    'django_celery_results',  # For storing task results

    # Local apps
    'portfolio',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React frontend default port
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',  # Allow the Authorization header
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

ROOT_URLCONF = 'portfolio_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'portfolio_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'financial_portfolio',
        'USER': 'portfolio_user',  # or 'postgres' if you didn't create a new user
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),  # the password you set
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

#import sys
#if 'test' in sys.argv:
#    DATABASES['default'] = {
#        'ENGINE': 'django.db.backends.sqlite3',
#        'NAME': ':memory:'
#    }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'  # Store results in Django database
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'  # For stock market hours
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Keep existing behavior for gradual migration
LEGACY_US_ONLY_MODE = False  # Set to True to keep old US-only behavior

# Transition settings - you can enable these one by one
ENABLE_UK_MARKET_UPDATES = True
ENABLE_EUROPEAN_MARKET_UPDATES = True
ENABLE_ASIAN_MARKET_UPDATES = True
ENABLE_CRYPTO_24_7_UPDATES = True

# Market hours checking behavior
CHECK_MARKET_HOURS = True  # Set to False to disable all market hours checking

# Multi-exchange support settings
ENABLE_MULTI_EXCHANGE_UPDATES = True  # Enable the new multi-exchange system

# Price update configuration
PRICE_UPDATE_SETTINGS = {
    # Global settings
    'CHECK_MARKET_HOURS_GLOBALLY': False,  # If True, only update when US market is open (old behavior)
    'RESPECT_INDIVIDUAL_MARKET_HOURS': True,  # If True, check each security's market hours

    # Update frequencies (in minutes) by market type
    'UPDATE_FREQUENCIES': {
        'US_MARKET': 15,  # Every 15 minutes during US market hours
        'UK_MARKET': 20,  # Every 20 minutes during UK market hours
        'EUROPEAN_MARKET': 20,  # Every 20 minutes during European market hours
        'ASIAN_MARKET': 30,  # Every 30 minutes during Asian market hours
        'CRYPTO': 60,  # Every hour for crypto (24/7)
        'AFTER_HOURS': 30,  # Every 30 minutes for after-hours trading
        'PRE_MARKET': 30,  # Every 30 minutes for pre-market trading
    },

    # API rate limiting
    'BATCH_SIZE_BY_REGION': {
        'US': 20,  # Process 20 US securities at once
        'GB': 15,  # Process 15 UK securities at once
        'EUR': 15,  # Process 15 European securities at once
        'ASIA': 10,  # Process 10 Asian securities at once
        'OTHER': 10,  # Process 10 other securities at once
    },

    # Retry settings for different regions
    'RETRY_DELAYS': {
        'US': 60,  # 1 minute retry delay for US markets
        'GB': 90,  # 1.5 minute retry delay for UK markets
        'OTHER': 120,  # 2 minute retry delay for other markets
    },
}

# Market holiday configuration (optional - for future enhancement)
MARKET_HOLIDAYS = {
    'US': [
        # US market holidays (you can populate this)
        # '2025-01-01',  # New Year's Day
        # '2025-07-04',  # Independence Day
        # Add more as needed
    ],
    'GB': [
        # UK market holidays
        # '2025-01-01',  # New Year's Day
        # '2025-12-25',  # Christmas Day
    ],
    # Add more countries as needed
}

# Regional API endpoints (for future multi-provider support)
MARKET_DATA_PROVIDERS = {
    'DEFAULT': 'yahoo',  # Default provider
    'PROVIDERS': {
        'yahoo': {
            'regions': ['US', 'GB', 'DE', 'FR', 'JP', 'HK', 'AU', 'CA'],
            'rate_limit': 2000,  # requests per hour
            'supports_crypto': True,
        },
        # Future providers can be added here
        # 'alpha_vantage': {
        #     'regions': ['US', 'GB'],
        #     'rate_limit': 5,  # requests per minute (free tier)
        #     'supports_crypto': False,
        # },
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'xirr_format': {
            'format': '[XIRR] {levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        # Console handler for development
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # General application log file
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'portfolio.log',
            'formatter': 'verbose',
        },
        # XIRR-specific log file
        'xirr_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'xirr.log',
            'formatter': 'xirr_format',
        },
        # Celery log file (keep existing)
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'celery.log',
            'formatter': 'verbose',
        },
        # Error-only log file
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Root portfolio app logger
        'portfolio': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # XIRR-specific logger
        'portfolio.services.xirr_service': {
            'handlers': ['console', 'xirr_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Portfolio views logger
        'portfolio.views': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Celery logger (keep existing)
        'celery': {
            'handlers': ['console', 'celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Django root logger
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Database queries (only in development - uncomment to see SQL queries)
        # 'django.db.backends': {
        #     'handlers': ['console'] if DEBUG else [],
        #     'level': 'DEBUG' if DEBUG else 'INFO',
        #     'propagate': False,
        # },
    },
}

# Enhanced logging for market hours
LOGGING['loggers']['portfolio.market_hours'] = {
    'handlers': ['console', 'file'],
    'level': 'INFO',
    'propagate': True,
}

# Add market hours specific log file if desired
LOGGING['handlers']['market_hours_file'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'market_hours.log'),
    'maxBytes': 1024*1024*5,  # 5 MB
    'backupCount': 5,
    'formatter': 'verbose',
}

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Currency settings
DEFAULT_CURRENCY = 'USD'
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'HKD', 'SGD', 'INR', 'BRL']

# Portfolio History Settings
PORTFOLIO_AUTO_RECALCULATION = True  # Enable automatic recalculation
PORTFOLIO_SIGNAL_DEBUGGING = False   # Enable signal debugging
PORTFOLIO_BATCH_RECALCULATION_DELAY = 300  # 5 minutes delay for batch operations
PORTFOLIO_RECALCULATION_QUEUE = 'portfolio_history'  # Celery queue name
PORTFOLIO_HISTORY_RETENTION_DAYS = 365  # Default retention for free users (1 year)
PORTFOLIO_PREMIUM_RETENTION_DAYS = 3650  # Premium users (10 years)
PORTFOLIO_MAX_CONCURRENT_CALCULATIONS = 5  # Max concurrent portfolio calculations
PORTFOLIO_CALCULATION_TIMEOUT = 300  # 5 minutes timeout for calculations
PORTFOLIO_BACKFILL_BATCH_SIZE = 50  # Number of days to process in each batch
PORTFOLIO_CACHE_TIMEOUT = 300  # 5 minutes cache for portfolio calculations
PORTFOLIO_PERFORMANCE_CACHE_TIMEOUT = 1800  # 30 minutes cache for performance data


# Exchange rate API configuration
EXCHANGE_RATE_PROVIDER = 'portfolio.services.currency_service.ExchangeRateAPIProvider'
EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY')

# Cache configuration for exchange rates
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

# Cache timeout for exchange rates (in seconds)
EXCHANGE_RATE_CACHE_TIMEOUT = 3600  # 1 hour

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100
}