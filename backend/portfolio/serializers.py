from rest_framework import serializers
from .models import AssetCategory, Asset, Transaction, Portfolio, PriceHistory, Stock
from django.contrib.auth.models import User
from decimal import Decimal


class PortfolioSerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()  # Unique stocks
    transaction_count = serializers.SerializerMethodField()  # Total transactions
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = ['id', 'name', 'description', 'created_at', 'updated_at',
                  'asset_count', 'transaction_count', 'total_value']

    def get_asset_count(self, obj):
        # Count unique stocks
        unique_stocks = obj.assets.values('stock').distinct().count()
        return unique_stocks

    def get_transaction_count(self, obj):
        # Count total transactions
        return obj.assets.count()

    def get_total_value(self, obj):
        return sum(asset.total_value for asset in obj.assets.all())


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = '__all__'


class AssetSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    portfolio_name = serializers.ReadOnlyField(source='portfolio.name')
    current_price = serializers.ReadOnlyField()  # Now comes from property
    stock_last_updated = serializers.ReadOnlyField(source='stock.last_updated')
    gain_loss = serializers.ReadOnlyField()
    gain_loss_percentage = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at', 'stock']

    def get_total_cost(self, obj):
        return float(obj.purchase_price * obj.quantity)


class TransactionSerializer(serializers.ModelSerializer):
    asset_name = serializers.ReadOnlyField(source='asset.name')
    asset_symbol = serializers.ReadOnlyField(source='asset.symbol')
    portfolio_name = serializers.ReadOnlyField(source='asset.portfolio.name')
    total_value = serializers.ReadOnlyField()

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['user', 'created_at']


class PriceHistorySerializer(serializers.ModelSerializer):
    asset_name = serializers.ReadOnlyField(source='asset.name')

    class Meta:
        model = PriceHistory
        fields = ['id', 'asset', 'asset_name', 'date', 'price', 'volume']


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            'id', 'symbol', 'name', 'asset_type', 'exchange',
            'currency', 'current_price', 'last_updated', 'sector',
            'industry', 'market_cap', 'pe_ratio', 'day_high',
            'day_low', 'volume', 'week_52_high', 'week_52_low'
        ]