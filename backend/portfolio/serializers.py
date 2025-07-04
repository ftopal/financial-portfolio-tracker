from rest_framework import serializers
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, RealEstateAsset, User, PortfolioCashAccount, CashTransaction, UserPreferences
)
from decimal import Decimal
from rest_framework import serializers
from .models import Currency, ExchangeRate
from django.utils import timezone


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

    # CRITICAL: Make these fields WRITABLE (remove read_only=True)
    exchange_rate = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=False,  # Optional - will auto-calculate if not provided
        allow_null=True
    )
    base_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,  # Optional - will auto-calculate if not provided
        allow_null=True
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
        portfolio_currency = portfolio.base_currency or portfolio.currency

        if currency and currency != portfolio_currency:
            # CHECK IF USER PROVIDED CUSTOM VALUES
            user_exchange_rate = validated_data.get('exchange_rate')
            user_base_amount = validated_data.get('base_amount')

            print(f"DEBUG: User provided exchange_rate: {user_exchange_rate}")
            print(f"DEBUG: User provided base_amount: {user_base_amount}")

            if user_exchange_rate is not None:
                # USER PROVIDED CUSTOM EXCHANGE RATE - USE IT
                validated_data['exchange_rate'] = user_exchange_rate

                # If user also provided base_amount, use it; otherwise calculate
                if user_base_amount is not None:
                    validated_data['base_amount'] = user_base_amount
                else:
                    # Calculate base amount using user's exchange rate
                    quantity = validated_data.get('quantity', 0)
                    price = validated_data.get('price', 0)
                    fees = validated_data.get('fees', 0)
                    transaction_type = validated_data.get('transaction_type')

                    if transaction_type == 'BUY':
                        total_amount = (quantity * price) + fees
                    elif transaction_type == 'SELL':
                        total_amount = (quantity * price) - fees
                    else:
                        total_amount = quantity * price

                    validated_data['base_amount'] = total_amount * user_exchange_rate

            elif user_base_amount is not None:
                # USER PROVIDED BASE AMOUNT BUT NOT EXCHANGE RATE
                validated_data['base_amount'] = user_base_amount

                # Calculate the implied exchange rate
                quantity = validated_data.get('quantity', 0)
                price = validated_data.get('price', 0)
                fees = validated_data.get('fees', 0)
                transaction_type = validated_data.get('transaction_type')

                if transaction_type == 'BUY':
                    total_amount = (quantity * price) + fees
                elif transaction_type == 'SELL':
                    total_amount = (quantity * price) - fees
                else:
                    total_amount = quantity * price

                if total_amount > 0:
                    calculated_rate = user_base_amount / total_amount
                    validated_data['exchange_rate'] = calculated_rate

            else:
                # NO USER OVERRIDE - USE AUTOMATIC CALCULATION (existing logic)
                from .services.currency_service import CurrencyService
                from django.utils import timezone

                # Get the transaction date
                transaction_date = validated_data.get('transaction_date', timezone.now()).date()

                # Get exchange rate
                exchange_rate = CurrencyService.get_exchange_rate(
                    currency,
                    portfolio_currency,
                    transaction_date
                )

                if exchange_rate:
                    validated_data['exchange_rate'] = exchange_rate

                    # Calculate base amount properly
                    quantity = validated_data.get('quantity', 0)
                    price = validated_data.get('price', 0)
                    fees = validated_data.get('fees', 0)
                    transaction_type = validated_data.get('transaction_type')

                    if transaction_type == 'BUY':
                        total_amount = (quantity * price) + fees
                    elif transaction_type == 'SELL':
                        total_amount = (quantity * price) - fees
                    else:
                        total_amount = quantity * price

                    validated_data['base_amount'] = total_amount * exchange_rate

        print(f"DEBUG: Final exchange_rate in validated_data: {validated_data.get('exchange_rate')}")
        print(f"DEBUG: Final base_amount in validated_data: {validated_data.get('base_amount')}")

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Similar logic for updates
        currency = validated_data.get('currency', instance.currency)
        portfolio = instance.portfolio
        portfolio_currency = portfolio.base_currency or portfolio.currency

        if currency and currency != portfolio_currency:
            user_exchange_rate = validated_data.get('exchange_rate')
            user_base_amount = validated_data.get('base_amount')

            # If user provided custom values, use them
            if user_exchange_rate is not None or user_base_amount is not None:
                quantity = validated_data.get('quantity', instance.quantity)
                price = validated_data.get('price', instance.price)
                fees = validated_data.get('fees', instance.fees)
                transaction_type = validated_data.get('transaction_type', instance.transaction_type)

                if transaction_type == 'BUY':
                    total_amount = (quantity * price) + fees
                elif transaction_type == 'SELL':
                    total_amount = (quantity * price) - fees
                else:
                    total_amount = quantity * price

                if user_exchange_rate is not None and user_base_amount is None:
                    # User provided rate, calculate amount
                    validated_data['base_amount'] = total_amount * user_exchange_rate
                elif user_base_amount is not None and user_exchange_rate is None:
                    # User provided amount, calculate rate
                    if total_amount > 0:
                        validated_data['exchange_rate'] = user_base_amount / total_amount
                # If both provided, use both as-is

        return super().update(instance, validated_data)


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
        # Get currency from validated data or use security's currency
        currency = validated_data.get('currency')
        if not currency and 'security' in validated_data:
            currency = validated_data['security'].currency
            validated_data['currency'] = currency

        # Calculate exchange rate if currency differs from portfolio currency
        portfolio = validated_data['portfolio']
        portfolio_currency = portfolio.base_currency or portfolio.currency  # Use base_currency first

        if currency and currency != portfolio_currency:
            from .services.currency_service import CurrencyService
            exchange_rate = CurrencyService.get_exchange_rate(
                currency,
                portfolio_currency,
                validated_data.get('transaction_date', timezone.now()).date()
            )
            if exchange_rate:
                validated_data['exchange_rate'] = exchange_rate

                # Calculate base amount INCLUDING FEES
                quantity = validated_data.get('quantity', 0)
                price = validated_data.get('price', 0)
                fees = validated_data.get('fees', 0)
                transaction_type = validated_data.get('transaction_type')

                if transaction_type == 'BUY':
                    total_amount = (quantity * price) + fees
                elif transaction_type == 'SELL':
                    total_amount = (quantity * price) - fees
                else:
                    total_amount = quantity * price

                validated_data['base_amount'] = total_amount * exchange_rate

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