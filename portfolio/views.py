from rest_framework import viewsets, permissions, status
from .models import AssetCategory, Asset, Transaction, Portfolio, PriceHistory, Stock
from .serializers import AssetCategorySerializer, AssetSerializer, TransactionSerializer, PortfolioSerializer, StockSerializer
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Avg, Count, Q
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.db.models.functions import Coalesce
from collections import defaultdict
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import action
from .services.stock_import_service import StockImportService
from rest_framework.exceptions import ValidationError


class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.filter(is_active=True)
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search stocks in database"""
        query = request.query_params.get('q', '')
        if not query:
            return Response({'results': []})

        stocks = StockImportService.search_stocks(query)
        serializer = StockSerializer(stocks, many=True)
        return Response({'results': serializer.data})

    @action(detail=False, methods=['post'])
    def import_stock(self, request):
        """Import a stock from Yahoo Finance"""
        symbol = request.data.get('symbol', '').strip().upper()

        if not symbol:
            return Response({'error': 'Symbol is required'}, status=400)

        result = StockImportService.search_and_import_stock(symbol)

        if result.get('error'):
            return Response({'error': result['error']}, status=404)

        serializer = StockSerializer(result['stock'])
        return Response({
            'stock': serializer.data,
            'created': result.get('created', False),
            'exists': result.get('exists', False)
        })


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optimize with prefetch_related
        return Portfolio.objects.filter(user=self.request.user)\
            .prefetch_related('assets')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Asset.objects.filter(user=self.request.user) \
            .select_related('category', 'portfolio')

        # Filter by portfolio if specified
        portfolio_id = self.request.query_params.get('portfolio_id')
        if portfolio_id:
            queryset = queryset.filter(portfolio_id=portfolio_id)

        # Filter by asset type
        asset_type = self.request.query_params.get('asset_type')
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)

        return queryset

    def perform_create(self, serializer):
        stock_id = self.request.data.get('stock_id')
        if not stock_id:
            raise ValidationError({'stock_id': 'Stock selection is required'})

        try:
            stock = Stock.objects.get(id=stock_id)
        except Stock.DoesNotExist:
            raise ValidationError({'stock_id': 'Invalid stock selected'})

        serializer.save(
            user=self.request.user,
            stock=stock,
            name=stock.name,
            symbol=stock.symbol,
            asset_type=stock.asset_type
        )

    @action(detail=False, methods=['post'])
    def update_all_prices(self, request):
        """Update prices for all stocks"""
        from .services.stock_service import StockService
        result = StockService.update_all_stock_prices()
        return Response(result)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def grouped_assets(request):
    """Return assets grouped by symbol/name with consolidated quantities and values"""
    assets = Asset.objects.filter(user=request.user)

    # Group assets by symbol (or name if symbol doesn't exist)
    grouped = defaultdict(lambda: {
        'symbol': '',
        'name': '',
        'category': None,
        'asset_type': '',
        'total_quantity': 0,
        'total_invested': 0,
        'current_price': 0,
        'total_value': 0,
        'gain_loss': 0,
        'gain_loss_percentage': 0,
        'individual_purchases': []
    })

    for asset in assets:
        # Use symbol as key, fall back to name if no symbol
        key = asset.symbol if hasattr(asset, 'symbol') and asset.symbol else asset.name

        # Store basic info (same for all purchases of same asset)
        grouped[key]['symbol'] = asset.symbol if hasattr(asset, 'symbol') else ''
        grouped[key]['name'] = asset.name
        grouped[key]['category'] = asset.category.name if asset.category else 'Uncategorized'
        grouped[key]['asset_type'] = asset.get_asset_type_display()
        grouped[key]['current_price'] = asset.current_price

        # Aggregate quantities and values
        grouped[key]['total_quantity'] += asset.quantity
        grouped[key]['total_invested'] += (asset.purchase_price * asset.quantity)
        grouped[key]['total_value'] += asset.total_value
        grouped[key]['gain_loss'] += asset.gain_loss

        # Store individual purchase details
        grouped[key]['individual_purchases'].append({
            'id': asset.id,
            'quantity': asset.quantity,
            'purchase_price': asset.purchase_price,
            'purchase_date': asset.purchase_date if hasattr(asset, 'purchase_date') else None,
            'total_cost': asset.purchase_price * asset.quantity,
            'current_value': asset.total_value
        })

    # Calculate average purchase price and gain/loss percentage for each group
    for key, group in grouped.items():
        if group['total_quantity'] > 0:
            group['average_purchase_price'] = group['total_invested'] / group['total_quantity']

        if group['total_invested'] > 0:
            group['gain_loss_percentage'] = (group['gain_loss'] / group['total_invested']) * 100

    # Convert to list for JSON response
    result = list(grouped.values())

    return Response(result)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def all_portfolios_summary(request):
    portfolios = Portfolio.objects.filter(user=request.user)

    total_value = 0
    total_invested = 0
    portfolio_data = []

    for portfolio in portfolios:
        portfolio_assets = portfolio.assets.all()
        portfolio_value = sum(asset.total_value for asset in portfolio_assets)
        portfolio_investment = sum(asset.purchase_price * asset.quantity for asset in portfolio_assets)

        portfolio_data.append({
            'id': portfolio.id,
            'name': portfolio.name,
            'asset_count': portfolio_assets.count(),
            'total_value': portfolio_value,
            'total_invested': portfolio_investment,
            'gain_loss': portfolio_value - portfolio_investment,
            'gain_loss_percentage': ((
                                                 portfolio_value - portfolio_investment) / portfolio_investment * 100) if portfolio_investment else 0
        })

        total_value += portfolio_value
        total_invested += portfolio_investment

    # Get distribution by asset type across all portfolios
    all_assets = Asset.objects.filter(user=request.user)
    by_asset_type = {}

    for asset in all_assets:
        asset_type = asset.get_asset_type_display()
        if asset_type not in by_asset_type:
            by_asset_type[asset_type] = {
                'total_value': 0,
                'percentage': 0
            }
        by_asset_type[asset_type]['total_value'] += asset.total_value

    # Calculate percentages
    for asset_type in by_asset_type:
        by_asset_type[asset_type]['percentage'] = (
                    by_asset_type[asset_type]['total_value'] / total_value * 100) if total_value else 0

    return Response({
        'total_value': total_value,
        'total_invested': total_invested,
        'total_gain_loss': total_value - total_invested,
        'gain_loss_percentage': ((total_value - total_invested) / total_invested * 100) if total_invested else 0,
        'portfolios': portfolio_data,
        'portfolio_count': portfolios.count(),
        'by_asset_type': by_asset_type
    })


@api_view(['GET'])
def portfolio_summary(request):
    """Get comprehensive portfolio summary"""
    portfolio_id = request.query_params.get('portfolio_id')

    # Base query
    assets_query = Asset.objects.filter(user=request.user)
    if portfolio_id:
        assets_query = assets_query.filter(portfolio_id=portfolio_id)

    # Get all assets and calculate in Python (simpler and works reliably)
    assets = assets_query.select_related('category')

    # Calculate totals
    total_value = sum(float(asset.current_price * asset.quantity) for asset in assets)
    total_cost = sum(float(asset.purchase_price * asset.quantity) for asset in assets)
    total_gain_loss = total_value - total_cost
    gain_loss_percentage = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

    # Group by asset type
    asset_breakdown = {}
    for asset in assets:
        if asset.asset_type not in asset_breakdown:
            asset_breakdown[asset.asset_type] = {
                'count': 0,
                'value': 0
            }
        asset_breakdown[asset.asset_type]['count'] += 1
        asset_breakdown[asset.asset_type]['value'] += float(asset.current_price * asset.quantity)

    # Convert to list format
    breakdown_list = [
        {
            'asset_type': asset_type,
            'count': data['count'],
            'value': data['value']
        }
        for asset_type, data in asset_breakdown.items()
    ]
    breakdown_list.sort(key=lambda x: x['value'], reverse=True)

    return Response({
        'totals': {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_gain_loss': total_gain_loss,
            'gain_loss_percentage': gain_loss_percentage,
            'total_assets': len(assets)
        },
        'asset_breakdown': breakdown_list,
        'last_updated': timezone.now()
    })


@api_view(['GET'])
def portfolio_consolidated_view(request, portfolio_id):
    """Get consolidated view of assets grouped by symbol/name"""
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id, user=request.user)
    except Portfolio.DoesNotExist:
        return Response({'error': 'Portfolio not found'}, status=404)

    # Get all assets for this portfolio
    assets = Asset.objects.filter(
        portfolio=portfolio,
        user=request.user
    ).select_related('category', 'stock').order_by('symbol', 'name')

    # Group assets by symbol (or name if no symbol)
    grouped_assets = {}

    for asset in assets:
        key = asset.symbol if asset.symbol else asset.name

        if key not in grouped_assets:
            grouped_assets[key] = {
                'symbol': asset.symbol,
                'name': asset.name,
                'asset_type': asset.asset_type,
                'category_name': asset.category.name if asset.category else None,
                'total_quantity': 0,
                'total_cost': 0,
                'current_price': float(asset.current_price),
                'transactions': []
            }

        # Add to totals (convert Decimal to float)
        grouped_assets[key]['total_quantity'] += float(asset.quantity)
        grouped_assets[key]['total_cost'] += float(asset.purchase_price) * float(asset.quantity)

        # Update current price to the latest one (in case different transactions have different current prices)
        grouped_assets[key]['current_price'] = float(asset.current_price)

        # Add transaction details
        grouped_assets[key]['transactions'].append({
            'id': asset.id,
            'stock_id': asset.stock.id if asset.stock else None,
            'purchase_date': asset.purchase_date,
            'quantity': float(asset.quantity),
            'purchase_price': float(asset.purchase_price),
            'current_price': float(asset.current_price),
            'value': float(asset.current_price) * float(asset.quantity),
            'cost': float(asset.purchase_price) * float(asset.quantity),
            'gain_loss': float((asset.current_price - asset.purchase_price) * asset.quantity),
            'gain_loss_percentage': float(asset.gain_loss_percentage) if asset.gain_loss_percentage else 0
        })

    # Calculate consolidated metrics
    result = []
    for key, data in grouped_assets.items():
        avg_cost_price = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        total_current_value = data['current_price'] * data['total_quantity']
        total_gain_loss = total_current_value - data['total_cost']
        gain_loss_percentage = (total_gain_loss / data['total_cost'] * 100) if data['total_cost'] > 0 else 0

        result.append({
            'key': key,
            'symbol': data['symbol'],
            'name': data['name'],
            'asset_type': data['asset_type'],
            'category_name': data['category_name'],
            'total_quantity': data['total_quantity'],
            'avg_cost_price': avg_cost_price,
            'current_price': data['current_price'],
            'total_current_value': total_current_value,
            'total_cost': data['total_cost'],
            'total_gain_loss': total_gain_loss,
            'gain_loss_percentage': gain_loss_percentage,
            'transactions': sorted(data['transactions'], key=lambda x: x['purchase_date'], reverse=True)
        })

    # Sort by total value descending
    result.sort(key=lambda x: x['total_current_value'], reverse=True)

    return Response({
        'portfolio': PortfolioSerializer(portfolio).data,
        'consolidated_assets': result,
        'summary': {
            'total_value': sum(item['total_current_value'] for item in result),
            'total_cost': sum(item['total_cost'] for item in result),
            'total_gain_loss': sum(item['total_gain_loss'] for item in result),
            'unique_assets': len(result),
            'total_transactions': sum(len(item['transactions']) for item in result)
        }
    })