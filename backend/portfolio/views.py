from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.db.models import Sum, Count, Q, F, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, RealEstateAsset
)
from .serializers import (
    PortfolioSerializer, PortfolioDetailSerializer,
    AssetCategorySerializer, SecuritySerializer,
    TransactionSerializer, HoldingSerializer,
    PriceHistorySerializer, RealEstateAssetSerializer
)
from .services.security_import_service import SecurityImportService


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PortfolioDetailSerializer
        return PortfolioSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def holdings(self, request, pk=None):
        """Get portfolio holdings with details"""
        portfolio = self.get_object()
        holdings = portfolio.get_holdings()

        holdings_data = []
        for security_id, data in holdings.items():
            holding = {
                'security': SecuritySerializer(data['security']).data,
                'quantity': float(data['quantity']),
                'avg_cost': float(data['avg_cost']),
                'current_value': float(data['current_value']),
                'unrealized_gains': float(data['unrealized_gains']),
                'realized_gains': float(data['realized_gains']),
                'total_gains': float(data['total_gains']),
                'total_dividends': float(data['total_dividends']),
                'transactions': TransactionSerializer(data['transactions'], many=True).data
            }
            holdings_data.append(holding)

        # Sort by current value descending
        holdings_data.sort(key=lambda x: x['current_value'], reverse=True)

        return Response({
            'portfolio': PortfolioSerializer(portfolio).data,
            'holdings': holdings_data,
            'summary': portfolio.get_summary()
        })

    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get all transactions for a portfolio"""
        portfolio = self.get_object()
        transactions = portfolio.transactions.select_related('security').order_by('-transaction_date')

        # Optional filtering
        security_id = request.query_params.get('security_id')
        if security_id:
            transactions = transactions.filter(security_id=security_id)

        transaction_type = request.query_params.get('type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)

        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class SecurityViewSet(viewsets.ModelViewSet):
    queryset = Security.objects.filter(is_active=True)
    serializer_class = SecuritySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search securities in database"""
        query = request.query_params.get('q', '')
        if not query:
            return Response({'results': []})

        securities = Security.objects.filter(
            Q(symbol__icontains=query) | Q(name__icontains=query),
            is_active=True
        )[:20]

        serializer = SecuritySerializer(securities, many=True)
        return Response({'results': serializer.data})

    @action(detail=False, methods=['post'])
    def import_security(self, request):
        """Import a security from external data source"""
        symbol = request.data.get('symbol', '').strip().upper()

        if not symbol:
            return Response({'error': 'Symbol is required'}, status=400)

        result = SecurityImportService.search_and_import_security(symbol)

        if result.get('error'):
            return Response({'error': result['error']}, status=404)

        serializer = SecuritySerializer(result['security'])
        return Response({
            'security': serializer.data,
            'created': result.get('created', False),
            'exists': result.get('exists', False)
        })

    @action(detail=True, methods=['post'])
    def update_price(self, request, pk=None):
        """Manually update security price"""
        security = self.get_object()
        new_price = request.data.get('price')

        if not new_price:
            return Response({'error': 'Price is required'}, status=400)

        security.current_price = new_price
        security.last_updated = timezone.now()
        security.save()

        # Record in price history
        PriceHistory.objects.create(
            security=security,
            date=timezone.now(),
            close_price=new_price
        )

        return Response(SecuritySerializer(security).data)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user) \
            .select_related('portfolio', 'security')

        # Filtering
        portfolio_id = self.request.query_params.get('portfolio_id')
        if portfolio_id:
            queryset = queryset.filter(portfolio_id=portfolio_id)

        security_id = self.request.query_params.get('security_id')
        if security_id:
            queryset = queryset.filter(security_id=security_id)

        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)

        return queryset.order_by('-transaction_date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]


@api_view(['GET'])
def portfolio_summary(request):
    """Get summary of all portfolios"""
    portfolios = Portfolio.objects.filter(user=request.user)

    total_value = 0
    total_cost = 0
    total_gains = 0
    total_dividends = 0

    portfolio_summaries = []

    for portfolio in portfolios:
        summary = portfolio.get_summary()
        total_value += summary['total_value']
        total_cost += summary['total_cost']
        total_gains += summary['total_gains']
        total_dividends += summary['total_dividends']

        portfolio_summaries.append({
            'portfolio': PortfolioSerializer(portfolio).data,
            'summary': summary
        })

    return Response({
        'total_value': float(total_value),
        'total_cost': float(total_cost),
        'total_gains': float(total_gains),
        'total_dividends': float(total_dividends),
        'total_return': float(total_gains + total_dividends),
        'total_return_pct': float(((total_gains + total_dividends) / total_cost * 100) if total_cost > 0 else 0),
        'portfolios': portfolio_summaries
    })


@api_view(['GET'])
def portfolio_holdings_consolidated(request, portfolio_id):
    """Get consolidated view of holdings for frontend compatibility"""
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id, user=request.user)
    except Portfolio.DoesNotExist:
        return Response({'error': 'Portfolio not found'}, status=404)

    holdings = portfolio.get_holdings()
    consolidated_assets = []

    for security_id, data in holdings.items():
        # Build transactions list in the format the frontend expects
        transactions = []
        for transaction in data['transactions']:
            if transaction.transaction_type == 'BUY':
                transactions.append({
                    'id': transaction.id,
                    'stock_id': transaction.security.id,
                    'purchase_date': transaction.transaction_date,
                    'quantity': float(transaction.quantity),
                    'purchase_price': float(transaction.price),
                    'current_price': float(data['security'].current_price),
                    'value': float(transaction.quantity * data['security'].current_price),
                    'cost': float(transaction.quantity * transaction.price),
                    'gain_loss': float((data['security'].current_price - transaction.price) * transaction.quantity),
                    'gain_loss_percentage': float(
                        ((data['security'].current_price - transaction.price) / transaction.price * 100)
                        if transaction.price > 0 else 0
                    )
                })

        # Only include if there are buy transactions
        if transactions and data['quantity'] > 0:
            consolidated_asset = {
                'key': f"{data['security'].symbol}_{security_id}",
                'symbol': data['security'].symbol,
                'name': data['security'].name,
                'asset_type': data['security'].security_type,
                'category_name': data['security'].category.name if data['security'].category else None,
                'total_quantity': float(data['quantity']),
                'avg_cost_price': float(data['avg_cost']),
                'current_price': float(data['security'].current_price),
                'total_current_value': float(data['current_value']),
                'total_cost': float(data['quantity'] * data['avg_cost']),
                'total_gain_loss': float(data['unrealized_gains']),
                'gain_loss_percentage': float(
                    (data['unrealized_gains'] / (data['quantity'] * data['avg_cost']) * 100)
                    if data['quantity'] > 0 and data['avg_cost'] > 0 else 0
                ),
                'transactions': sorted(transactions, key=lambda x: x['purchase_date'], reverse=True)
            }
            consolidated_assets.append(consolidated_asset)

    # Sort by total value descending
    consolidated_assets.sort(key=lambda x: x['total_current_value'], reverse=True)

    # Calculate summary
    summary = {
        'total_value': sum(item['total_current_value'] for item in consolidated_assets),
        'total_cost': sum(item['total_cost'] for item in consolidated_assets),
        'total_gain_loss': sum(item['total_gain_loss'] for item in consolidated_assets),
        'unique_assets': len(consolidated_assets),
        'total_transactions': sum(len(item['transactions']) for item in consolidated_assets)
    }

    return Response({
        'portfolio': PortfolioSerializer(portfolio).data,
        'consolidated_assets': consolidated_assets,
        'summary': summary
    })