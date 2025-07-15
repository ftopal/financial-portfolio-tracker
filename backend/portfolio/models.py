from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, Q, Case, When, DecimalField
from .models_currency import Currency, ExchangeRate
import logging

logger = logging.getLogger(__name__)


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    base_currency = models.CharField(
        max_length=3,
        default='USD',  # This ensures existing portfolios will have USD
        help_text='Base currency for this portfolio'
    )

    class Meta:
        unique_together = ['user', 'name']
        ordering = ['-created_at']

    def get_holdings_cached(self):
        """Get holdings with request-level caching"""
        if not hasattr(self, '_cached_holdings'):
            self._cached_holdings = self.get_holdings()
        return self._cached_holdings

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        """Override save to create cash account automatically"""
        is_new = self.pk is None

        # Ensure only one default portfolio per user
        if self.is_default:
            Portfolio.objects.filter(user=self.user, is_default=True).update(is_default=False)

        super().save(*args, **kwargs)

        # Create cash account for new portfolios
        if is_new:
            PortfolioCashAccount.objects.create(
                portfolio=self,
                currency=self.base_currency or self.currency  # Use base_currency first
            )

    def get_holdings(self):
        """Calculate current holdings based on transactions - with currency conversion"""
        holdings = {}
        portfolio_currency = self.base_currency or self.currency
        processed_transactions = set()

        transactions = self.transactions.filter(
            transaction_type__in=['BUY', 'SELL', 'DIVIDEND', 'SPLIT']
        ).select_related('security').order_by('transaction_date')

        for transaction in transactions:
            if transaction.id in processed_transactions:
                continue
            processed_transactions.add(transaction.id)

            security_id = transaction.security.id

            if security_id not in holdings:
                holdings[security_id] = {
                    'security': transaction.security,
                    'quantity': Decimal('0'),
                    'total_cost': Decimal('0'),
                    'total_proceeds': Decimal('0'),
                    'total_dividends': Decimal('0'),
                    'realized_gains': Decimal('0'),
                    'transactions': [],
                    'buy_lots': [],
                    'net_cash_invested': Decimal('0'),
                    'total_cost_base_currency': Decimal('0'),  # Track in portfolio currency
                }

            holdings[security_id]['transactions'].append(transaction)

            if transaction.transaction_type == 'BUY':
                holdings[security_id]['quantity'] += transaction.quantity
                holdings[security_id]['total_cost'] += transaction.quantity * transaction.price

                # Track net cash invested in base currency
                if transaction.base_amount:
                    holdings[security_id]['net_cash_invested'] += transaction.base_amount
                    # For cost basis, we need to track without fees
                    cost_without_fees_base = (transaction.quantity * transaction.price) * (
                                transaction.exchange_rate or Decimal('1'))
                    holdings[security_id]['total_cost_base_currency'] += cost_without_fees_base
                else:
                    holdings[security_id]['net_cash_invested'] += transaction.total_value
                    holdings[security_id]['total_cost_base_currency'] += transaction.quantity * transaction.price

                # Add to buy lots for FIFO tracking
                holdings[security_id]['buy_lots'].append({
                    'date': transaction.transaction_date,
                    'quantity': transaction.quantity,
                    'price': transaction.price,
                    'remaining': transaction.quantity
                })

            elif transaction.transaction_type == 'SELL':
                holdings[security_id]['quantity'] -= transaction.quantity
                holdings[security_id]['total_proceeds'] += transaction.total_value

                if transaction.base_amount:
                    holdings[security_id]['net_cash_invested'] -= transaction.base_amount
                else:
                    holdings[security_id]['net_cash_invested'] -= transaction.total_value

                # Calculate realized gains using FIFO
                remaining_to_sell = transaction.quantity
                for lot in holdings[security_id]['buy_lots']:
                    if remaining_to_sell <= 0:
                        break
                    if lot['remaining'] > 0:
                        sold_from_lot = min(lot['remaining'], remaining_to_sell)
                        cost_basis = sold_from_lot * lot['price']
                        proceeds = sold_from_lot * transaction.price
                        holdings[security_id]['realized_gains'] += (proceeds - cost_basis)
                        lot['remaining'] -= sold_from_lot
                        remaining_to_sell -= sold_from_lot


            elif transaction.transaction_type == 'DIVIDEND':
                # Calculate actual dividend amount (NET of fees) in portfolio base currency
                if transaction.dividend_per_share:
                    gross_dividend = transaction.quantity * transaction.dividend_per_share
                else:
                    gross_dividend = transaction.price or Decimal('0')

                # Subtract fees to get net dividend
                net_dividend = gross_dividend - transaction.fees

                # Convert to base currency if needed
                if transaction.base_amount:
                    # If we have base_amount, we need to recalculate it for net dividend
                    if transaction.exchange_rate and transaction.exchange_rate != Decimal('1'):
                        dividend_amount_base_currency = net_dividend * transaction.exchange_rate
                    else:
                        dividend_amount_base_currency = net_dividend
                else:
                    dividend_amount_base_currency = net_dividend

                holdings[security_id]['total_dividends'] += dividend_amount_base_currency

                # ✅ CRITICAL FIX: Dividends reduce the effective cost basis by NET amount
                holdings[security_id]['total_cost_base_currency'] -= dividend_amount_base_currency
                holdings[security_id]['net_cash_invested'] -= dividend_amount_base_currency

                # Also reduce the original currency cost by net dividend
                holdings[security_id]['total_cost'] -= net_dividend


            elif transaction.transaction_type == 'SPLIT':
                # Handle stock splits correctly
                if transaction.split_ratio:
                    try:
                        # Parse split ratio (e.g., "4:1" means 4 new shares for 1 old share)
                        ratio_parts = transaction.split_ratio.split(':')
                        if len(ratio_parts) == 2:
                            new_shares = Decimal(str(ratio_parts[0]))
                            old_shares = Decimal(str(ratio_parts[1]))

                            if old_shares > 0:
                                # Calculate the split multiplier
                                split_multiplier = new_shares / old_shares
                                # CORRECT LOGIC:
                                # holdings[security_id]['quantity'] contains quantity from all previous transactions
                                # This is the quantity we had BEFORE this split
                                quantity_before_split = holdings[security_id]['quantity']

                                # Apply the split: multiply existing quantity by split ratio
                                new_total_quantity = quantity_before_split * split_multiplier
                                holdings[security_id]['quantity'] = new_total_quantity

                                # CRITICAL: Adjust the buy lots for FIFO tracking
                                # All historical buy lots need to be adjusted for the split
                                for lot in holdings[security_id]['buy_lots']:
                                    lot['quantity'] *= split_multiplier
                                    lot['remaining'] *= split_multiplier
                                    lot['price'] /= split_multiplier  # Price per share decreases proportionally

                                # NOTE: total_cost and total_cost_base_currency remain unchanged
                                # because the total invested amount doesn't change in a split


                    except (ValueError, IndexError, ZeroDivisionError) as e:
                        print(f"Error parsing split ratio {transaction.split_ratio}: {e}")
                        # If parsing fails, fall back to simply adding the additional shares
                        # This maintains backward compatibility but may not be accurate
                        holdings[security_id]['quantity'] += transaction.quantity

        # Calculate current metrics for each holding
        for security_id, data in holdings.items():
            if data['quantity'] > 0:
                # Average cost in security currency
                if data['total_cost'] > 0:
                    data['avg_cost'] = data['total_cost'] / data['quantity']
                else:
                    data['avg_cost'] = Decimal('0')

                # Average cost in portfolio currency
                if data['total_cost_base_currency'] > 0:
                    data['avg_cost_base_currency'] = data['total_cost_base_currency'] / data['quantity']
                else:
                    data['avg_cost_base_currency'] = Decimal('0')

                # Current value in security currency
                data['current_value'] = data['quantity'] * data['security'].current_price

                # Convert current value to portfolio currency
                if data['security'].currency != portfolio_currency:
                    from .services.currency_service import CurrencyService
                    try:
                        data['current_value_base_currency'] = CurrencyService.convert_amount(
                            data['current_value'],
                            data['security'].currency,
                            portfolio_currency
                        )
                    except:
                        # Fallback to last exchange rate
                        last_buy = next((t for t in reversed(data['transactions']) if t.transaction_type == 'BUY'),
                                        None)
                        if last_buy and last_buy.exchange_rate:
                            data['current_value_base_currency'] = data['current_value'] * last_buy.exchange_rate
                        else:
                            data['current_value_base_currency'] = data['current_value']
                else:
                    data['current_value_base_currency'] = data['current_value']

                # Calculate unrealized gains in portfolio currency
                data['unrealized_gains'] = data['current_value_base_currency'] - data['total_cost_base_currency']
                data['total_gains'] = data['realized_gains'] + data['unrealized_gains']

        # Filter out positions with 0 quantity
        return {k: v for k, v in holdings.items() if v['quantity'] > 0}

    def get_total_value(self):
        """Get total portfolio value including cash - all in base currency"""
        holdings = self.get_holdings()
        # Use current_value_base_currency for accurate total
        holdings_value = sum(h.get('current_value_base_currency', h['current_value']) for h in holdings.values())
        cash_value = self.cash_account.balance if hasattr(self, 'cash_account') else Decimal('0')
        return holdings_value + cash_value

    def get_summary_with_cash(self):
        """Get portfolio summary including cash position"""
        summary = self.get_summary()
        if hasattr(self, 'cash_account'):
            summary['cash_balance'] = float(self.cash_account.balance)
            summary['total_value_with_cash'] = float(self.get_total_value())
        return summary

    def get_summary(self):
        """Get portfolio summary statistics - all values in base currency"""
        holdings = self.get_holdings()

        # Calculate totals using base currency values
        total_value = sum(h.get('current_value_base_currency', h['current_value']) for h in holdings.values())
        total_cost = sum(h.get('total_cost_base_currency', h['total_cost']) for h in holdings.values())
        total_gains = sum(h['unrealized_gains'] for h in holdings.values())
        total_dividends = sum(h['total_dividends'] for h in holdings.values())
        total_realized_gains = sum(h['realized_gains'] for h in holdings.values())

        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_gains': total_gains,
            'total_dividends': total_dividends,
            'total_realized_gains': total_realized_gains,
            'total_return': total_gains + total_dividends,
            'total_return_pct': ((total_gains + total_dividends) / total_cost * 100) if total_cost > 0 else 0,
            'holdings_count': len(holdings)
        }


class AssetCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3B82F6')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Asset Categories"
        ordering = ['name']


class Security(models.Model):
    """Universal model for all tradeable securities"""
    SECURITY_TYPES = [
        ('STOCK', 'Stock'),
        ('ETF', 'ETF'),
        ('CRYPTO', 'Cryptocurrency'),
        ('BOND', 'Bond'),
        ('MUTUAL_FUND', 'Mutual Fund'),
        ('COMMODITY', 'Commodity'),
        ('INDEX', 'Index'),
        ('OPTION', 'Option'),
    ]

    DATA_SOURCES = [
        ('yahoo', 'Yahoo Finance'),
        ('coingecko', 'CoinGecko'),
        ('manual', 'Manual Entry'),
        ('alpha_vantage', 'Alpha Vantage'),
    ]

    # Basic identification
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    security_type = models.CharField(max_length=20, choices=SECURITY_TYPES, db_index=True)

    # Trading information
    exchange = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    country = models.CharField(max_length=100, blank=True)

    # Current market data
    current_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,  # Support crypto with small values
        validators=[MinValueValidator(Decimal('0'))]
    )
    last_updated = models.DateTimeField(default=timezone.now)

    # Additional market data
    market_cap = models.BigIntegerField(null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    day_high = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    day_low = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    week_52_high = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    week_52_low = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    # Fundamental data (mainly for stocks/ETFs)
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    dividend_yield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Classification
    sector = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, blank=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    data_source = models.CharField(max_length=20, choices=DATA_SOURCES, default='yahoo')

    # For options
    underlying_security = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name='derivatives')
    expiration_date = models.DateField(null=True, blank=True)
    strike_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    option_type = models.CharField(max_length=4, choices=[('CALL', 'Call'), ('PUT', 'Put')], blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Securities"
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['symbol', 'security_type']),
            models.Index(fields=['security_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    @property
    def price_change(self):
        """Calculate daily price change"""
        if self.day_high and self.day_low:
            return self.current_price - ((self.day_high + self.day_low) / 2)
        return Decimal('0')

    @property
    def price_change_pct(self):
        """Calculate daily price change percentage"""
        if self.day_high and self.day_low:
            avg_price = (self.day_high + self.day_low) / 2
            return ((self.current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        return Decimal('0')


class Transaction(models.Model):
    """Record of all portfolio transactions"""
    TRANSACTION_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('DIVIDEND', 'Dividend'),
        ('SPLIT', 'Stock Split'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('FEE', 'Fee'),
        ('INTEREST', 'Interest'),
    ]

    # Core relationships
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='transactions')
    security = models.ForeignKey(Security, on_delete=models.PROTECT, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_transactions')

    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, db_index=True)
    transaction_date = models.DateTimeField(default=timezone.now, db_index=True)
    settlement_date = models.DateTimeField(null=True, blank=True)

    # Currency
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('1'),
        help_text="Exchange rate to portfolio base currency at transaction date"
    )
    base_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total value in portfolio base currency"
    )

    # Amounts
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal('0'))]
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal('0'))]
    )
    fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )

    # For dividends
    dividend_per_share = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # For stock splits
    split_ratio = models.CharField(max_length=20, blank=True)  # e.g., "2:1"

    # Additional info
    notes = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)  # Broker reference

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['portfolio', 'transaction_date']),
            models.Index(fields=['security', 'transaction_type']),
            models.Index(fields=['user', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.security.symbol} - {self.transaction_date.date()}"

    @property
    def total_value(self):
        """Calculate total transaction value in PORTFOLIO BASE CURRENCY including fees"""
        # First calculate the raw value in transaction currency
        if self.transaction_type == 'BUY':
            raw_value = (self.quantity * self.price) + self.fees
        elif self.transaction_type == 'SELL':
            raw_value = (self.quantity * self.price) - self.fees
        elif self.transaction_type == 'DIVIDEND':
            if self.dividend_per_share:
                # For dividends, fees are deducted from the dividend amount
                raw_value = (self.quantity * self.dividend_per_share) - self.fees
            elif self.price and self.quantity:
                # If using price field for total dividend
                raw_value = self.price - self.fees
            else:
                raw_value = Decimal('0')
        elif self.transaction_type == 'SPLIT':
            # Stock splits don't have monetary value
            return Decimal('0')
        elif self.transaction_type == 'FEE':
            raw_value = -self.fees
        elif self.transaction_type == 'INTEREST':
            raw_value = self.quantity
        else:
            raw_value = Decimal('0')

        # If we have a base_amount (converted value), use that
        # base_amount ALREADY includes fees from the save() method
        if self.base_amount:
            return self.base_amount

        # Convert to base currency if needed
        if self.currency != self.portfolio.base_currency and self.exchange_rate:
            return raw_value * self.exchange_rate
        else:
            return raw_value

    @property
    def total_value_transaction_currency(self):
        """Get total value in transaction currency (not converted)"""
        if self.transaction_type == 'BUY':
            return (self.quantity * self.price) + self.fees
        elif self.transaction_type == 'SELL':
            return (self.quantity * self.price) - self.fees
        elif self.transaction_type == 'DIVIDEND':
            if self.dividend_per_share:
                # Subtract fees from dividend amount
                return (self.quantity * self.dividend_per_share) - self.fees
            elif self.price and self.quantity:
                # When using price field for total dividend, subtract fees
                return self.price - self.fees
            elif self.price:
                # If only price is set (total dividend), subtract fees
                return self.price - self.fees
            return Decimal('0')
        elif self.transaction_type == 'SPLIT':
            return Decimal('0')
        elif self.transaction_type == 'FEE':
            return -self.fees
        elif self.transaction_type == 'INTEREST':
            return self.quantity
        return Decimal('0')

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate transaction date not in future
        if self.transaction_date > timezone.now():
            raise ValidationError("Transaction date cannot be in the future.")

        # Validate dividend fields
        if self.transaction_type == 'DIVIDEND':
            if not self.dividend_per_share and self.price and self.quantity:
                # Frontend sends total dividend amount in price field
                # Calculate dividend_per_share from total amount
                if self.quantity > 0:
                    # Round to 4 decimal places to match the field specification
                    calculated_dps = self.price / self.quantity
                    self.dividend_per_share = Decimal(str(round(float(calculated_dps), 4)))
                else:
                    raise ValidationError("Quantity must be greater than 0 for dividend transactions.")
            elif not self.dividend_per_share and not self.price:
                raise ValidationError(
                    "Dividend per share or total dividend amount (price) is required for dividend transactions.")

            # If dividend_per_share is provided, ensure it's properly rounded
            if self.dividend_per_share:
                self.dividend_per_share = Decimal(str(round(float(self.dividend_per_share), 4)))

        # Validate stock split fields
        if self.transaction_type == 'SPLIT':
            if not self.split_ratio:
                raise ValidationError("Split ratio is required for stock split transactions.")
            # Validate split ratio format (e.g., "2:1", "3:2")
            import re
            if not re.match(r'^\d+:\d+$', self.split_ratio):
                raise ValidationError("Split ratio must be in format 'X:Y' (e.g., '2:1')")

    def save(self, *args, **kwargs):
        # Calculate base amount if not provided
        if not self.base_amount and self.portfolio:
            # Use base_currency, not currency
            portfolio_currency = self.portfolio.base_currency or self.portfolio.currency

            if self.currency == portfolio_currency:
                # Calculate total including fees for the base amount
                if self.transaction_type == 'BUY':
                    self.base_amount = (self.quantity * self.price) + self.fees
                elif self.transaction_type == 'SELL':
                    self.base_amount = (self.quantity * self.price) - self.fees
                else:
                    self.base_amount = self.quantity * self.price

                self.exchange_rate = Decimal('1')
            else:
                # Get exchange rate
                from .services.currency_service import CurrencyService
                rate = CurrencyService.get_exchange_rate(
                    self.currency,
                    portfolio_currency,
                    self.transaction_date.date() if hasattr(self.transaction_date, 'date') else self.transaction_date
                )
                if rate:
                    self.exchange_rate = rate
                    # Calculate total including fees for the base amount
                    if self.transaction_type == 'BUY':
                        total_in_transaction_currency = (self.quantity * self.price) + self.fees
                    elif self.transaction_type == 'SELL':
                        total_in_transaction_currency = (self.quantity * self.price) - self.fees
                    else:
                        total_in_transaction_currency = self.quantity * self.price

                    self.base_amount = total_in_transaction_currency * rate

        super().save(*args, **kwargs)


class PriceHistory(models.Model):
    """Historical price data for securities"""
    security = models.ForeignKey(Security, on_delete=models.CASCADE, related_name='price_history')
    date = models.DateTimeField(db_index=True)
    currency = models.CharField(max_length=3, default='USD')

    # Price data
    open_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    high_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    low_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    close_price = models.DecimalField(max_digits=20, decimal_places=8)
    adjusted_close = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    # Volume data
    volume = models.BigIntegerField(null=True, blank=True)

    # Metadata
    data_source = models.CharField(max_length=20, default='yahoo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['security', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['security', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.security.symbol} - {self.date.date()} - ${self.close_price}"


# Keep this for non-tradeable assets
class RealEstateAsset(models.Model):
    """Model for real estate and other non-tradeable assets"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='real_estate_assets')
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=50, default='REAL_ESTATE')

    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)

    # Financial data
    purchase_price = models.DecimalField(max_digits=20, decimal_places=2)
    current_value = models.DecimalField(max_digits=20, decimal_places=2)
    purchase_date = models.DateField()

    # Additional info
    property_type = models.CharField(max_length=50)  # House, Apartment, Land, etc.
    size_sqft = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date']

    def __str__(self):
        return f"{self.name} - {self.city}"

    @property
    def unrealized_gain(self):
        return self.current_value - self.purchase_price

    @property
    def unrealized_gain_pct(self):
        return ((self.current_value - self.purchase_price) / self.purchase_price * 100) if self.purchase_price > 0 else 0


class PortfolioCashAccount(models.Model):
    """Cash account associated with each portfolio"""
    portfolio = models.OneToOneField(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='cash_account'
    )
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.portfolio.name} Cash Account - {self.currency} {self.balance}"

    def has_sufficient_balance(self, amount):
        """Check if account has sufficient balance for a transaction"""
        return self.balance >= amount

    def get_total_value_in_currency(self, target_currency=None):
        """Get total portfolio value in specified currency"""
        if target_currency is None:
            target_currency = self.currency

        from .services.currency_service import CurrencyService
        return CurrencyService.get_portfolio_value_in_currency(self, target_currency)

    def get_holdings_with_currency(self, target_currency=None):
        """Get holdings with values converted to target currency"""
        if target_currency is None:
            target_currency = self.currency

        holdings = self.get_holdings()

        if target_currency == self.currency:
            return holdings

        from .services.currency_service import CurrencyService

        # Convert values to target currency
        for security_id, data in holdings.items():
            security = data['security']
            if security.currency != target_currency:
                # Convert current value
                data['current_value_converted'] = CurrencyService.convert_amount(
                    data['current_value'],
                    security.currency,
                    target_currency
                )
                # Convert other monetary values
                data['total_dividends_converted'] = CurrencyService.convert_amount(
                    data['total_dividends'],
                    security.currency,
                    target_currency
                )
            else:
                data['current_value_converted'] = data['current_value']
                data['total_dividends_converted'] = data['total_dividends']

        return holdings

    def update_balance(self, amount):
        """
        Update balance by amount - DEPRECATED
        Use recalculate_balances() instead for accurate balance tracking
        """
        # For backward compatibility, we'll just trigger a full recalculation
        self.recalculate_balances()
        return self.balance

    def recalculate_balances(self):
        """
        Recalculate balance_after for all transactions in chronological order
        """
        from decimal import Decimal

        try:
            # Get all transactions ordered by transaction date and creation time
            transactions = self.transactions.order_by('transaction_date', 'created_at')

            running_balance = Decimal('0')

            # Use bulk_update to avoid triggering signals
            transactions_to_update = []

            for transaction in transactions:
                running_balance += transaction.amount

                # Check if balance_after needs updating
                if transaction.balance_after != running_balance:
                    transaction.balance_after = running_balance
                    transactions_to_update.append(transaction)

            # Bulk update all transactions at once (doesn't trigger signals)
            if transactions_to_update:
                # Use the model class from the transaction instance
                transaction.__class__.objects.bulk_update(transactions_to_update, ['balance_after'])

            # Update the cash account's current balance
            if self.balance != running_balance:
                self.balance = running_balance
                # Use a try-catch to handle the case where the instance might be in the process of being deleted
                try:
                    self.save(update_fields=['balance'])
                except Exception as e:
                    # Log the error but don't re-raise it to avoid blocking deletion processes
                    logger.warning(f"Failed to save cash account balance during recalculation: {e}")
                    # If save with update_fields fails, it might be because the object is being deleted
                    # In that case, we can skip updating the balance since it won't matter

            return running_balance

        except Exception as e:
            # Log any errors that occur during balance recalculation
            logger.error(f"Error during balance recalculation for cash account {self.id}: {e}")
            # Re-raise the exception unless it's a specific database error that indicates deletion
            if "did not affect any rows" in str(e) or "DoesNotExist" in str(e):
                logger.info(f"Skipping balance recalculation for cash account {self.id} - likely being deleted")
                return self.balance
            else:
                raise

    def get_balance_verification(self):
        """
        Verify that the current balance matches the sum of all transactions
        """
        from decimal import Decimal
        from django.db.models import Sum

        calculated_balance = self.transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        difference = self.balance - calculated_balance

        return {
            'stored_balance': float(self.balance),
            'calculated_balance': float(calculated_balance),
            'difference': float(difference),
            'is_consistent': abs(difference) < Decimal('0.01')  # Allow for minor rounding
        }


class CashTransaction(models.Model):
    """Record of all cash movements in portfolio"""
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('BUY', 'Security Purchase'),
        ('SELL', 'Security Sale'),
        ('DIVIDEND', 'Dividend Payment'),
        ('INTEREST', 'Interest Payment'),
        ('FEE', 'Fee'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('SPLIT', 'Stock Split'),
    ]

    # Relationships
    cash_account = models.ForeignKey(
        PortfolioCashAccount,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cash_transactions'
    )
    related_transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_transaction'
    )

    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, db_index=True)
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Positive for inflows, negative for outflows"
    )
    balance_after = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Cash balance after this transaction"
    )

    # Additional info
    description = models.TextField(blank=True)
    transaction_date = models.DateTimeField(default=timezone.now, db_index=True)
    is_auto_deposit = models.BooleanField(
        default=False,
        help_text="True if this was an automatic deposit for insufficient funds"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['cash_account', 'transaction_date']),
            models.Index(fields=['transaction_type', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.transaction_date.date()}"

    def save(self, *args, **kwargs):
        # Auto-set balance_after if not provided
        if not self.balance_after:
            self.balance_after = self.cash_account.balance + self.amount
        super().save(*args, **kwargs)


class PortfolioXIRRCache(models.Model):
    """Cache for portfolio-level XIRR calculations"""
    portfolio = models.OneToOneField(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='xirr_cache'
    )
    xirr_value = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        help_text="XIRR as decimal (e.g., 0.15 for 15%)"
    )
    last_transaction_id = models.IntegerField(
        null=True,
        help_text="ID of last transaction used in calculation"
    )
    calculation_date = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.portfolio.name} XIRR: {self.xirr_value}"


class AssetXIRRCache(models.Model):
    """Cache for individual asset XIRR calculations"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    security = models.ForeignKey(Security, on_delete=models.CASCADE)
    xirr_value = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        help_text="XIRR as decimal (e.g., 0.15 for 15%)"
    )
    last_transaction_id = models.IntegerField(
        null=True,
        help_text="ID of last transaction for this asset used in calculation"
    )
    calculation_date = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['portfolio', 'security']

    def __str__(self):
        return f"{self.portfolio.name} - {self.security.symbol} XIRR: {self.xirr_value}"


class UserPreferences(models.Model):
    """User preferences for portfolio management"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='portfolio_preferences'
    )

    # Cash management preferences
    auto_deposit_enabled = models.BooleanField(
        default=True,
        help_text="Automatically create deposits when buying with insufficient cash"
    )
    auto_deposit_mode = models.CharField(
        max_length=20,
        choices=[
            ('EXACT', 'Deposit exact amount needed'),
            ('SHORTFALL', 'Deposit only the shortfall'),
        ],
        default='EXACT'
    )
    show_cash_warnings = models.BooleanField(
        default=True,
        help_text="Show warnings when cash balance is low"
    )

    # Display preferences
    default_currency = models.CharField(max_length=3, default='USD')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"{self.user.username} preferences"


class PortfolioValueHistory(models.Model):
    """
    Daily portfolio value snapshots for historical performance tracking.

    This model stores daily portfolio value calculations to enable
    historical performance charts and time-series analysis.
    """

    # Core relationships
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='value_history'
    )

    # Date for this snapshot (stored as date, not datetime for daily aggregation)
    date = models.DateField(db_index=True)

    # Portfolio values in the portfolio's base currency
    total_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total portfolio value including holdings and cash"
    )
    total_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total cost basis of all holdings"
    )
    cash_balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Cash balance in portfolio"
    )

    # Portfolio composition metrics
    holdings_count = models.IntegerField(
        help_text="Number of unique securities with non-zero positions"
    )

    # Performance metrics (calculated fields)
    unrealized_gains = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Unrealized gains/losses (total_value - total_cost - cash_balance)"
    )
    total_return_pct = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Total return percentage since inception"
    )

    # Metadata
    calculation_source = models.CharField(
        max_length=20,
        default='daily_task',
        choices=[
            ('daily_task', 'Daily Automated Task'),
            ('manual_calc', 'Manual Calculation'),
            ('backfill', 'Historical Backfill'),
            ('transaction_trigger', 'Transaction Trigger'),
        ],
        help_text="Source of this calculation"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure only one record per portfolio per date
        unique_together = ['portfolio', 'date']
        ordering = ['-date']

        # Optimize for common queries
        indexes = [
            models.Index(fields=['portfolio', 'date']),
            models.Index(fields=['portfolio', '-date']),  # For latest-first queries
            models.Index(fields=['date']),  # For cross-portfolio date queries
            models.Index(fields=['portfolio', 'calculation_source']),
        ]

        verbose_name = "Portfolio Value History"
        verbose_name_plural = "Portfolio Value History"

    def __str__(self):
        return f"{self.portfolio.name} - {self.date} - ${self.total_value:,.2f}"

    @property
    def holdings_value(self):
        """Calculate value of holdings (excluding cash)"""
        return self.total_value - self.cash_balance

    @property
    def daily_return_pct(self):
        """Calculate daily return percentage (requires previous day's data)"""
        try:
            previous_day = PortfolioValueHistory.objects.filter(
                portfolio=self.portfolio,
                date__lt=self.date
            ).order_by('-date').first()

            if previous_day:
                return ((self.total_value - previous_day.total_value) / previous_day.total_value * 100)
            return Decimal('0')
        except:
            return Decimal('0')

    def save(self, *args, **kwargs):
        """Calculate derived fields before saving"""
        # Calculate unrealized gains
        self.unrealized_gains = self.total_value - self.total_cost - self.cash_balance

        # Calculate total return percentage
        if self.total_cost > 0:
            self.total_return_pct = (self.unrealized_gains / self.total_cost) * 100
        else:
            self.total_return_pct = Decimal('0')

        super().save(*args, **kwargs)

    @classmethod
    def calculate_portfolio_value_for_date(cls, portfolio, target_date):
        """
        Calculate portfolio value for a specific date.

        Args:
            portfolio: Portfolio instance
            target_date: Date to calculate value for (datetime.date)

        Returns:
            dict: Portfolio value data for the date
        """
        from datetime import datetime
        from .services.price_history_service import PriceHistoryService

        # If target_date is a datetime, convert to date
        if isinstance(target_date, datetime):
            target_date = target_date.date()

        # Get all transactions up to and including the target date
        transactions = portfolio.transactions.filter(
            transaction_date__date__lte=target_date
        ).order_by('transaction_date')

        # Calculate holdings as of the target date
        holdings = {}
        cash_balance = Decimal('0')

        for transaction in transactions:
            symbol = transaction.security.symbol

            if symbol not in holdings:
                holdings[symbol] = {
                    'quantity': Decimal('0'),
                    'total_cost': Decimal('0'),
                    'security': transaction.security,
                    'transactions': []
                }

            # Process transaction based on type
            if transaction.transaction_type == 'BUY':
                holdings[symbol]['quantity'] += transaction.quantity
                holdings[symbol]['total_cost'] += transaction.base_amount or (transaction.quantity * transaction.price)
                # Reduce cash for purchases
                cash_balance -= transaction.base_amount or (transaction.quantity * transaction.price)

            elif transaction.transaction_type == 'SELL':
                # Calculate cost basis for sold shares (FIFO)
                sold_quantity = transaction.quantity
                if holdings[symbol]['quantity'] > 0:
                    cost_per_share = holdings[symbol]['total_cost'] / holdings[symbol]['quantity']
                    cost_reduction = min(sold_quantity, holdings[symbol]['quantity']) * cost_per_share
                    holdings[symbol]['total_cost'] -= cost_reduction
                    holdings[symbol]['quantity'] -= sold_quantity

                # Add cash from sales
                cash_balance += transaction.base_amount or (transaction.quantity * transaction.price)

            elif transaction.transaction_type == 'DIVIDEND':
                # Add dividend to cash
                cash_balance += transaction.base_amount or (transaction.quantity * transaction.price)

            # Add transaction to holdings for reference
            holdings[symbol]['transactions'].append(transaction)

        # Get cash account balance if exists
        if hasattr(portfolio, 'cash_account'):
            # Use cash account balance as it's more accurate than transaction-based calculation
            cash_balance = portfolio.cash_account.balance

        # Calculate current values using prices on target_date
        total_value = cash_balance
        total_cost = Decimal('0')
        holdings_count = 0

        for symbol, holding in holdings.items():
            if holding['quantity'] > 0:
                holdings_count += 1
                total_cost += holding['total_cost']

                # Get price for the target date
                price_on_date = PriceHistoryService.get_price_for_date(
                    holding['security'],
                    target_date
                )

                if price_on_date:
                    holding_value = holding['quantity'] * price_on_date
                    total_value += holding_value

        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'cash_balance': cash_balance,
            'holdings_count': holdings_count,
            'unrealized_gains': total_value - total_cost - cash_balance,
            'total_return_pct': (
                        (total_value - total_cost - cash_balance) / total_cost * 100) if total_cost > 0 else Decimal(
                '0'),
        }

    @classmethod
    def create_snapshot(cls, portfolio, target_date, calculation_source='daily_task'):
        """
        Create or update a portfolio value snapshot for a specific date.

        Args:
            portfolio: Portfolio instance
            target_date: Date to create snapshot for
            calculation_source: Source of calculation

        Returns:
            PortfolioValueHistory instance
        """
        # Calculate portfolio value for the date
        value_data = cls.calculate_portfolio_value_for_date(portfolio, target_date)

        # Create or update the snapshot
        snapshot, created = cls.objects.update_or_create(
            portfolio=portfolio,
            date=target_date,
            defaults={
                'total_value': value_data['total_value'],
                'total_cost': value_data['total_cost'],
                'cash_balance': value_data['cash_balance'],
                'holdings_count': value_data['holdings_count'],
                'calculation_source': calculation_source,
            }
        )

        return snapshot


@receiver(post_save, sender=CashTransaction)
def recalculate_on_save(sender, instance, created, **kwargs):
    """
    Recalculate balances whenever a cash transaction is saved
    """
    if created or kwargs.get('update_fields'):
        instance.cash_account.recalculate_balances()


@receiver(post_delete, sender=CashTransaction)
def recalculate_on_delete(sender, instance, **kwargs):
    """
    Recalculate balances whenever a cash transaction is deleted
    """
    # Store the cash account ID before deletion
    cash_account_id = instance.cash_account_id

    def safe_recalculate():
        """
        Safely recalculate balances only if the cash account still exists
        """
        try:
            # Import here to avoid circular imports
            from .models import PortfolioCashAccount

            # Check if the cash account still exists in the database
            # This prevents the error when the entire portfolio (and cash account) is being deleted
            if PortfolioCashAccount.objects.filter(id=cash_account_id).exists():
                cash_account = PortfolioCashAccount.objects.get(id=cash_account_id)
                cash_account.recalculate_balances()
                logger.info(f"Recalculated balances for cash account {cash_account_id} after transaction deletion")
            else:
                logger.info(
                    f"Skipped balance recalculation - cash account {cash_account_id} no longer exists (likely due to portfolio deletion)")
        except Exception as e:
            # Log the error but don't raise it to prevent blocking the deletion process
            logger.warning(
                f"Failed to recalculate balances for cash account {cash_account_id} after transaction deletion: {e}")

    # Use Django's transaction.on_commit to ensure this runs after the delete is committed
    from django.db import transaction
    transaction.on_commit(safe_recalculate)