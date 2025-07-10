from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from django.contrib import messages
from .models import Security, Portfolio, Transaction, AssetCategory, PriceHistory, RealEstateAsset, \
    PortfolioCashAccount, CashTransaction, UserPreferences
from .services.security_import_service import SecurityImportService
from .models_currency import Currency, ExchangeRate
import logging

logger = logging.getLogger(__name__)

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
    list_display = ('symbol', 'name', 'security_type', 'current_price', 'currency', 'exchange', 'is_active',
                    'last_updated')
    list_filter = ('security_type', 'currency', 'exchange', 'is_active', 'data_source')
    search_fields = ('symbol', 'name', 'exchange')
    readonly_fields = ('created_at', 'updated_at', 'last_updated')
    ordering = ('symbol',)

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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-security/', self.admin_site.admin_view(self.import_security_view),
                 name='portfolio_security_import'),
        ]
        return custom_urls + urls

    def import_security_view(self, request):
        """Admin view for importing securities from Yahoo Finance"""
        if request.method == 'POST':
            symbol = request.POST.get('symbol', '').strip().upper()

            if not symbol:
                messages.error(request, 'Please enter a valid symbol.')
                return render(request, 'admin/portfolio/security/import_form.html')

            try:
                service = SecurityImportService()
                result = service.search_and_import_security(symbol)

                if result.get('error'):
                    messages.error(request, f"Import failed: {result['error']}")
                elif result.get('exists'):
                    messages.warning(request, f"Security {symbol} already exists in the database.")
                else:
                    security = result.get('security')
                    messages.success(request, f"Successfully imported {security.symbol} - {security.name}")

            except Exception as e:
                logger.error(f"Admin import error for {symbol}: {str(e)}")
                messages.error(request, f"Import failed: {str(e)}")

            return HttpResponseRedirect('../')

        return render(request, 'admin/portfolio/security/import_form.html')


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