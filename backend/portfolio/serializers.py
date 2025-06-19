from rest_framework import serializers
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, RealEstateAsset, User
)
from decimal import Decimal


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

    class Meta:
        model = Transaction
        fields = [
            'id', 'portfolio', 'portfolio_name', 'security', 'security_symbol',
            'security_name', 'transaction_type', 'transaction_date', 'quantity',
            'price', 'fees', 'total_value', 'dividend_per_share', 'notes',
            'created_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Auto-set user from request
        validated_data['user'] = self.context['request'].user
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

    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'is_default', 'currency',
            'created_at', 'updated_at', 'total_value', 'total_cost',
            'total_gains', 'holdings_count'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

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


class PortfolioDetailSerializer(PortfolioSerializer):
    """Detailed portfolio serializer with holdings"""
    holdings = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta(PortfolioSerializer.Meta):
        fields = PortfolioSerializer.Meta.fields + ['holdings', 'summary']

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