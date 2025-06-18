from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, DecimalField

ASSET_TYPE_CHOICES = [
    ('STOCK', 'Stock'),
    ('BOND', 'Bond'),
    ('SAVINGS', 'Savings Account'),
    ('CRYPTO', 'Cryptocurrency'),
    ('REAL_ESTATE', 'Real Estate'),
    ('ETF', 'ETF'),
    ('MUTUAL_FUND', 'Mutual Fund'),
    ('OTHER', 'Other'),
]


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'name']  # Prevent duplicate portfolio names per user
        ordering = ['-created_at']  # Newest first

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class AssetCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Asset Categories"


class Stock(models.Model):
    """Master stock information with current price"""
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, default='STOCK')

    # Additional stock information
    exchange = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    country = models.CharField(max_length=50, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=100, blank=True)

    # Price information
    current_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0'))]
    )
    last_updated = models.DateTimeField(default=timezone.now)

    # Market data
    market_cap = models.BigIntegerField(null=True, blank=True)
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    day_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    day_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    week_52_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    week_52_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)  # For delisted stocks

    class Meta:
        ordering = ['symbol']

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class Asset(models.Model):
    ASSET_TYPES = ASSET_TYPE_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assets')
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='assets')
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)
    stock = models.ForeignKey(
        'Stock',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets'
    )
    purchase_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,  # Changed from 2 to 4
        validators=[MinValueValidator(Decimal('0.0001'))]  # Must be greater than 0
    )
    purchase_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.symbol})" if self.symbol else self.name

    @property
    def total_value(self):
        return self.current_price * self.quantity

    @property
    def gain_loss(self):
        return (self.current_price - self.purchase_price) * self.quantity

    @property
    def gain_loss_percentage(self):
        if self.purchase_price:
            return ((self.current_price - self.purchase_price) / self.purchase_price) * 100
        return 0

    @property
    def current_price(self):
        """Get current price from associated stock"""
        return self.stock.current_price if self.stock else self.purchase_price

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.purchase_date and self.purchase_date > timezone.now().date():
            raise ValidationError("Purchase date cannot be in the future.")


class OldTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('DIVIDEND', 'Dividend'),
        ('INTEREST', 'Interest'),
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    date = models.DateField()
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0'))]
    )
    price_per_unit = models.DecimalField(max_digits=14, decimal_places=2)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.asset.name} - {self.date}"

    @property
    def total_value(self):
        return (self.quantity * self.price_per_unit) + self.fees


class PriceHistory(models.Model):
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='price_history',
        null=True,  # Add this
        blank=True  # Add this
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='price_history'
    )
    date = models.DateTimeField(default=timezone.now)
    price = models.DecimalField(max_digits=14, decimal_places=4)
    volume = models.BigIntegerField(null=True, blank=True)

    class Meta:
        # Remove the unique_together for now since we're transitioning
        # unique_together = ['stock', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['asset', 'date']),  # Keep index for asset too
        ]

    def __str__(self):
        if self.stock:
            return f"{self.stock.symbol} - {self.date.date()} - ${self.price}"
        elif self.asset:
            return f"{self.asset.name} - {self.date.date()} - ${self.price}"
        return f"Price History - {self.date.date()} - ${self.price}"


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