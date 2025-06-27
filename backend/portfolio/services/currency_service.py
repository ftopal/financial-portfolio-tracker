import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from ..models import ExchangeRate, Currency

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for handling currency conversions and exchange rates"""

    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_supported_currencies():
        """Get list of supported currencies"""
        return Currency.objects.filter(is_active=True).order_by('code')

    @classmethod
    def get_exchange_rate(cls, from_currency, to_currency, date=None):
        """
        Get exchange rate between two currencies for a specific date.
        Uses caching to reduce database queries.
        """
        if from_currency == to_currency:
            return Decimal('1')

        if date is None:
            date = timezone.now().date()

        # Check cache first
        cache_key = f"exchange_rate:{from_currency}:{to_currency}:{date}"
        cached_rate = cache.get(cache_key)
        if cached_rate is not None:
            return Decimal(str(cached_rate))

        # Get from database
        rate = ExchangeRate.get_rate(from_currency, to_currency, date)

        if rate is not None:
            cache.set(cache_key, str(rate), cls.CACHE_TIMEOUT)
            return rate

        # If no rate found, try to fetch from external API
        if date == timezone.now().date():
            cls.update_exchange_rates([from_currency], [to_currency])
            rate = ExchangeRate.get_rate(from_currency, to_currency, date)
            if rate is not None:
                cache.set(cache_key, str(rate), cls.CACHE_TIMEOUT)
                return rate

        logger.warning(f"No exchange rate found for {from_currency}/{to_currency} on {date}")
        return None

    @classmethod
    def convert_amount(cls, amount, from_currency, to_currency, date=None):
        """Convert an amount from one currency to another"""
        if amount == 0:
            return Decimal('0')

        rate = cls.get_exchange_rate(from_currency, to_currency, date)
        if rate is None:
            raise ValueError(f"No exchange rate available for {from_currency}/{to_currency}")

        return amount * rate

    @classmethod
    def update_exchange_rates(cls, base_currencies=None, target_currencies=None):
        """
        Fetch latest exchange rates from external API.
        This example uses exchangerate-api.com (free tier available)
        """
        if base_currencies is None:
            base_currencies = ['USD', 'EUR', 'GBP']

        if target_currencies is None:
            # Get all active currencies
            target_currencies = list(
                Currency.objects.filter(is_active=True).values_list('code', flat=True)
            )

        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)

        for base in base_currencies:
            try:
                # Using exchangerate-api.com free tier
                if api_key:
                    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}"
                else:
                    # Free endpoint (limited requests)
                    url = f"https://api.exchangerate-api.com/v4/latest/{base}"

                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                rates = data.get('rates', {})
                date = timezone.now().date()

                for target in target_currencies:
                    if target in rates and target != base:
                        ExchangeRate.objects.update_or_create(
                            from_currency=base,
                            to_currency=target,
                            date=date,
                            defaults={
                                'rate': Decimal(str(rates[target])),
                                'source': 'exchangerate-api.com'
                            }
                        )

                logger.info(f"Updated exchange rates for {base}")

            except requests.RequestException as e:
                logger.error(f"Failed to fetch exchange rates for {base}: {e}")
            except Exception as e:
                logger.error(f"Error updating exchange rates for {base}: {e}")

    @classmethod
    def get_portfolio_value_in_currency(cls, portfolio, target_currency, date=None):
        """Calculate total portfolio value in a specific currency"""
        from ..models import Transaction

        if date is None:
            date = timezone.now().date()

        total_value = Decimal('0')

        # Get holdings
        holdings = portfolio.get_holdings()

        for security_id, holding_data in holdings.items():
            security = holding_data['security']
            quantity = holding_data['quantity']
            current_value = security.current_price * quantity

            # Convert from security currency to target currency
            if security.currency != target_currency:
                converted_value = cls.convert_amount(
                    current_value,
                    security.currency,
                    target_currency,
                    date
                )
                total_value += converted_value
            else:
                total_value += current_value

        # Add cash balance
        if hasattr(portfolio, 'cash_account'):
            cash_balance = portfolio.cash_account.balance
            if portfolio.cash_account.currency != target_currency:
                cash_balance = cls.convert_amount(
                    cash_balance,
                    portfolio.cash_account.currency,
                    target_currency,
                    date
                )
            total_value += cash_balance

        return total_value

    @classmethod
    def get_currency_exposure(cls, portfolio):
        """
        Calculate portfolio exposure by currency
        Returns dict with currency codes as keys and exposure amounts as values
        """
        exposure = {}

        # Get holdings
        holdings = portfolio.get_holdings()

        for security_id, holding_data in holdings.items():
            security = holding_data['security']
            quantity = holding_data['quantity']
            current_value = security.current_price * quantity

            currency = security.currency
            if currency not in exposure:
                exposure[currency] = Decimal('0')
            exposure[currency] += current_value

        # Add cash
        if hasattr(portfolio, 'cash_account'):
            currency = portfolio.cash_account.currency
            if currency not in exposure:
                exposure[currency] = Decimal('0')
            exposure[currency] += portfolio.cash_account.balance

        return exposure

    @classmethod
    def calculate_fx_impact(cls, portfolio, start_date, end_date, base_currency=None):
        """
        Calculate the impact of currency movements on portfolio returns
        """
        if base_currency is None:
            base_currency = portfolio.currency

        fx_impact = Decimal('0')

        # Get currency exposure at start date
        exposure_start = cls.get_currency_exposure(portfolio)

        for currency, amount in exposure_start.items():
            if currency != base_currency:
                # Get exchange rates
                rate_start = cls.get_exchange_rate(currency, base_currency, start_date)
                rate_end = cls.get_exchange_rate(currency, base_currency, end_date)

                if rate_start and rate_end:
                    # Calculate impact
                    value_start = amount * rate_start
                    value_end = amount * rate_end
                    fx_impact += (value_end - value_start)

        return fx_impact


class ExchangeRateProvider:
    """Base class for exchange rate providers"""

    def fetch_rates(self, base_currency, target_currencies):
        raise NotImplementedError


class ExchangeRateAPIProvider(ExchangeRateProvider):
    """Provider for exchangerate-api.com"""

    def __init__(self, api_key=None):
        self.api_key = api_key

    def fetch_rates(self, base_currency, target_currencies):
        if self.api_key:
            url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/latest/{base_currency}"
        else:
            url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        rates = {}
        all_rates = data.get('rates', {})

        for target in target_currencies:
            if target in all_rates:
                rates[target] = Decimal(str(all_rates[target]))

        return rates