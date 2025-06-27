from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class Currency(models.Model):
    """Supported currencies in the system"""
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    decimal_places = models.IntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Currencies"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ExchangeRate(models.Model):
    """Historical exchange rates between currencies"""
    from_currency = models.CharField(max_length=3, db_index=True)
    to_currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal('0.00000001'))]
    )
    date = models.DateField(db_index=True)
    source = models.CharField(max_length=50, default='manual')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['from_currency', 'to_currency', 'date']
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', '-date']),
            models.Index(fields=['date', 'from_currency', 'to_currency']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.from_currency}/{self.to_currency} - {self.rate} ({self.date})"

    @classmethod
    def get_rate(cls, from_currency, to_currency, date=None):
        """Get exchange rate for a specific date (or latest if not specified)"""
        if from_currency == to_currency:
            return Decimal('1')

        if date is None:
            date = timezone.now().date()

        # Try direct rate
        rate = cls.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            date__lte=date
        ).order_by('-date').first()

        if rate:
            return rate.rate

        # Try inverse rate
        inverse_rate = cls.objects.filter(
            from_currency=to_currency,
            to_currency=from_currency,
            date__lte=date
        ).order_by('-date').first()

        if inverse_rate:
            return Decimal('1') / inverse_rate.rate

        # Try triangulation through USD
        if from_currency != 'USD' and to_currency != 'USD':
            from_usd = cls.get_rate('USD', from_currency, date)
            to_usd = cls.get_rate('USD', to_currency, date)
            if from_usd and to_usd:
                return to_usd / from_usd

        return None