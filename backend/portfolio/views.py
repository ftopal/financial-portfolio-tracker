from datetime import timedelta, datetime
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from portfolio_project import settings
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, CashTransaction, UserPreferences,
    Currency, ExchangeRate
)
from .serializers import (
    PortfolioSerializer, PortfolioDetailSerializer,
    AssetCategorySerializer, SecuritySerializer,
    TransactionSerializer, CashTransactionSerializer, UserPreferencesSerializer,
    CurrencySerializer, ExchangeRateSerializer, CurrencyConversionSerializer
)
from .services.security_import_service import SecurityImportService
from .services.currency_service import CurrencyService
import logging

logger = logging.getLogger(__name__)


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for currencies"""
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """Convert amount between currencies"""
        serializer = CurrencyConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            converted_amount = CurrencyService.convert_amount(
                serializer.validated_data['amount'],
                serializer.validated_data['from_currency'],
                serializer.validated_data['to_currency'],
                serializer.validated_data.get('date')
            )

            return Response({
                'amount': serializer.validated_data['amount'],
                'from_currency': serializer.validated_data['from_currency'],
                'to_currency': serializer.validated_data['to_currency'],
                'converted_amount': converted_amount,
                'date': serializer.validated_data.get('date', timezone.now().date())
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def update_rates(self, request):
        """Manually trigger exchange rate update"""
        CurrencyService.update_exchange_rates()
        return Response({'status': 'Exchange rates update initiated'})


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for exchange rates"""
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ExchangeRate.objects.all()

        # Filter by currencies if provided
        from_currency = self.request.query_params.get('from_currency')
        to_currency = self.request.query_params.get('to_currency')
        date = self.request.query_params.get('date')

        if from_currency:
            queryset = queryset.filter(from_currency=from_currency)
        if to_currency:
            queryset = queryset.filter(to_currency=to_currency)
        if date:
            queryset = queryset.filter(date=date)

        return queryset.order_by('-date')[:100]  # Limit to 100 most recent


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
        """Deposit cash to portfolio"""
        portfolio = self.get_object()
        amount = Decimal(str(request.data.get('amount', 0)))

        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        # Get or create cash account using the correct model name
        from .models import PortfolioCashAccount, CashTransaction
        cash_account, created = PortfolioCashAccount.objects.get_or_create(
            portfolio=portfolio,
            defaults={'balance': Decimal('0'), 'currency': portfolio.base_currency}
        )

        # Create cash transaction
        transaction = CashTransaction.objects.create(
            cash_account=cash_account,
            user=request.user,
            transaction_type='DEPOSIT',
            amount=amount,
            description=request.data.get('description', 'Cash deposit'),
            transaction_date=request.data.get('transaction_date', timezone.now()),
            balance_after=cash_account.balance + amount
        )

        # Update cash account balance
        cash_account.balance += amount
        cash_account.save()

        serializer = CashTransactionSerializer(transaction)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=['post'])
    def withdraw_cash(self, request, pk=None):
        """Withdraw cash from portfolio"""
        portfolio = self.get_object()
        amount = Decimal(str(request.data.get('amount', 0)))

        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        # Get or create cash account using the correct model name
        from .models import PortfolioCashAccount, CashTransaction
        cash_account, created = PortfolioCashAccount.objects.get_or_create(
            portfolio=portfolio,
            defaults={'balance': Decimal('0'), 'currency': portfolio.base_currency}
        )

        if cash_account.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        # Create cash transaction
        transaction = CashTransaction.objects.create(
            cash_account=cash_account,
            user=request.user,
            transaction_type='WITHDRAWAL',
            amount=-amount,  # Negative for withdrawal
            description=request.data.get('description', 'Cash withdrawal'),
            transaction_date=request.data.get('transaction_date', timezone.now()),
            balance_after=cash_account.balance - amount
        )

        # Update cash account balance
        cash_account.balance -= amount
        cash_account.save()

        serializer = CashTransactionSerializer(transaction)
        return Response(serializer.data, status=201)

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

    @action(detail=True, methods=['get'])
    def value(self, request, pk=None):
        """Get portfolio value in specified currency"""
        portfolio = self.get_object()
        currency = request.query_params.get('currency', portfolio.currency)
        date = request.query_params.get('date')

        if date:
            date = datetime.strptime(date, '%Y-%m-%d').date()

        try:
            value = CurrencyService.get_portfolio_value_in_currency(
                portfolio, currency, date
            )

            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'base_currency': portfolio.currency,
                'target_currency': currency,
                'value': value,
                'date': date or timezone.now().date()
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def supported_currencies(self, request):
        """Get list of supported currencies for portfolios"""
        # First try to get active currencies from database
        currencies_qs = Currency.objects.filter(is_active=True).values_list('code', flat=True)

        if currencies_qs.exists():
            currencies = list(currencies_qs)
        else:
            # Fallback to settings if no currencies in database
            currencies = getattr(settings, 'SUPPORTED_CURRENCIES',
                                 ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY'])

        return Response({
            'currencies': currencies,
            'default': getattr(settings, 'DEFAULT_CURRENCY', 'USD')
        })

    @action(detail=True, methods=['get'])
    def currency_exposure(self, request, pk=None):
        """Get portfolio exposure by currency"""
        portfolio = self.get_object()
        exposure = CurrencyService.get_currency_exposure(portfolio)

        # Convert to target currency if requested
        target_currency = request.query_params.get('currency')
        if target_currency:
            converted_exposure = {}
            total = Decimal('0')

            for currency, amount in exposure.items():
                if currency == target_currency:
                    converted_exposure[currency] = {
                        'amount': amount,
                        'converted_amount': amount,
                        'percentage': 0  # Will calculate after
                    }
                    total += amount
                else:
                    converted_amount = CurrencyService.convert_amount(
                        amount, currency, target_currency
                    )
                    converted_exposure[currency] = {
                        'amount': amount,
                        'converted_amount': converted_amount,
                        'percentage': 0  # Will calculate after
                    }
                    total += converted_amount

            # Calculate percentages
            for currency in converted_exposure:
                if total > 0:
                    converted_exposure[currency]['percentage'] = float(
                        (converted_exposure[currency]['converted_amount'] / total) * 100
                    )

            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'target_currency': target_currency,
                'total_value': total,
                'exposure': converted_exposure
            })
        else:
            # Return raw exposure
            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'exposure': exposure
            })

    @action(detail=True, methods=['post'])
    def recalculate_cash_balance(self, request, pk=None):
        """Recalculate cash balance for this portfolio based on all transactions"""
        portfolio = self.get_object()

        try:
            from .models import PortfolioCashAccount
            cash_account, created = PortfolioCashAccount.objects.get_or_create(
                portfolio=portfolio,
                defaults={'balance': Decimal('0'), 'currency': portfolio.base_currency}
            )

            if created:
                return Response({'message': 'Cash account created', 'balance': float(cash_account.balance)})

            old_balance = cash_account.balance

            # Recalculate balance from all transactions
            from django.db.models import Sum
            total_amount = cash_account.transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0')

            cash_account.balance = total_amount
            cash_account.save()

            difference = cash_account.balance - old_balance

            return Response({
                'message': 'Cash balance recalculated successfully',
                'old_balance': float(old_balance),
                'new_balance': float(cash_account.balance),
                'difference': float(difference),
                'transaction_count': cash_account.transactions.count()
            })

        except Exception as e:
            return Response({'error': f'Failed to recalculate balance: {str(e)}'}, status=500)

    @action(detail=True, methods=['get'])
    def verify_cash_balance(self, request, pk=None):
        """Verify that the cash balance is consistent with transaction history"""
        portfolio = self.get_object()

        try:
            from .models import PortfolioCashAccount
            try:
                cash_account = PortfolioCashAccount.objects.get(portfolio=portfolio)
            except PortfolioCashAccount.DoesNotExist:
                return Response({
                    'is_consistent': True,
                    'message': 'No cash account exists yet',
                    'stored_balance': 0,
                    'calculated_balance': 0,
                    'difference': 0
                })

            # Calculate what the balance should be
            from django.db.models import Sum
            calculated_balance = cash_account.transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0')

            difference = cash_account.balance - calculated_balance
            is_consistent = abs(difference) < Decimal('0.01')

            return Response({
                'is_consistent': is_consistent,
                'stored_balance': float(cash_account.balance),
                'calculated_balance': float(calculated_balance),
                'difference': float(difference),
                'transaction_count': cash_account.transactions.count(),
                'message': 'Balance is consistent' if is_consistent else f'Balance inconsistency detected. Difference: {difference}'
            })

        except Exception as e:
            return Response({'error': f'Failed to verify balance: {str(e)}'}, status=500)


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

        try:
            service = SecurityImportService()
            # Fix: Call the correct method name
            result = service.search_and_import_security(symbol)

            if result.get('error'):
                return Response({'error': result['error']}, status=400)

            return Response({
                'security': SecuritySerializer(result['security']).data,
                'created': result.get('created', False),
                'exists': result.get('exists', False)
            })
        except Exception as e:
            logger.error(f"Error importing security {symbol}: {str(e)}")
            return Response(
                {'error': f'Failed to import {symbol}. Please check the symbol and try again.'},
                status=400
            )

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

        # Skip cash transactions for splits - they don't involve money
        if transaction.transaction_type == 'SPLIT':
            return

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
            # Note: transaction.total_value already returns NET dividend (after fees) from the model property
            dividend_amount = transaction.total_value

            # Create description that includes fee information
            description = f'Dividend from {transaction.security.symbol}'
            if transaction.fees > 0:
                description += f' (net after {transaction.fees} {transaction.currency} fees)'

            CashTransaction.objects.create(
                cash_account=cash_account,
                user=self.request.user,
                transaction_type='DIVIDEND',
                amount=dividend_amount,
                description=description,
                transaction_date=transaction.transaction_date,
                related_transaction=transaction
            )
            cash_account.update_balance(dividend_amount)

    def perform_destroy(self, instance):
        """Override to handle cash transaction cleanup when deleting a transaction"""

        # Store the transaction details for logging
        transaction_type = instance.transaction_type
        security_symbol = instance.security.symbol

        # Check if there's a related cash transaction
        if hasattr(instance, 'cash_transaction'):
            cash_transaction = instance.cash_transaction
            cash_account = cash_transaction.cash_account

            # Reverse the cash balance change
            # The amount in cash_transaction is negative for outflows (BUY)
            # and positive for inflows (SELL, DIVIDEND)
            reversal_amount = -cash_transaction.amount

            # Update the cash balance
            cash_account.update_balance(reversal_amount)

            # Delete the cash transaction
            # This will happen automatically due to CASCADE when we delete the transaction
            # but we can do it explicitly for clarity
            cash_transaction.delete()

            # Log the action
            print(f"Deleted {transaction_type} transaction for {security_symbol}, "
                  f"reversed cash amount: {reversal_amount}")

        # Delete the transaction itself
        super().perform_destroy(instance)


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

    def destroy(self, request, *args, **kwargs):
        """
        Override destroy to:
        1. Prevent deletion of auto-generated cash transactions
        2. Update cash account balance when deleting manual transactions
        """
        instance = self.get_object()

        # Check if this cash transaction is related to a security transaction
        if instance.related_transaction:
            return Response(
                {'error': 'Cannot delete cash transactions that are linked to security transactions. '
                          'Please delete the security transaction instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Store the cash account and transaction details before deletion
        cash_account = instance.cash_account
        transaction_amount = instance.amount
        transaction_type = instance.transaction_type

        # Log the operation for debugging
        logger.info(f"Deleting cash transaction: {transaction_type} of {transaction_amount}")
        logger.info(f"Current cash balance before deletion: {cash_account.balance}")

        # **CRITICAL FIX: Update the cash account balance by reversing the transaction**
        reversal_amount = -transaction_amount

        logger.info(f"Applying reversal amount: {reversal_amount}")

        # Update the cash account balance
        cash_account.update_balance(reversal_amount)

        logger.info(f"New cash balance after reversal: {cash_account.balance}")

        # Delete the transaction
        response = super().destroy(request, *args, **kwargs)

        # Return success response with updated balance info
        return Response({
            'message': f'{transaction_type} transaction deleted successfully',
            'new_balance': float(cash_account.balance),
            'reversed_amount': float(reversal_amount)
        }, status=status.HTTP_200_OK)


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

    holdings = portfolio.get_holdings_cached()

    # DEBUG: Let's see what get_holdings() actually calculated
    for security_id, data in holdings.items():
        if data['security'].symbol == 'GOOG':
            print(f"DEBUG: get_holdings() calculated for GOOG:")
            print(f"  total_cost_base_currency: {data.get('total_cost_base_currency', 'NOT_FOUND')}")
            print(f"  avg_cost_base_currency: {data.get('avg_cost_base_currency', 'NOT_FOUND')}")
            print(f"  quantity: {data.get('quantity', 'NOT_FOUND')}")
            print(f"  total_dividends: {data.get('total_dividends', 'NOT_FOUND')}")

    consolidated_assets = []
    portfolio_currency = portfolio.base_currency or portfolio.currency

    for security_id, data in holdings.items():
        # Build transactions list
        transactions = []

        # Calculate proper average costs in both currencies
        portfolio_base_currency = portfolio.base_currency or portfolio.currency
        security_currency = data['security'].currency

        # ✅ USE the correct values from get_holdings() (which already accounts for dividends but NOT fees)
        # For portfolio currency, we need to add fees to the cost basis
        total_cost_portfolio_currency = data.get('total_cost_base_currency', Decimal('0'))

        # Add fees to the total cost for portfolio currency
        fees_total_portfolio_currency = Decimal('0')
        for transaction in data['transactions']:
            if transaction.transaction_type == 'BUY':
                if transaction.base_amount:
                    # base_amount includes fees, so calculate fees from the difference
                    cost_without_fees = (transaction.quantity * transaction.price) * (
                                transaction.exchange_rate or Decimal('1'))
                    fees_total_portfolio_currency += transaction.base_amount - cost_without_fees
                else:
                    fees_total_portfolio_currency += transaction.fees * (transaction.exchange_rate or Decimal('1'))
            elif transaction.transaction_type == 'SELL':
                if data['quantity'] > 0:
                    # Reduce fees proportionally for sells
                    cost_per_share = fees_total_portfolio_currency / (data['quantity'] + transaction.quantity)
                    fees_total_portfolio_currency -= cost_per_share * transaction.quantity

        # Add fees to total cost
        total_cost_portfolio_currency += fees_total_portfolio_currency

        # Calculate average cost including fees
        if data['quantity'] > 0:
            avg_cost_portfolio_currency = total_cost_portfolio_currency / data['quantity']
        else:
            avg_cost_portfolio_currency = Decimal('0')

        # For security currency, we need to calculate total cost including fees
        # get_holdings() only tracks quantity * price, not fees
        total_cost_security_currency = Decimal('0')

        # Calculate total cost including fees from transactions
        for transaction in data['transactions']:
            if transaction.transaction_type == 'BUY':
                total_cost_security_currency += (transaction.quantity * transaction.price) + transaction.fees
            elif transaction.transaction_type == 'SELL':
                # For SELL, reduce cost basis proportionally
                if data['quantity'] > 0:
                    cost_per_share = total_cost_security_currency / (data['quantity'] + transaction.quantity)
                    total_cost_security_currency -= cost_per_share * transaction.quantity
            elif transaction.transaction_type == 'DIVIDEND':
                # Dividends reduce cost basis
                if transaction.dividend_per_share:
                    dividend_amount = transaction.quantity * transaction.dividend_per_share
                else:
                    dividend_amount = transaction.price or Decimal('0')
                total_cost_security_currency -= dividend_amount

        # Calculate average cost in security currency
        if data['quantity'] > 0:
            avg_cost_security_currency = total_cost_security_currency / data['quantity']
        else:
            avg_cost_security_currency = Decimal('0')

        # Get current value in base currency (using CURRENT exchange rate)
        current_value_base_currency = data.get('current_value_base_currency', Decimal('0'))

        for transaction in data['transactions']:
            # Calculate gain/loss for this specific transaction in its original currency
            if transaction.transaction_type == 'BUY':
                # Current value of the shares bought in this transaction
                current_value = transaction.quantity * data['security'].current_price

                # Total cost INCLUDING FEES in transaction currency
                total_cost_with_fees = (transaction.quantity * transaction.price) + transaction.fees

                # Gain/Loss in transaction currency
                gain_loss_total = current_value - total_cost_with_fees

                # Percentage based on total cost including fees
                gain_loss_percentage = (gain_loss_total / total_cost_with_fees * 100) if total_cost_with_fees > 0 else 0

                # Convert gain/loss to portfolio currency using CURRENT exchange rate
                if transaction.currency != portfolio_currency:
                    try:
                        from .services.currency_service import CurrencyService
                        # Use current exchange rate for gain/loss conversion
                        current_exchange_rate = CurrencyService.get_exchange_rate(
                            transaction.currency,
                            portfolio_currency
                        )

                        if current_exchange_rate:
                            gain_loss_base_currency = gain_loss_total * current_exchange_rate
                        else:
                            # Fallback to historical rate if current rate not available
                            gain_loss_base_currency = gain_loss_total * (transaction.exchange_rate or 1)
                    except Exception as e:
                        # Fallback to historical rate if conversion fails
                        gain_loss_base_currency = gain_loss_total * (transaction.exchange_rate or 1)
                else:
                    gain_loss_base_currency = gain_loss_total

                # Convert total cost to portfolio currency using HISTORICAL rate (transaction date rate)
                if transaction.currency != portfolio_currency and transaction.exchange_rate:
                    total_cost_base_currency = total_cost_with_fees * transaction.exchange_rate
                else:
                    total_cost_base_currency = total_cost_with_fees

                transaction_data = {
                    'id': transaction.id,
                    'date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_type': transaction.transaction_type,
                    'quantity': float(transaction.quantity),
                    'price': float(transaction.price),
                    'fees': float(transaction.fees or 0),
                    'value': float(total_cost_base_currency),  # Show converted amount as primary
                    'value_original': float(total_cost_with_fees),  # Original amount
                    'total_cost': float(total_cost_with_fees),
                    'gain_loss': float(gain_loss_total),  # In original currency
                    'gain_loss_total': float(gain_loss_total),
                    'gain_loss_base_currency': float(gain_loss_base_currency),  # Converted using current rate
                    'gain_loss_percentage': float(gain_loss_percentage),
                    'currency': transaction.currency,
                    'exchange_rate': float(transaction.exchange_rate or 1),
                    'stock_id': transaction.security.id
                }
            elif transaction.transaction_type == 'DIVIDEND':
                # For dividends, calculate the actual dividend amount
                if transaction.dividend_per_share:
                    dividend_amount = transaction.quantity * transaction.dividend_per_share
                elif transaction.price:
                    # If dividend_per_share is not set, use price field
                    dividend_amount = transaction.price
                else:
                    dividend_amount = Decimal('0')

                # Convert to base currency
                if transaction.base_amount:
                    dividend_base_currency = transaction.base_amount
                else:
                    dividend_base_currency = dividend_amount * (transaction.exchange_rate or Decimal('1'))

                transaction_data = {
                    'id': transaction.id,
                    'date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_type': transaction.transaction_type,
                    'quantity': float(transaction.quantity),
                    'price': float(transaction.price or 0),
                    'fees': float(transaction.fees or 0),
                    'value': float(dividend_base_currency),  # Converted dividend amount
                    'value_original': float(dividend_amount),  # Original dividend amount
                    'total_amount': float(dividend_amount),
                    'currency': transaction.currency,
                    'exchange_rate': float(transaction.exchange_rate or 1),
                    'stock_id': transaction.security.id,
                    'dividend_per_share': float(
                        transaction.dividend_per_share) if transaction.dividend_per_share else None,
                    'base_amount': float(dividend_base_currency),
                    # For dividends, the gain/loss is the dividend amount itself
                    'gain_loss': float(dividend_amount),
                    'gain_loss_base_currency': float(dividend_base_currency)
                }
            else:
                # Handle other transaction types (SELL, etc.)
                total_amount = transaction.quantity * (transaction.price or 0)

                # Convert to base currency if needed
                if transaction.base_amount:
                    total_base_currency = transaction.base_amount
                else:
                    total_base_currency = total_amount * (transaction.exchange_rate or Decimal('1'))

                transaction_data = {
                    'id': transaction.id,
                    'date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
                    'transaction_type': transaction.transaction_type,
                    'quantity': float(transaction.quantity),
                    'price': float(transaction.price or 0),
                    'fees': float(transaction.fees or 0),
                    'value': float(total_base_currency),  # Converted amount
                    'value_original': float(total_amount),  # Original amount
                    'total_amount': float(total_amount),
                    'currency': transaction.currency,
                    'exchange_rate': float(transaction.exchange_rate or 1),
                    'stock_id': transaction.security.id
                }

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
                # Average cost in portfolio base currency (includes fees and dividend adjustments)
                'avg_cost_price': float(avg_cost_portfolio_currency),
                'avg_cost_price_original': float(avg_cost_security_currency),
                'security_currency': security_currency,
                # Current price in original currency
                'current_price': float(data['security'].current_price),
                'current_price_currency': security_currency,
                # Total value in portfolio base currency (using CURRENT exchange rate)
                'total_current_value': float(current_value_base_currency),
                # Total cost in portfolio base currency (dividend-adjusted and includes fees)
                'total_cost': float(total_cost_portfolio_currency),
                'total_cost_original': float(total_cost_security_currency),
                # Gain/loss in portfolio base currency (using CURRENT rate for current value)
                'total_gain_loss': float(current_value_base_currency - total_cost_portfolio_currency),
                'total_dividends': float(data['total_dividends']),
                'gain_loss_percentage': float(
                    ((
                                 current_value_base_currency - total_cost_portfolio_currency) / total_cost_portfolio_currency * 100)
                    if total_cost_portfolio_currency > 0 else 0
                ),
                'transactions': sorted(transactions, key=lambda x: x['date'], reverse=True)
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
        'total_value': securities_value + cash_balance,
        'securities_value': securities_value,
        'cash_balance': cash_balance,
        'total_cost': securities_cost,
        'total_gain_loss': sum(item['total_gain_loss'] for item in consolidated_assets),
        'total_dividends': sum(item['total_dividends'] for item in consolidated_assets),
        'unique_assets': len(consolidated_assets),
        'total_transactions': sum(len(item['transactions']) for item in consolidated_assets)
    }

    portfolio_data = {
        'id': portfolio.id,
        'name': portfolio.name,
        'description': portfolio.description,
        'currency': portfolio.currency,
        'base_currency': portfolio.base_currency,
        'is_default': portfolio.is_default,
        'created_at': portfolio.created_at,
        'updated_at': portfolio.updated_at,
        # Add the summary data directly
        'total_value': summary['total_value'],
        'total_cost': summary['total_cost'],
        'total_gains': summary['total_gain_loss'],
        'total_gain_loss': summary['total_gain_loss'],
        'gain_loss_percentage': (summary['total_gain_loss'] / summary['total_cost'] * 100) if summary['total_cost'] > 0 else 0,
        'holdings_count': summary['unique_assets'],
        'asset_count': summary['unique_assets'],
        'transaction_count': summary['total_transactions'],
        'cash_balance': cash_balance,
        'total_value_with_cash': summary['total_value']
    }

    return Response({
        'portfolio': portfolio_data,
        'consolidated_assets': consolidated_assets,
        'cash_account': cash_info,
        'summary': summary
    })