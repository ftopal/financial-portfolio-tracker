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

        # If no rate found for the exact date, try to find the most recent rate
        recent_rate = ExchangeRate.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            date__lte=date
        ).order_by('-date').first()

        if recent_rate:
            logger.info(f"Using recent rate for {from_currency}/{to_currency} from {recent_rate.date}")
            cache.set(cache_key, str(recent_rate.rate), cls.CACHE_TIMEOUT)
            return recent_rate.rate

        # Try inverse rate
        recent_inverse = ExchangeRate.objects.filter(
            from_currency=to_currency,
            to_currency=from_currency,
            date__lte=date
        ).order_by('-date').first()

        if recent_inverse:
            inverse_rate = Decimal('1') / recent_inverse.rate
            logger.info(f"Using inverse rate for {from_currency}/{to_currency} from {recent_inverse.date}")
            cache.set(cache_key, str(inverse_rate), cls.CACHE_TIMEOUT)
            return inverse_rate

        # If no rate found and it's today, try to fetch from external API
        if date == timezone.now().date():
            try:
                cls.update_exchange_rates([from_currency], [to_currency])
                rate = ExchangeRate.get_rate(from_currency, to_currency, date)
                if rate is not None:
                    cache.set(cache_key, str(rate), cls.CACHE_TIMEOUT)
                    return rate
            except Exception as e:
                logger.error(f"Failed to fetch exchange rate from external API: {e}")

        logger.warning(f"No exchange rate found for {from_currency}/{to_currency} on {date}")
        return None

    @classmethod
    def convert_amount(cls, amount, from_currency, to_currency, date=None):
        """Convert an amount from one currency to another"""
        if amount == 0:
            return Decimal('0')

        # Special handling for GBp conversions
        if from_currency == 'GBp' or to_currency == 'GBp':
            return cls.convert_amount_with_normalization(amount, from_currency, to_currency, date)

        # Validate currencies exist in our system
        if not cls._validate_currency(from_currency):
            raise ValueError(f"Currency '{from_currency}' is not supported or active")

        if not cls._validate_currency(to_currency):
            raise ValueError(f"Currency '{to_currency}' is not supported or active")

        rate = cls.get_exchange_rate(from_currency, to_currency, date)
        if rate is None:
            raise ValueError(f"No exchange rate available for {from_currency}/{to_currency}")

        return amount * rate

    @classmethod
    def _validate_currency(cls, currency_code):
        """Validate that a currency is active in our system"""
        # Special case for GBp - it's valid even if not in the database
        if currency_code == 'GBp':  # Remove .upper() here too
            return True
        return Currency.objects.filter(code=currency_code, is_active=True).exists()

    @classmethod
    def update_exchange_rates(cls, base_currencies=None, target_currencies=None):
        """
        Fetch latest exchange rates from external API.
        This example uses exchangerate-api.com (free tier available)
        """
        if base_currencies is None:
            # Only use active currencies
            base_currencies = list(Currency.objects.filter(is_active=True).values_list('code', flat=True))

        if target_currencies is None:
            # Only use active currencies
            target_currencies = list(Currency.objects.filter(is_active=True).values_list('code', flat=True))

        if not base_currencies or not target_currencies:
            logger.warning("No active currencies found for exchange rate update")
            return

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

                # FIX: Handle both API versions
                # v6 API (paid) uses 'conversion_rates'
                # v4 API (free) uses 'rates'
                rates = data.get('conversion_rates') or data.get('rates', {})

                if not rates:
                    logger.error(f"No rates found in API response for {base}")
                    continue

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
                logger.error(f"Unexpected error updating exchange rates for {base}: {e}")

    @classmethod
    def get_portfolio_value_in_currency(cls, portfolio, target_currency, date=None):
        """
        Get portfolio value converted to target currency
        """
        holdings = portfolio.get_holdings()
        total_value = Decimal('0')

        for holding in holdings.values():
            # FIXED: holding['security'] is a Security MODEL OBJECT, not a dict
            security = holding['security']  # This is a Security model instance
            security_currency = security.currency or 'USD'  # Access currency attribute directly
            current_value = Decimal(str(holding['current_value']))

            if security_currency == target_currency:
                total_value += current_value
            else:
                converted_value = cls.convert_amount(
                    current_value, security_currency, target_currency, date
                )
                total_value += converted_value

        # Add cash balance
        if hasattr(portfolio, 'cash_account'):
            cash_currency = portfolio.cash_account.currency or portfolio.base_currency
            cash_balance = portfolio.cash_account.balance

            if cash_currency == target_currency:
                total_value += cash_balance
            else:
                converted_cash = cls.convert_amount(
                    cash_balance, cash_currency, target_currency, date
                )
                total_value += converted_cash

        return total_value

    @classmethod
    def get_currency_exposure(cls, portfolio):
        """
        Calculate the currency exposure of a portfolio
        Returns dict with currency as key and exposure amount as value
        Handles currency normalization (e.g., GBp -> GBP conversion)
        """
        exposure = {}

        # Get holdings currency exposure
        holdings = portfolio.get_holdings()
        logger.info(f"Portfolio {portfolio.id} holdings count: {len(holdings)}")

        for holding in holdings.values():
            security = holding['security']  # Security model instance
            original_currency = security.currency or 'USD'
            current_value = Decimal(str(holding['current_value']))

            # Normalize currency (converts GBp to GBP with proper factor)
            normalized_currency, conversion_factor = cls.normalize_currency_code(original_currency)

            # Convert the amount using the normalization factor
            normalized_amount = current_value * conversion_factor
            logger.info(
                f"Security {security.symbol}: {original_currency} {current_value} -> {normalized_currency} {normalized_amount}")

            if normalized_currency not in exposure:
                exposure[normalized_currency] = Decimal('0')
            exposure[normalized_currency] += normalized_amount

        # Add cash balance - WITH DEBUGGING
        if hasattr(portfolio, 'cash_account'):
            cash_currency = portfolio.cash_account.currency or portfolio.currency
            cash_balance = portfolio.cash_account.balance

            logger.info(f"Cash account found: {cash_currency} {cash_balance}")

            # Normalize cash currency too
            normalized_cash_currency, cash_conversion_factor = cls.normalize_currency_code(cash_currency)
            normalized_cash_amount = cash_balance * cash_conversion_factor

            logger.info(
                f"Cash normalized: {cash_currency} {cash_balance} -> {normalized_cash_currency} {normalized_cash_amount}")

            if normalized_cash_currency not in exposure:
                exposure[normalized_cash_currency] = Decimal('0')
            exposure[normalized_cash_currency] += normalized_cash_amount
        else:
            logger.warning(f"Portfolio {portfolio.id} has no cash_account!")

        logger.info(f"Final exposure: {exposure}")
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

    @classmethod
    def normalize_currency_code(cls, currency_code):
        """
        Normalize currency codes to handle special cases like GBp (pence)
        Returns tuple: (normalized_currency, conversion_factor)
        """
        if not currency_code:
            return 'USD', Decimal('1')

        # First strip whitespace
        currency_code = currency_code.strip()

        # Handle UK pence (GBp) BEFORE uppercasing
        if currency_code == 'GBp':
            return 'GBP', Decimal('0.01')  # 1 pence = 0.01 pounds

        # Now uppercase for other checks
        currency_code = currency_code.upper()

        if currency_code == 'GBP':
            return 'GBP', Decimal('1')  # 1 pound = 1 pound

        # Handle other potential special cases
        elif currency_code in ['USD', 'EUR', 'JPY', 'CHF', 'CAD', 'AUD', 'CNY', 'HKD', 'SGD', 'INR', 'BRL']:
            return currency_code, Decimal('1')

        # Default case
        return currency_code, Decimal('1')

    @classmethod
    def convert_amount_with_normalization(cls, amount, from_currency, to_currency, date=None):
        """
        Convert amount between currencies with automatic normalization for special cases like GBp
        """
        if amount == 0:
            return Decimal('0')

        # Normalize currencies
        from_currency_norm, from_factor = cls.normalize_currency_code(from_currency)
        to_currency_norm, to_factor = cls.normalize_currency_code(to_currency)

        # Apply pence conversion if needed
        normalized_amount = amount * from_factor

        # If both currencies are the same after normalization, just return the normalized amount
        if from_currency_norm == to_currency_norm:
            return normalized_amount / to_factor

        # Get exchange rate between normalized currencies
        rate = cls.get_exchange_rate(from_currency_norm, to_currency_norm, date)
        if rate is None:
            raise ValueError(f"No exchange rate available for {from_currency_norm}/{to_currency_norm}")

        # Convert and apply target factor
        converted_amount = normalized_amount * rate
        return converted_amount / to_factor


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