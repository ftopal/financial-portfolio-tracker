from django.contrib import admin
from .models import *
from .models_currency import Currency, ExchangeRate

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['security', 'transaction_type', 'transaction_date', 'quantity', 'price', 'total_value']
    list_filter = ['transaction_type', 'transaction_date', 'security']
    search_fields = ['security__symbol', 'security__name', 'notes']
    date_hierarchy = 'transaction_date'
    readonly_fields = ['total_value', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('portfolio', 'security', 'transaction_type', 'transaction_date')
        }),
        ('Transaction Details', {
            'fields': ('quantity', 'price', 'fees', 'total_value')
        }),
        ('Additional Information', {
            'fields': ('dividend_per_share', 'split_ratio', 'notes', 'reference_number')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['security', 'date', 'close_price', 'volume']
    list_filter = ['security', 'date']
    date_hierarchy = 'date'


@admin.register(Security)
class SecurityAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'security_type', 'current_price', 'last_updated']
    list_filter = ['security_type', 'exchange', 'is_active', 'sector']
    search_fields = ['symbol', 'name']
    readonly_fields = ['created_at', 'updated_at', 'last_updated']

    fieldsets = (
        ('Basic Information', {
            'fields': ('symbol', 'name', 'security_type', 'exchange', 'currency')
        }),
        ('Market Data', {
            'fields': ('current_price', 'last_updated', 'market_cap', 'volume',
                       'day_high', 'day_low', 'week_52_high', 'week_52_low')
        }),
        ('Classification', {
            'fields': ('sector', 'industry', 'category')
        }),
        ('Metadata', {
            'fields': ('is_active', 'data_source', 'created_at', 'updated_at')
        }),
    )


@admin.register(RealEstateAsset)
class RealEstateAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'purchase_price', 'current_value', 'unrealized_gain']
    list_filter = ['property_type', 'city', 'country']
    search_fields = ['name', 'address', 'city']
    readonly_fields = ['unrealized_gain', 'unrealized_gain_pct', 'created_at', 'updated_at']


# Add these to your backend/portfolio/admin.py file

@admin.register(PortfolioCashAccount)
class PortfolioCashAccountAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'balance', 'currency', 'updated_at']
    list_filter = ['currency', 'created_at']
    search_fields = ['portfolio__name', 'portfolio__user__username']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Account Information', {
            'fields': ('portfolio', 'currency', 'balance')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ['cash_account', 'transaction_type', 'amount', 'balance_after',
                    'transaction_date', 'is_auto_deposit']
    list_filter = ['transaction_type', 'is_auto_deposit', 'transaction_date']
    search_fields = ['cash_account__portfolio__name', 'description', 'user__username']
    date_hierarchy = 'transaction_date'
    readonly_fields = ['balance_after', 'created_at', 'updated_at']

    fieldsets = (
        ('Transaction Information', {
            'fields': ('cash_account', 'user', 'transaction_type', 'transaction_date')
        }),
        ('Financial Details', {
            'fields': ('amount', 'balance_after', 'description')
        }),
        ('Related Information', {
            'fields': ('related_transaction', 'is_auto_deposit')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'auto_deposit_enabled', 'auto_deposit_mode',
                    'show_cash_warnings', 'default_currency']
    list_filter = ['auto_deposit_enabled', 'auto_deposit_mode', 'default_currency']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Cash Management', {
            'fields': ('auto_deposit_enabled', 'auto_deposit_mode', 'show_cash_warnings')
        }),
        ('Display Preferences', {
            'fields': ('default_currency',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'decimal_places', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']
    ordering = ['code']

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'date', 'source']
    list_filter = ['from_currency', 'to_currency', 'source', 'date']
    search_fields = ['from_currency', 'to_currency']
    date_hierarchy = 'date'
    ordering = ['-date', 'from_currency', 'to_currency']