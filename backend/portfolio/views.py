from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, CashTransaction, UserPreferences
)
from .serializers import (
    PortfolioSerializer, PortfolioDetailSerializer,
    AssetCategorySerializer, SecuritySerializer,
    TransactionSerializer, CashTransactionSerializer, UserPreferencesSerializer
)
from .services.security_import_service import SecurityImportService


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Annotate with counts for better performance
        return Portfolio.objects.filter(user=self.request.user).annotate(
            transaction_count=Count('transactions'),
            # Count unique securities with BUY transactions
            asset_count=Count(
                'transactions__security',
                filter=Q(transactions__transaction_type='BUY'),
                distinct=True
            )
        )

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
            'holdings': holdings_data,
            'summary': portfolio.get_summary()
        })

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get portfolio performance over time"""
        portfolio = self.get_object()
        days = int(request.query_params.get('days', 30))

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get all transactions up to end date
        transactions = portfolio.transactions.filter(
            transaction_date__lte=end_date
        ).select_related('security')

        # Calculate daily values
        performance_data = []
        current_date = start_date

        while current_date <= end_date:
            daily_value = Decimal('0')

            # Get holdings as of current_date
            for security in transactions.values('security').distinct():
                security_transactions = transactions.filter(
                    security=security['security'],
                    transaction_date__lte=current_date
                )

                # Calculate quantity held
                quantity = security_transactions.filter(
                    transaction_type='BUY'
                ).aggregate(
                    total=Coalesce(Sum('quantity'), Decimal('0'))
                )['total'] - security_transactions.filter(
                    transaction_type='SELL'
                ).aggregate(
                    total=Coalesce(Sum('quantity'), Decimal('0'))
                )['total']

                if quantity > 0:
                    # Get price for this date
                    price_history = PriceHistory.objects.filter(
                        security_id=security['security'],
                        date__date=current_date.date()
                    ).first()

                    if price_history:
                        daily_value += quantity * price_history.close_price

            performance_data.append({
                'date': current_date.date(),
                'value': float(daily_value)
            })

            current_date += timedelta(days=1)

        return Response(performance_data)

    @action(detail=True, methods=['post'])
    def deposit_cash(self, request, pk=None):
        """Deposit cash into portfolio"""
        portfolio = self.get_object()
        amount = Decimal(request.data.get('amount', 0))
        description = request.data.get('description', 'Cash deposit')

        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        # Create cash transaction
        cash_transaction = CashTransaction.objects.create(
            cash_account=portfolio.cash_account,
            user=request.user,
            transaction_type='DEPOSIT',
            amount=amount,
            description=description,
            transaction_date=timezone.now()
        )

        # Update balance
        portfolio.cash_account.update_balance(amount)

        return Response(CashTransactionSerializer(cash_transaction).data)

    @action(detail=True, methods=['post'])
    def withdraw_cash(self, request, pk=None):
        """Withdraw cash from portfolio"""
        portfolio = self.get_object()
        amount = Decimal(request.data.get('amount', 0))
        description = request.data.get('description', 'Cash withdrawal')

        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        if not portfolio.cash_account.has_sufficient_balance(amount):
            return Response({'error': 'Insufficient cash balance'}, status=400)

        # Create cash transaction (negative amount for withdrawal)
        cash_transaction = CashTransaction.objects.create(
            cash_account=portfolio.cash_account,
            user=request.user,
            transaction_type='WITHDRAWAL',
            amount=-amount,
            description=description,
            transaction_date=timezone.now()
        )

        # Update balance
        portfolio.cash_account.update_balance(-amount)

        return Response(CashTransactionSerializer(cash_transaction).data)

    @action(detail=True, methods=['get'])
    def cash_history(self, request, pk=None):
        """Get cash transaction history for portfolio"""
        portfolio = self.get_object()
        transactions = CashTransaction.objects.filter(
            cash_account=portfolio.cash_account
        ).order_by('-transaction_date')

        # Pagination
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = CashTransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CashTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class SecurityViewSet(viewsets.ModelViewSet):
    queryset = Security.objects.all()
    serializer_class = SecuritySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtering
        security_type = self.request.query_params.get('type')
        if security_type:
            queryset = queryset.filter(security_type=security_type)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(symbol__icontains=search) | Q(name__icontains=search)
            )

        return queryset.filter(is_active=True)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search securities by symbol or name"""
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response([])

        securities = Security.objects.filter(
            Q(symbol__icontains=query) | Q(name__icontains=query),
            is_active=True
        )[:20]

        return Response(SecuritySerializer(securities, many=True).data)

    @action(detail=False, methods=['post'])
    def import_security(self, request):
        """Import security data from external source"""
        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=400)

        service = SecurityImportService()
        result = service.import_security(symbol)

        if result.get('error'):
            return Response({'error': result['error']}, status=400)

        return Response({
            'security': SecuritySerializer(result['security']).data,
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
        """Override to handle cash transactions"""
        transaction = serializer.save(user=self.request.user)

        # Get user preferences
        preferences, _ = UserPreferences.objects.get_or_create(user=self.request.user)

        # Handle cash flow based on transaction type
        cash_account = transaction.portfolio.cash_account

        # Check if cash transaction already exists
        if hasattr(transaction, 'cash_transaction'):
            return  # Cash transaction already exists, skip

        if transaction.transaction_type == 'BUY':
            # Calculate total cost including fees
            total_cost = transaction.total_value

            # Check cash balance
            if not cash_account.has_sufficient_balance(total_cost):
                if preferences.auto_deposit_enabled:
                    # Calculate deposit amount based on mode
                    if preferences.auto_deposit_mode == 'EXACT':
                        deposit_amount = total_cost
                    else:  # SHORTFALL
                        deposit_amount = total_cost - cash_account.balance

                    # Create auto-deposit
                    CashTransaction.objects.create(
                        cash_account=cash_account,
                        user=self.request.user,
                        transaction_type='DEPOSIT',
                        amount=deposit_amount,
                        description=f'Auto-deposit for {transaction.security.symbol} purchase',
                        transaction_date=transaction.transaction_date,
                        is_auto_deposit=True
                    )
                    cash_account.update_balance(deposit_amount)

            # Create buy cash transaction
            CashTransaction.objects.create(
                cash_account=cash_account,
                user=self.request.user,
                transaction_type='BUY',
                amount=-total_cost,
                description=f'Bought {transaction.quantity} {transaction.security.symbol}',
                transaction_date=transaction.transaction_date,
                related_transaction=transaction
            )
            cash_account.update_balance(-total_cost)

        elif transaction.transaction_type == 'SELL':
            # Calculate proceeds after fees
            proceeds = transaction.total_value

            # Create sell cash transaction
            CashTransaction.objects.create(
                cash_account=cash_account,
                user=self.request.user,
                transaction_type='SELL',
                amount=proceeds,
                description=f'Sold {transaction.quantity} {transaction.security.symbol}',
                transaction_date=transaction.transaction_date,
                related_transaction=transaction
            )
            cash_account.update_balance(proceeds)

        elif transaction.transaction_type == 'DIVIDEND':
            # Create dividend cash transaction
            dividend_amount = transaction.total_value

            CashTransaction.objects.create(
                cash_account=cash_account,
                user=self.request.user,
                transaction_type='DIVIDEND',
                amount=dividend_amount,
                description=f'Dividend from {transaction.security.symbol}',
                transaction_date=transaction.transaction_date,
                related_transaction=transaction
            )
            cash_account.update_balance(dividend_amount)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]


class CashTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for cash transactions"""
    serializer_class = CashTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CashTransaction.objects.filter(user=self.request.user) \
            .select_related('cash_account__portfolio', 'related_transaction')

        # Filter by portfolio
        portfolio_id = self.request.query_params.get('portfolio_id')
        if portfolio_id:
            queryset = queryset.filter(cash_account__portfolio_id=portfolio_id)

        # Filter by transaction type
        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Date filtering
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)

        return queryset.order_by('-transaction_date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserPreferencesViewSet(viewsets.ModelViewSet):
    """ViewSet for user preferences"""
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        """Override list to ensure user always has preferences"""
        # Get or create preferences for the user
        preferences, created = UserPreferences.objects.get_or_create(
            user=request.user,
            defaults={
                'auto_deposit_enabled': True,
                'auto_deposit_mode': 'EXACT',
                'show_cash_warnings': True,
                'default_currency': 'USD'
            }
        )

        # Return single object as list for consistency with frontend
        serializer = self.get_serializer([preferences], many=True)
        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': serializer.data
        })

    def get_object(self):
        """Get or create user preferences"""
        obj, created = UserPreferences.objects.get_or_create(
            user=self.request.user,
            defaults={
                'auto_deposit_enabled': True,
                'auto_deposit_mode': 'EXACT',
                'show_cash_warnings': True,
                'default_currency': 'USD'
            }
        )
        return obj

    def perform_create(self, serializer):
        """Ensure user is set when creating preferences"""
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Override create to handle get_or_create logic"""
        # Check if preferences already exist
        existing = UserPreferences.objects.filter(user=request.user).first()
        if existing:
            # Update existing preferences
            serializer = self.get_serializer(existing, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data, status=200)
        else:
            # Create new preferences
            return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Override update to ensure correct instance"""
        # Force partial update
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


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

        # Include ALL transaction types, not just BUY
        for transaction in data['transactions']:
            transaction_data = {
                'id': transaction.id,
                'stock_id': transaction.security.id,
                'transaction_type': transaction.transaction_type,
                'transaction_date': transaction.transaction_date,
                'quantity': float(transaction.quantity),
                'price': float(transaction.price),
                'current_price': float(data['security'].current_price),
                'fees': float(transaction.fees),
            }

            # Add specific fields based on transaction type
            if transaction.transaction_type == 'BUY':
                transaction_data.update({
                    'purchase_date': transaction.transaction_date,  # For compatibility
                    'purchase_price': float(transaction.price),  # For compatibility
                    'value': float(transaction.quantity * data['security'].current_price),
                    'cost': float(transaction.quantity * transaction.price),
                    'gain_loss': float((data['security'].current_price - transaction.price) * transaction.quantity),
                    'gain_loss_percentage': float(
                        ((data['security'].current_price - transaction.price) / transaction.price * 100)
                        if transaction.price > 0 else 0
                    )
                })
            elif transaction.transaction_type == 'SELL':
                transaction_data.update({
                    'purchase_date': transaction.transaction_date,  # For compatibility
                    'purchase_price': float(transaction.price),  # For compatibility
                    'value': float(transaction.quantity * transaction.price),
                    'proceeds': float(transaction.quantity * transaction.price - transaction.fees)
                })
            elif transaction.transaction_type == 'DIVIDEND':
                transaction_data.update({
                    'purchase_date': transaction.transaction_date,  # For compatibility
                    'dividend_per_share': float(
                        transaction.dividend_per_share) if transaction.dividend_per_share else 0,
                    'total_dividend': float(transaction.total_value),
                    'purchase_price': 0,  # No purchase price for dividends
                    'value': float(transaction.total_value),
                    'gain_loss': 0,
                    'gain_loss_percentage': 0
                })

            transactions.append(transaction_data)

        # Only include if there are transactions and positive quantity
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
                'total_cost': float(data.get('net_cash_invested', data['quantity'] * data['avg_cost'])),
                'total_gain_loss': float(data['unrealized_gains']),
                'total_dividends': float(data['total_dividends']),
                'gain_loss_percentage': float(
                    (data['unrealized_gains'] / (data.get('net_cash_invested', data['quantity'] * data['avg_cost'])) * 100)
                    if data.get('net_cash_invested', data['quantity'] * data['avg_cost']) > 0 else 0
                ),
                'transactions': sorted(transactions, key=lambda x: x['transaction_date'], reverse=True)
            }
            consolidated_assets.append(consolidated_asset)

    # Sort by total value descending
    consolidated_assets.sort(key=lambda x: x['total_current_value'], reverse=True)

    # Get cash account info
    cash_info = None
    if hasattr(portfolio, 'cash_account'):
        cash_info = {
            'balance': float(portfolio.cash_account.balance),
            'currency': portfolio.cash_account.currency,
            'last_updated': portfolio.cash_account.updated_at
        }

    # Calculate summary including cash
    securities_value = sum(item['total_current_value'] for item in consolidated_assets)
    securities_cost = sum(item['total_cost'] for item in consolidated_assets)
    cash_balance = cash_info['balance'] if cash_info else 0

    summary = {
        'total_value': securities_value + cash_balance,  # Include cash in total value
        'securities_value': securities_value,
        'cash_balance': cash_balance,
        'total_cost': securities_cost,
        'total_gain_loss': sum(item['total_gain_loss'] for item in consolidated_assets),
        'total_dividends': sum(item['total_dividends'] for item in consolidated_assets),
        'unique_assets': len(consolidated_assets),
        'total_transactions': sum(len(item['transactions']) for item in consolidated_assets)
    }

    return Response({
        'portfolio': PortfolioSerializer(portfolio).data,
        'consolidated_assets': consolidated_assets,
        'cash_account': cash_info,
        'summary': summary
    })