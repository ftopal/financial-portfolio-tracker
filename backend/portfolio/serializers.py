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
    amount = serializers.DecimalField(max_digits=20, decimal_places=12)  # Increased from 8 to 12
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    date = serializers.DateField(required=False)

    def validate_amount(self, value):
        """Additional validation for amount"""
        if value < 0:
            raise serializers.ValidationError("Amount must be positive")

        # Round to 8 decimal places for processing if needed
        # This prevents issues with JavaScript floating point precision
        return value.quantize(Decimal('0.00000001'))  # 8 decimal places


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
        required=False,
        allow_null=True
    )
    base_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
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

    def validate(self, data):
        """Add validation for dividend transactions with decimal shares"""
        transaction_type = data.get('transaction_type')

        # Handle dividend per share calculation and rounding
        if transaction_type == 'DIVIDEND':
            quantity = data.get('quantity')
            price = data.get('price')
            dividend_per_share = data.get('dividend_per_share')

            # If dividend_per_share is not provided but price (total dividend) is
            if not dividend_per_share and price and quantity:
                if quantity > 0:
                    # Calculate and round to 4 decimal places to match model field
                    calculated_dps = price / quantity
                    data['dividend_per_share'] = Decimal(str(round(float(calculated_dps), 4)))
                else:
                    raise serializers.ValidationError({
                        'quantity': 'Quantity must be greater than 0 for dividend transactions.'
                    })

            # If dividend_per_share is provided, ensure it's properly rounded
            elif dividend_per_share:
                data['dividend_per_share'] = Decimal(str(round(float(dividend_per_share), 4)))

        return data

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
                    elif transaction_type == 'DIVIDEND':
                        # For dividends, fees should be subtracted
                        if 'dividend_per_share' in validated_data:
                            total_amount = (quantity * validated_data['dividend_per_share']) - fees
                        else:
                            total_amount = (validated_data.get('price', 0) or 0) - fees
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
                elif transaction_type == 'DIVIDEND':
                    # For dividends, properly handle the calculation
                    if 'dividend_per_share' in validated_data:
                        total_amount = (quantity * validated_data['dividend_per_share']) - fees
                    else:
                        total_amount = (validated_data.get('price', 0) or 0) - fees
                else:
                    total_amount = quantity * price

                if total_amount > 0:
                    calculated_rate = user_base_amount / total_amount
                    validated_data['exchange_rate'] = calculated_rate

            else:
                # NO USER OVERRIDE - USE AUTOMATIC CALCULATION
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
                    elif transaction_type == 'DIVIDEND':
                        # For dividends, fees should be subtracted
                        if 'dividend_per_share' in validated_data:
                            total_amount = (quantity * validated_data['dividend_per_share']) - fees
                        else:
                            total_amount = (validated_data.get('price', 0) or 0) - fees
                    else:
                        total_amount = quantity * price

                    validated_data['base_amount'] = total_amount * exchange_rate

        print(f"DEBUG: Final exchange_rate in validated_data: {validated_data.get('exchange_rate')}")
        print(f"DEBUG: Final base_amount in validated_data: {validated_data.get('base_amount')}")

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Store old values for cash transaction update
        old_exchange_rate = instance.exchange_rate
        old_base_amount = instance.base_amount
        old_total_value = instance.total_value

        # Similar logic for updates as in create method
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
                elif transaction_type == 'DIVIDEND':
                    # For dividends, fees should be subtracted, not added
                    if validated_data.get('dividend_per_share'):
                        total_amount = (quantity * validated_data.get('dividend_per_share')) - fees
                    else:
                        total_amount = (validated_data.get('price', price) or 0) - fees
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

        # Update the transaction
        updated_instance = super().update(instance, validated_data)

        # CHECK IF WE NEED TO UPDATE THE RELATED CASH TRANSACTION
        new_base_amount = updated_instance.base_amount or updated_instance.total_value

        # Import here to avoid circular imports
        from .models import CashTransaction

        # Check if there's a related cash transaction that needs updating
        try:
            related_cash_transaction = CashTransaction.objects.get(
                related_transaction=updated_instance
            )

            # Calculate the difference in cash amount
            old_cash_amount = old_base_amount or old_total_value
            new_cash_amount = new_base_amount

            print(f"DEBUG: Old cash amount: {old_cash_amount}")
            print(f"DEBUG: New cash amount: {new_cash_amount}")

            if old_cash_amount != new_cash_amount:
                # Update the cash transaction amount
                cash_difference = new_cash_amount - old_cash_amount

                if updated_instance.transaction_type == 'BUY':
                    # For BUY transactions, cash amount is negative (outflow)
                    new_cash_transaction_amount = -new_cash_amount
                    cash_balance_adjustment = -cash_difference
                elif updated_instance.transaction_type == 'SELL':
                    # For SELL transactions, cash amount is positive (inflow)
                    new_cash_transaction_amount = new_cash_amount
                    cash_balance_adjustment = cash_difference
                elif updated_instance.transaction_type == 'DIVIDEND':
                    # For DIVIDEND transactions, cash amount is positive (inflow)
                    new_cash_transaction_amount = new_cash_amount
                    cash_balance_adjustment = cash_difference
                else:
                    # For other transaction types, no cash impact
                    return updated_instance

                print(
                    f"DEBUG: Updating cash transaction from {related_cash_transaction.amount} to {new_cash_transaction_amount}")
                print(f"DEBUG: Cash balance adjustment: {cash_balance_adjustment}")

                # Update the cash transaction amount
                related_cash_transaction.amount = new_cash_transaction_amount
                related_cash_transaction.save()

                # Update the cash account balance
                cash_account = related_cash_transaction.cash_account
                cash_account.update_balance(cash_balance_adjustment)

                print(f"DEBUG: Updated cash account balance to: {cash_account.balance}")

        except CashTransaction.DoesNotExist:
            print(f"DEBUG: No related cash transaction found for transaction {updated_instance.id}")
            pass
        except Exception as e:
            print(f"DEBUG: Error updating related cash transaction: {e}")
            pass

        return updated_instance


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

    def to_representation(self, instance):
        # Cache both holdings and summary for this serialization
        if not hasattr(instance, '_cached_holdings'):
            instance._cached_holdings = instance.get_holdings()
        if not hasattr(instance, '_cached_summary'):
            instance._cached_summary = instance.get_summary()

        data = super().to_representation(instance)
        return data

    def get_cash_balance(self, obj):
        """Get current cash balance"""
        if hasattr(obj, 'cash_account'):
            return float(obj.cash_account.balance)
        return 0.0

    def get_total_value_with_cash(self, obj):
        """Get total portfolio value including cash"""
        return float(obj.get_total_value())

    def get_total_value(self, obj):
        if hasattr(obj, '_cached_summary'):
            return float(obj._cached_summary['total_value'])
        return float(obj.get_summary()['total_value'])

    def get_total_cost(self, obj):
        if hasattr(obj, '_cached_summary'):
            return float(obj._cached_summary['total_cost'])
        return float(obj.get_summary()['total_cost'])

    def get_total_gains(self, obj):
        if hasattr(obj, '_cached_summary'):
            return float(obj._cached_summary['total_gains'])
        return float(obj.get_summary()['total_gains'])

    def get_holdings_count(self, obj):
        if hasattr(obj, '_cached_summary'):
            return obj._cached_summary['holdings_count']
        return obj.get_summary()['holdings_count']

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
        if hasattr(obj, '_cached_summary'):
            return float(obj._cached_summary['total_gains'])
        return float(obj.get_summary()['total_gains'])

    def get_gain_loss_percentage(self, obj):
        if hasattr(obj, '_cached_summary'):
            return float(obj._cached_summary['total_return_pct'])
        return float(obj.get_summary()['total_return_pct'])

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