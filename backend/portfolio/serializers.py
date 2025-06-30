from rest_framework import serializers
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, RealEstateAsset, User, PortfolioCashAccount, CashTransaction, UserPreferences
)
from decimal import Decimal
from rest_framework import serializers
from .models import Currency, ExchangeRate


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'decimal_places']


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ['from_currency', 'to_currency', 'rate', 'date', 'source']


class CurrencyConversionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=8)
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    date = serializers.DateField(required=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = '__all__'


class SecuritySerializer(serializers.ModelSerializer):
    price_change = serializers.ReadOnlyField()
    price_change_pct = serializers.ReadOnlyField()

    class Meta:
        model = Security
        fields = [
            'id', 'symbol', 'name', 'security_type', 'exchange', 'currency', 'country',
            'current_price', 'last_updated', 'price_change', 'price_change_pct',
            'market_cap', 'volume', 'day_high', 'day_low', 'week_52_high',
            'week_52_low', 'pe_ratio', 'dividend_yield', 'sector', 'industry',
            'is_active', 'data_source'
        ]


class TransactionSerializer(serializers.ModelSerializer):
    security_symbol = serializers.ReadOnlyField(source='security.symbol')
    security_name = serializers.ReadOnlyField(source='security.name')
    portfolio_name = serializers.ReadOnlyField(source='portfolio.name')
    total_value = serializers.ReadOnlyField()
    currency = serializers.CharField(max_length=3, required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        read_only=True
    )
    base_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            'id', 'portfolio', 'portfolio_name', 'security', 'security_symbol',
            'security_name', 'transaction_type', 'transaction_date', 'quantity',
            'price', 'fees', 'total_value', 'dividend_per_share', 'notes',
            'created_at', 'currency', 'exchange_rate', 'base_amount', 'split_ratio'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Get currency from validated data or use security's currency
        currency = validated_data.get('currency')
        if not currency and 'security' in validated_data:
            currency = validated_data['security'].currency
            validated_data['currency'] = currency

        # Calculate exchange rate if currency differs from portfolio currency
        portfolio = validated_data['portfolio']
        if currency and currency != portfolio.currency:
            from .services.currency_service import CurrencyService
            exchange_rate = CurrencyService.get_exchange_rate(
                currency,
                portfolio.currency,
                validated_data.get('transaction_date', timezone.now()).date()
            )
            if exchange_rate:
                validated_data['exchange_rate'] = exchange_rate
                # Calculate base amount
                total_amount = validated_data['quantity'] * validated_data['price']
                validated_data['base_amount'] = total_amount * exchange_rate

        return super().create(validated_data)


class HoldingSerializer(serializers.Serializer):
    """Serializer for portfolio holdings (calculated data)"""
    security = SecuritySerializer()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=8)
    avg_cost = serializers.DecimalField(max_digits=20, decimal_places=8)
    current_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=20, decimal_places=2)
    unrealized_gains = serializers.DecimalField(max_digits=20, decimal_places=2)
    realized_gains = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_gains = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_dividends = serializers.DecimalField(max_digits=20, decimal_places=2)
    gain_loss_pct = serializers.SerializerMethodField()
    transactions_count = serializers.SerializerMethodField()

    def get_gain_loss_pct(self, obj):
        if obj['quantity'] > 0 and obj['avg_cost'] > 0:
            total_cost = obj['quantity'] * obj['avg_cost']
            return float((obj['unrealized_gains'] / total_cost) * 100)
        return 0

    def get_transactions_count(self, obj):
        return len(obj.get('transactions', []))


class PortfolioSerializer(serializers.ModelSerializer):
    total_value = serializers.SerializerMethodField()
    total_cost = serializers.SerializerMethodField()
    total_gains = serializers.SerializerMethodField()
    holdings_count = serializers.SerializerMethodField()
    asset_count = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    total_gain_loss = serializers.SerializerMethodField()
    gain_loss_percentage = serializers.SerializerMethodField()
    cash_balance = serializers.SerializerMethodField()  # New field
    total_value_with_cash = serializers.SerializerMethodField()  # New field

    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'is_default', 'currency',
            'created_at', 'updated_at', 'total_value', 'total_cost',
            'total_gains', 'holdings_count', 'asset_count', 'transaction_count',
            'total_gain_loss', 'gain_loss_percentage', 'cash_balance',
            'total_value_with_cash', 'base_currency'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_cash_balance(self, obj):
        """Get current cash balance"""
        if hasattr(obj, 'cash_account'):
            return float(obj.cash_account.balance)
        return 0.0

    def get_total_value_with_cash(self, obj):
        """Get total portfolio value including cash"""
        return float(obj.get_total_value())

    def get_total_value(self, obj):
        summary = obj.get_summary()
        return float(summary['total_value'])

    def get_total_cost(self, obj):
        summary = obj.get_summary()
        return float(summary['total_cost'])

    def get_total_gains(self, obj):
        summary = obj.get_summary()
        return float(summary['total_gains'])

    def get_holdings_count(self, obj):
        summary = obj.get_summary()
        return summary['holdings_count']

    def get_asset_count(self, obj):
        # Use annotated field if available, otherwise calculate
        if hasattr(obj, 'asset_count'):
            return obj.asset_count
        # Count unique securities with positive quantity
        holdings = obj.get_holdings()
        return len(holdings)

    def get_transaction_count(self, obj):
        # Use annotated field if available, otherwise calculate
        if hasattr(obj, 'transaction_count'):
            return obj.transaction_count
        # Count all transactions for this portfolio
        return obj.transactions.count()

    def get_total_gain_loss(self, obj):
        # This is the same as total_gains but named differently for frontend compatibility
        summary = obj.get_summary()
        return float(summary['total_gains'])

    def get_gain_loss_percentage(self, obj):
        summary = obj.get_summary()
        return float(summary['total_return_pct'])

