from django.contrib import admin
from .models import *

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