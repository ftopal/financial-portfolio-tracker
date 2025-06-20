from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, DecimalField


# Keep your existing Portfolio and AssetCategory models
class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'name']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        # Ensure only one default portfolio per user
        if self.is_default:
            Portfolio.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def get_holdings(self):
        """Calculate current holdings from transactions"""
        from django.db.models import Sum, F, Q, DecimalField

        # Get all transactions for this portfolio
        holdings = {}

        # Aggregate transactions by security
        transactions = self.transactions.select_related('security').order_by('transaction_date')

        for transaction in transactions:
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
                    'buy_lots': []  # For FIFO calculation
                }

            holdings[security_id]['transactions'].append(transaction)

            if transaction.transaction_type == 'BUY':
                holdings[security_id]['quantity'] += transaction.quantity
                holdings[security_id]['total_cost'] += transaction.total_value
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
                holdings[security_id]['total_dividends'] += transaction.total_value

        # Calculate current metrics for each holding
        for security_id, data in holdings.items():
            if data['quantity'] > 0:
                # Calculate average cost for remaining shares
                remaining_cost = sum(
                    lot['remaining'] * lot['price']
                    for lot in data['buy_lots']
                    if lot['remaining'] > 0
                )
                data['avg_cost'] = remaining_cost / data['quantity'] if data['quantity'] > 0 else 0
                data['current_value'] = data['quantity'] * data['security'].current_price
                data['unrealized_gains'] = data['current_value'] - remaining_cost
                data['total_gains'] = data['realized_gains'] + data['unrealized_gains']

        # Filter out positions with 0 quantity
        return {k: v for k, v in holdings.items() if v['quantity'] > 0}

    def get_summary(self):
        """Get portfolio summary statistics"""
        holdings = self.get_holdings()

        total_value = sum(h['current_value'] for h in holdings.values())
        total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings.values())
        total_gains = sum(h['total_gains'] for h in holdings.values())
        total_dividends = sum(h['total_dividends'] for h in holdings.values())

        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_gains': total_gains,
            'total_dividends': total_dividends,
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
        """Calculate total transaction value including fees"""
        if self.transaction_type == 'BUY':
            return (self.quantity * self.price) + self.fees
        elif self.transaction_type == 'SELL':
            return (self.quantity * self.price) - self.fees
        elif self.transaction_type == 'DIVIDEND':
            return self.quantity * (self.dividend_per_share or Decimal('0'))
        elif self.transaction_type == 'FEE':
            return -self.fees
        elif self.transaction_type == 'INTEREST':
            return self.quantity  # Quantity represents the interest amount
        return Decimal('0')

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validate transaction date not in future
        if self.transaction_date > timezone.now():
            raise ValidationError("Transaction date cannot be in the future.")

        # Validate dividend fields
        if self.transaction_type == 'DIVIDEND' and not self.dividend_per_share:
            raise ValidationError("Dividend per share is required for dividend transactions.")

        # Validate split ratio
        if self.transaction_type == 'SPLIT' and not self.split_ratio:
            raise ValidationError("Split ratio is required for stock split transactions.")


class PriceHistory(models.Model):
    """Historical price data for securities"""
    security = models.ForeignKey(Security, on_delete=models.CASCADE, related_name='price_history')
    date = models.DateTimeField(db_index=True)

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