class PortfolioCashAccountSerializer(serializers.ModelSerializer):
    portfolio_name = serializers.ReadOnlyField(source='portfolio.name')

    class Meta:
        model = PortfolioCashAccount
        fields = [
            'id', 'portfolio', 'portfolio_name', 'balance', 'currency',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PortfolioDetailSerializer(PortfolioSerializer):
    """Detailed portfolio serializer with holdings"""
    holdings = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    cash_account = PortfolioCashAccountSerializer(read_only=True)

    class Meta(PortfolioSerializer.Meta):
        fields = PortfolioSerializer.Meta.fields + ['holdings', 'summary', 'cash_account']

    def get_holdings(self, obj):
        holdings = obj.get_holdings()
        return [
            {
                'security': SecuritySerializer(data['security']).data,
                'quantity': float(data['quantity']),
                'avg_cost': float(data['avg_cost']),
                'current_value': float(data['current_value']),
                'total_cost': float(data['quantity'] * data['avg_cost']),
                'unrealized_gains': float(data['unrealized_gains']),
                'realized_gains': float(data['realized_gains']),
                'total_gains': float(data['total_gains']),
                'total_dividends': float(data['total_dividends']),
            }
            for data in holdings.values()
        ]

    def get_summary(self, obj):
        summary = obj.get_summary()
        return {
            'total_value': float(summary['total_value']),
            'total_cost': float(summary['total_cost']),
            'total_gains': float(summary['total_gains']),
            'total_dividends': float(summary['total_dividends']),
            'total_return': float(summary['total_return']),
            'total_return_pct': float(summary['total_return_pct']),
            'holdings_count': summary['holdings_count']
        }


class PriceHistorySerializer(serializers.ModelSerializer):
    security_symbol = serializers.ReadOnlyField(source='security.symbol')

    class Meta:
        model = PriceHistory
        fields = [
            'id', 'security', 'security_symbol', 'date', 'open_price',
            'high_price', 'low_price', 'close_price', 'adjusted_close',
            'volume'
        ]


class RealEstateAssetSerializer(serializers.ModelSerializer):
    unrealized_gain = serializers.ReadOnlyField()
    unrealized_gain_pct = serializers.ReadOnlyField()

    class Meta:
        model = RealEstateAsset
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']


class CashTransactionSerializer(serializers.ModelSerializer):
    portfolio_name = serializers.ReadOnlyField(source='cash_account.portfolio.name')

    class Meta:
        model = CashTransaction
        fields = [
            'id', 'cash_account', 'portfolio_name', 'transaction_type',
            'amount', 'balance_after', 'description', 'transaction_date',
            'is_auto_deposit', 'related_transaction', 'created_at'
        ]
        read_only_fields = ['user', 'balance_after', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Auto-set user from request
        validated_data['user'] = self.context['request'].user

        # Update cash account balance
        cash_account = validated_data['cash_account']
        amount = validated_data['amount']

        # Update balance
        cash_account.update_balance(amount)

        # Set balance_after
        validated_data['balance_after'] = cash_account.balance

        return super().create(validated_data)


class UserPreferencesSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = UserPreferences
        fields = [
            'id', 'username', 'auto_deposit_enabled', 'auto_deposit_mode',
            'show_cash_warnings', 'default_currency', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'username', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        """Ensure all fields are properly updated"""
        instance.auto_deposit_enabled = validated_data.get('auto_deposit_enabled', instance.auto_deposit_enabled)
        instance.auto_deposit_mode = validated_data.get('auto_deposit_mode', instance.auto_deposit_mode)
        instance.show_cash_warnings = validated_data.get('show_cash_warnings', instance.show_cash_warnings)
        instance.default_currency = validated_data.get('default_currency', instance.default_currency)
        instance.save()
        return instance