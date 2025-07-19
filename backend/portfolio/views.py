from datetime import timedelta, datetime, date
from decimal import Decimal

from typing import Dict, List, Optional

from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from portfolio_project import settings
from .models import (
    Portfolio, AssetCategory, Security, Transaction,
    PriceHistory, CashTransaction, UserPreferences,
    Currency, ExchangeRate, PortfolioValueHistory
)
from .serializers import (
    PortfolioSerializer, PortfolioDetailSerializer,
    AssetCategorySerializer, SecuritySerializer,
    TransactionSerializer, CashTransactionSerializer, UserPreferencesSerializer,
    CurrencySerializer, ExchangeRateSerializer, CurrencyConversionSerializer
)
from .services.security_import_service import SecurityImportService
from .services.currency_service import CurrencyService
from .services.portfolio_history_service import PortfolioHistoryService
import logging
import math

logger = logging.getLogger(__name__)


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for currencies"""
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """Convert amount between currencies"""
        logger.info(f"Currency conversion request received: {request.data}")

        serializer = CurrencyConversionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        logger.info(f"Validated data: {validated_data}")

        try:
            # Extract values
            amount = validated_data['amount']
            from_currency = validated_data['from_currency']
            to_currency = validated_data['to_currency']
            conversion_date = validated_data.get('date')

            logger.info(f"Converting {amount} from {from_currency} to {to_currency} on {conversion_date}")

            # Special handling for GBp conversions
            # Don't use .upper() because it will convert 'GBp' to 'GBP'
            if from_currency == 'GBp' or to_currency == 'GBp':
                # Use the normalization method directly
                converted_amount = CurrencyService.convert_amount_with_normalization(
                    amount, from_currency, to_currency, conversion_date
                )
            else:
                # Check if currencies are active
                from_currency_active = Currency.objects.filter(code=from_currency, is_active=True).exists()
                to_currency_active = Currency.objects.filter(code=to_currency, is_active=True).exists()

                logger.info(
                    f"Currency status - {from_currency} active: {from_currency_active}, {to_currency} active: {to_currency_active}")

                if not from_currency_active:
                    error_msg = f"Currency '{from_currency}' is not active or not found"
                    logger.error(error_msg)
                    return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

                if not to_currency_active:
                    error_msg = f"Currency '{to_currency}' is not active or not found"
                    logger.error(error_msg)
                    return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

                # Standard conversion
                converted_amount = CurrencyService.convert_amount(
                    amount,
                    from_currency,
                    to_currency,
                    conversion_date
                )

            logger.info(f"Conversion successful: {converted_amount}")

            return Response({
                'amount': amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'converted_amount': converted_amount,
                'date': conversion_date
            })

        except ValueError as e:
            error_msg = str(e)
            logger.error(f"Currency conversion failed: {error_msg}")
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            error_msg = f"Unexpected error during currency conversion: {str(e)}"
            logger.error(error_msg)
            return Response(
                {'error': 'Currency conversion failed due to an internal error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        try:
            portfolio = self.get_object()
        except Portfolio.DoesNotExist:
            return Response(
                {'error': 'Portfolio not found'},
                status=status.HTTP_404_NOT_FOUND
            )
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
        """
        Get portfolio performance data with chart data
        Fixed version to handle all calculation issues
        """
        portfolio = get_object_or_404(Portfolio, pk=pk)

        # Get query parameters
        period = request.query_params.get('period', '1Y')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        try:
            # Calculate date range
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else date.today()

            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date_obj = self.get_period_start_date(period, end_date_obj)

            # Get portfolio performance data
            performance_data = self.get_portfolio_performance_data(
                portfolio, start_date_obj, end_date_obj
            )

            # Apply retention policy
            retention_applied = self.apply_retention_policy(
                request.user, start_date_obj, end_date_obj
            )

            if retention_applied:
                performance_data['retention_applied'] = True
                performance_data['retention_message'] = (
                    f"Historical data limited to {self.get_user_retention_days(request.user)} days. "
                    "Upgrade to Premium for unlimited access."
                )

            return Response(performance_data)

        except ValueError as e:
            return Response(
                {'error': f'Invalid date format: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting portfolio performance: {str(e)}")
            return Response(
                {'error': 'Failed to retrieve portfolio performance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_portfolio_performance_data(self, portfolio, start_date, end_date):
        """
        Get comprehensive portfolio performance data
        """
        from portfolio.services.portfolio_history_service import PortfolioHistoryService

        # Ensure we have portfolio value history
        self.ensure_portfolio_history(portfolio, start_date, end_date)

        # Get performance data from service
        performance_result = PortfolioHistoryService.get_portfolio_performance(
            portfolio, start_date, end_date
        )

        if not performance_result['success']:
            raise Exception(f"Failed to get performance data: {performance_result.get('error')}")

        # Get current portfolio value
        current_value_result = PortfolioHistoryService.calculate_portfolio_value_on_date(
            portfolio, date.today()
        )

        current_value = current_value_result['total_value'] if current_value_result['success'] else Decimal('0')

        # Format chart data for ApexCharts
        chart_data = []
        categories = []

        for data_point in performance_result['chart_data']:
            chart_data.append({
                'x': data_point['date'].strftime('%Y-%m-%d'),
                'y': float(data_point['value'])
            })
            categories.append(data_point['date'].strftime('%Y-%m-%d'))

        return {
            'success': True,
            'portfolio_id': portfolio.id,
            'portfolio_name': portfolio.name,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_days': (end_date - start_date).days
            },
            'current_value': float(current_value),
            'performance_metrics': {
                'total_return': float(performance_result['total_return']),
                'total_return_percentage': float(performance_result['total_return_percentage']),
                'volatility': float(performance_result['volatility']),
                'best_day': float(performance_result['best_day']),
                'worst_day': float(performance_result['worst_day']),
                'positive_days': performance_result['positive_days'],
                'negative_days': performance_result['negative_days'],
                'total_days': performance_result['total_days']
            },
            'chart_data': {
                'series': [{
                    'name': 'Portfolio Value',
                    'data': chart_data
                }],
                'categories': categories
            },
            'data_points': len(chart_data),
            'retention_applied': False
        }

    def ensure_portfolio_history(self, portfolio, start_date, end_date):
        """
        Ensure portfolio has complete value history for the requested period
        """
        from portfolio.services.portfolio_history_service import PortfolioHistoryService
        from portfolio.models import PortfolioValueHistory

        # Check if we have complete data
        existing_count = PortfolioValueHistory.objects.filter(
            portfolio=portfolio,
            date__gte=start_date,
            date__lte=end_date
        ).count()

        # Calculate expected business days
        expected_days = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                expected_days += 1
            current_date += timedelta(days=1)

        # If we're missing more than 10% of expected data, trigger backfill
        if existing_count < (expected_days * 0.9):
            logger.info(f"Backfilling portfolio history for {portfolio.name}")

            # Backfill missing data
            result = PortfolioHistoryService.backfill_portfolio_history(
                portfolio, start_date, end_date, force_update=False
            )

            if not result['success']:
                logger.error(f"Failed to backfill portfolio history: {result.get('error')}")

    def get_period_start_date(self, period, end_date):
        """
        Calculate start date based on period
        """
        if period == '1M':
            return end_date - timedelta(days=30)
        elif period == '3M':
            return end_date - timedelta(days=90)
        elif period == '6M':
            return end_date - timedelta(days=180)
        elif period == '1Y':
            return end_date - timedelta(days=365)
        elif period == 'YTD':
            return date(end_date.year, 1, 1)
        elif period == 'ALL':
            # Find the earliest transaction date
            earliest_transaction = Transaction.objects.filter(
                portfolio__user=self.request.user
            ).order_by('transaction_date').first()
            if earliest_transaction:
                return earliest_transaction.transaction_date.date()
            else:
                return end_date - timedelta(days=365)
        else:
            return end_date - timedelta(days=365)

    def apply_retention_policy(self, user, start_date, end_date):
        """
        Apply user retention policy
        """
        retention_days = self.get_user_retention_days(user)

        if retention_days is None:
            return False  # No retention limit

        cutoff_date = date.today() - timedelta(days=retention_days)

        return start_date < cutoff_date

    def get_user_retention_days(self, user):
        """
        Get user's data retention limit in days
        """
        # TODO: Implement user tier checking
        # For now, return 365 days for free users
        return 365

    @action(detail=True, methods=['post'])
    def deposit_cash(self, request, pk=None):
        """Deposit cash to portfolio"""
        portfolio = self.get_object()
        amount = Decimal(str(request.data.get('amount', 0)))

        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        # Get or create cash account
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
        )

        # Recalculate all balances
        cash_account.recalculate_balances()

        # Refresh transaction to get updated balance_after
        transaction.refresh_from_db()

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
        )

        # Recalculate all balances (same as deposit_cash method)
        cash_account.recalculate_balances()

        # Refresh transaction to get updated balance_after
        transaction.refresh_from_db()

        serializer = CashTransactionSerializer(transaction)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=['get'])
    def cash_history(self, request, pk=None):
        """Get cash transaction history for portfolio with proper pagination"""
        portfolio = self.get_object()

        try:
            transactions = CashTransaction.objects.filter(
                cash_account=portfolio.cash_account
            ).select_related('related_transaction__security').order_by('-transaction_date', '-created_at')

            # Optional filtering
            transaction_type = request.query_params.get('transaction_type')
            if transaction_type:
                transactions = transactions.filter(transaction_type=transaction_type)

            start_date = request.query_params.get('start_date')
            if start_date:
                transactions = transactions.filter(transaction_date__gte=start_date)

            end_date = request.query_params.get('end_date')
            if end_date:
                transactions = transactions.filter(transaction_date__lte=end_date)

            # Get total count before pagination
            total_count = transactions.count()

            # Pagination with default page size of 20
            page_size = int(request.query_params.get('page_size', 20))
            page_number = int(request.query_params.get('page', 1))

            # Ensure page size is within reasonable limits
            page_size = min(max(page_size, 1), 100)

            # Ensure page number is valid
            max_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            page_number = min(max(page_number, 1), max_pages)

            # Set pagination page size for this request
            self.paginator.page_size = page_size

            # Paginate the queryset
            page = self.paginate_queryset(transactions)
            if page is not None:
                serializer = CashTransactionSerializer(page, many=True)

                # Get the paginated response
                paginated_response = self.get_paginated_response(serializer.data)

                # Add additional pagination metadata
                paginated_response.data['current_page'] = page_number
                paginated_response.data['page_size'] = page_size
                paginated_response.data['total_pages'] = max_pages

                return paginated_response

            # Fallback for non-paginated response
            serializer = CashTransactionSerializer(transactions, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in cash_history: {str(e)}")
            return Response(
                {'error': f'Failed to fetch cash history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def value(self, request, pk=None):
        """Get portfolio value in specified currency"""
        portfolio = self.get_object()
        currency = request.query_params.get('currency', portfolio.base_currency)
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
                'base_currency': portfolio.base_currency,
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

    @action(detail=True, methods=['get'])
    def currency_exposure_chart(self, request, pk=None):
        """Get currency exposure data formatted for pie chart visualization"""
        portfolio = self.get_object()

        try:
            # Get raw exposure with normalization (for GBp -> GBP conversion)
            exposure = CurrencyService.get_currency_exposure(portfolio)

            if not exposure:
                return Response({
                    'portfolio_id': portfolio.id,
                    'portfolio_name': portfolio.name,
                    'base_currency': portfolio.base_currency,
                    'chart_data': [],
                    'total_value': 0,
                    'message': 'No currency exposure data available'
                })

            # Get target currency for conversion (or use portfolio base currency)
            target_currency = request.query_params.get('currency')
            if not target_currency:
                target_currency = portfolio.base_currency

            # Convert ALL amounts to target currency for proper percentage calculation
            converted_exposure = {}
            total_converted_value = Decimal('0')

            for currency, amount in exposure.items():
                if currency == target_currency:
                    converted_amount = amount
                else:
                    converted_amount = CurrencyService.convert_amount(
                        amount, currency, target_currency
                    )

                converted_exposure[currency] = {
                    'original_amount': amount,
                    'original_currency': currency,
                    'converted_amount': converted_amount,
                    'target_currency': target_currency
                }
                total_converted_value += converted_amount

            # Format data for pie chart with CORRECT percentages
            chart_data = []
            for currency, data in converted_exposure.items():
                # Calculate percentage based on CONVERTED amounts
                percentage = float(
                    (data['converted_amount'] / total_converted_value) * 100) if total_converted_value > 0 else 0

                chart_data.append({
                    'currency': currency,
                    'amount': float(data['converted_amount']),  # Show converted amount
                    'original_amount': float(data['original_amount']),  # Keep original for reference
                    'percentage': round(percentage, 2),  # Correct percentage based on converted values
                    'formatted_amount': f"{data['converted_amount']:,.2f}",
                    'color': self._get_currency_color(currency)
                })

            # Sort by converted amount (largest first)
            chart_data.sort(key=lambda x: x['amount'], reverse=True)

            response_data = {
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'base_currency': portfolio.base_currency,
                'target_currency': target_currency,
                'chart_data': chart_data,
                'total_value': float(total_converted_value),  # Total in target currency
                'currency_count': len(chart_data),
                'note': f'All amounts converted to {target_currency} for percentage calculation'
            }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error getting currency exposure chart data: {e}")
            return Response(
                {'error': f'Failed to get currency chart data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_currency_color(self, currency):
        """Get consistent color for each currency"""
        # Predefined colors for common currencies
        currency_colors = {
            'USD': '#2196F3',  # Blue
            'EUR': '#4CAF50',  # Green
            'GBP': '#FF9800',  # Orange
        }

        # Return predefined color or generate one based on currency code
        if currency in currency_colors:
            return currency_colors[currency]
        else:
            # Generate a color based on currency code hash
            import hashlib
            hash_obj = hashlib.md5(currency.encode())
            hash_hex = hash_obj.hexdigest()
            # Use first 6 characters as color hex
            return f"#{hash_hex[:6]}"

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

    @action(detail=True, methods=['post'])
    def check_auto_deposit(self, request, pk=None):
        """Check if auto-deposit would be triggered for a transaction"""
        portfolio = self.get_object()

        try:
            # Get transaction details from request
            transaction_type = request.data.get('transaction_type')
            total_cost = Decimal(str(request.data.get('total_cost', 0)))

            # Only check for BUY transactions
            if transaction_type != 'BUY' or total_cost <= 0:
                return Response({
                    'auto_deposit_needed': False,
                    'current_balance': float(portfolio.cash_account.balance),
                    'total_cost': float(total_cost),
                    'message': 'No auto-deposit needed for this transaction type'
                })

            # Get user preferences
            preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

            # Get cash account
            cash_account = portfolio.cash_account

            # Recalculate balance to ensure accuracy
            cash_account.recalculate_balances()

            # Check if sufficient balance exists
            has_sufficient_balance = cash_account.has_sufficient_balance(total_cost)

            if has_sufficient_balance:
                return Response({
                    'auto_deposit_needed': False,
                    'current_balance': float(cash_account.balance),
                    'total_cost': float(total_cost),
                    'shortfall': 0,
                    'message': 'Sufficient balance available'
                })

            # Calculate auto-deposit details
            if not preferences.auto_deposit_enabled:
                return Response({
                    'auto_deposit_needed': False,
                    'current_balance': float(cash_account.balance),
                    'total_cost': float(total_cost),
                    'shortfall': float(total_cost - cash_account.balance),
                    'message': 'Auto-deposit is disabled. Transaction will fail due to insufficient funds.',
                    'error': 'Insufficient cash balance'
                })

            # Calculate deposit amount based on user preference
            if preferences.auto_deposit_mode == 'EXACT':
                deposit_amount = total_cost
            else:  # SHORTFALL
                deposit_amount = total_cost - cash_account.balance

            return Response({
                'auto_deposit_needed': True,
                'auto_deposit_enabled': preferences.auto_deposit_enabled,
                'auto_deposit_mode': preferences.auto_deposit_mode,
                'current_balance': float(cash_account.balance),
                'total_cost': float(total_cost),
                'shortfall': float(total_cost - cash_account.balance),
                'deposit_amount': float(deposit_amount),
                'new_balance_after_deposit': float(cash_account.balance + deposit_amount),
                'currency': cash_account.currency,
                'message': f'Auto-deposit of {deposit_amount} {cash_account.currency} will be created'
            })

        except Exception as e:
            return Response({
                'error': f'Failed to check auto-deposit: {str(e)}'
            }, status=400)

    @action(detail=True, methods=['get'])
    def xirr(self, request, pk=None):
        """Get XIRR calculations for portfolio and all assets"""
        portfolio = self.get_object()

        try:
            from .services.xirr_service import XIRRService

            # Check if force recalculation is requested
            force_recalculate = request.query_params.get('force', '').lower() == 'true'

            # Calculate portfolio XIRR
            portfolio_xirr = XIRRService.get_portfolio_xirr(portfolio, force_recalculate)

            # Calculate asset XIRRs
            asset_xirrs = XIRRService.get_all_asset_xirrs(portfolio, force_recalculate)

            # Convert Decimals to floats for JSON serialization
            portfolio_xirr_float = float(portfolio_xirr) if portfolio_xirr is not None else None
            asset_xirrs_float = {
                str(security_id): float(xirr) if xirr is not None else None
                for security_id, xirr in asset_xirrs.items()
            }

            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'portfolio_xirr': portfolio_xirr_float,
                'asset_xirrs': asset_xirrs_float,
                'calculated_at': timezone.now().isoformat(),
                'cache_info': {
                    'force_recalculated': force_recalculate,
                    'total_assets': len(asset_xirrs_float),
                    'assets_with_xirr': len([x for x in asset_xirrs_float.values() if x is not None])
                }
            })

        except Exception as e:
            logger.error(f"XIRR calculation error for portfolio {portfolio.id}: {e}")
            return Response(
                {
                    'error': 'XIRR calculation failed',
                    'detail': str(e) if request.user.is_staff else 'Internal error',
                    'portfolio_id': portfolio.id
                },
                status=500
            )

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Get portfolio performance data for charts

        Query Parameters:
        - period: 1M, 3M, 6M, 1Y, YTD, ALL (default: 1Y)
        - start_date: YYYY-MM-DD format (overrides period)
        - end_date: YYYY-MM-DD format (defaults to today)
        """
        try:
            portfolio = self.get_object()

            # Check user permissions
            if portfolio.user != request.user:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Parse query parameters
            period = request.query_params.get('period', '1Y')
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            # Calculate date range
            end_date = date.today()
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {'error': 'Invalid end_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Calculate start date based on period or explicit start_date
            start_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                start_date = self._calculate_period_start_date(period, end_date)

            # Apply retention policy for free users
            retention_limit = self._get_user_retention_limit(request.user)
            if retention_limit:
                earliest_allowed = end_date - timedelta(days=retention_limit)
                if start_date < earliest_allowed:
                    start_date = earliest_allowed

            # Get performance data from service
            performance_data = PortfolioHistoryService.get_portfolio_performance(
                portfolio, start_date, end_date
            )

            if not performance_data['success']:
                return Response(
                    {'error': performance_data.get('error', 'Failed to calculate performance')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Format response for frontend (using correct keys from service)
            chart_data = self._format_chart_data(performance_data['chart_data'])

            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'chart_data': chart_data,
                'summary': performance_data['performance_summary'],  # FIXED: use correct key
                'retention_applied': retention_limit is not None
            })

        except Exception as e:
            logger.error(f"Error in portfolio performance endpoint: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def performance_summary(self, request, pk=None):
        """
        Get portfolio performance summary statistics

        Query Parameters:
        - period: 1M, 3M, 6M, 1Y, YTD, ALL (default: 1Y)
        """
        try:
            portfolio = self.get_object()

            # Check user permissions
            if portfolio.user != request.user:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            period = request.query_params.get('period', '1Y')
            end_date = date.today()
            start_date = self._calculate_period_start_date(period, end_date)

            # Apply retention policy
            retention_limit = self._get_user_retention_limit(request.user)
            if retention_limit:
                earliest_allowed = end_date - timedelta(days=retention_limit)
                if start_date < earliest_allowed:
                    start_date = earliest_allowed

            # Get performance data
            performance_data = PortfolioHistoryService.get_portfolio_performance(
                portfolio, start_date, end_date
            )

            if not performance_data['success']:
                return Response(
                    {'error': performance_data.get('error', 'Failed to calculate performance')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Return only summary data (using correct key)
            return Response({
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'summary': performance_data['performance_summary'],  # FIXED: use correct key
                'retention_applied': retention_limit is not None
            })

        except Exception as e:
            logger.error(f"Error in portfolio performance summary endpoint: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def recalculate_performance(self, request, pk=None):
        """
        Manually recalculate portfolio performance
        """
        portfolio = get_object_or_404(Portfolio, pk=pk)

        # Get parameters
        days = int(request.data.get('days', 30))
        force_update = request.data.get('force_update', False)

        # Validate days parameter
        if days < 1 or days > 365:
            return Response(
                {'error': 'Days must be between 1 and 365'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from portfolio.services.portfolio_history_service import PortfolioHistoryService

            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Trigger recalculation
            result = PortfolioHistoryService.backfill_portfolio_history(
                portfolio, start_date, end_date, force_update=force_update
            )

            if result['success']:
                return Response({
                    'success': True,
                    'message': f'Successfully recalculated {result["successful_snapshots"]} snapshots',
                    'details': result
                })
            else:
                return Response(
                    {'error': f'Recalculation failed: {result.get("error")}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Error recalculating portfolio performance: {str(e)}")
            return Response(
                {'error': 'Failed to recalculate portfolio performance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_period_start_date(self, period: str, end_date: date) -> date:
        """Calculate start date based on period"""
        if period == '1M':
            return end_date - timedelta(days=30)
        elif period == '3M':
            return end_date - timedelta(days=90)
        elif period == '6M':
            return end_date - timedelta(days=180)
        elif period == '1Y':
            return end_date - timedelta(days=365)
        elif period == 'YTD':
            return date(end_date.year, 1, 1)
        elif period == 'ALL':
            # Find earliest transaction date
            earliest_transaction = Transaction.objects.filter(
                portfolio__user=self.request.user
            ).order_by('transaction_date').first()

            if earliest_transaction:
                return earliest_transaction.transaction_date.date()
            else:
                return end_date - timedelta(days=365)  # Default to 1 year
        else:
            # Default to 1 year
            return end_date - timedelta(days=365)

    def _get_user_retention_limit(self, user) -> Optional[int]:
        """
        Get data retention limit for user based on their subscription
        Returns None for unlimited access, or number of days for limited access
        """
        # Check if user has premium subscription
        # This is a placeholder - implement based on your user model/subscription system

        # For now, assume all users are free tier with 1 year retention
        # TODO: Implement proper subscription checking
        if hasattr(user, 'subscription') and getattr(user.subscription, 'is_premium', False):
            return None  # Unlimited access for premium users
        else:
            return None  # 1 year retention for free users

    def _format_chart_data(self, chart_data: List[Dict]) -> Dict:
        """Format performance data for frontend chart consumption"""
        # chart_data is already a list of dictionaries with the correct structure
        # Convert to format expected by ApexCharts
        formatted_data = []
        for point in chart_data:
            formatted_data.append({
                'x': point['date'],  # ApexCharts expects 'x' for time series
                'y': point['total_value']  # Use total_value as the main chart value
            })

        return {
            'series': [{
                'name': 'Portfolio Value',
                'data': formatted_data
            }],
            'categories': [point['date'] for point in chart_data],
            'raw_data': chart_data  # Include raw data for additional chart types
        }


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
        """Import security data from external source - ADMIN ONLY"""

        # Check if user is admin/staff
        if not request.user.is_staff:
            return Response(
                {
                    'error': 'Security import is restricted to administrators only. Please contact your administrator to add new securities.'},
                status=status.HTTP_403_FORBIDDEN
            )

        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = SecurityImportService()
            result = service.search_and_import_security(symbol)

            if result.get('error'):
                return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'security': SecuritySerializer(result['security']).data,
                'created': result.get('created', False),
                'exists': result.get('exists', False)
            })
        except Exception as e:
            logger.error(f"Error importing security {symbol}: {str(e)}")
            return Response(
                {'error': f'Failed to import {symbol}. Please check the symbol and try again.'},
                status=status.HTTP_400_BAD_REQUEST
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
            # Use base_amount if available (already converted to portfolio currency)
            if transaction.base_amount:
                total_cost = transaction.base_amount
            else:
                # Fallback to calculating it
                total_cost = transaction.total_value
                if transaction.exchange_rate:
                    total_cost = total_cost * transaction.exchange_rate

            # Check cash balance (use the recalculated balance)
            cash_account.recalculate_balances()

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

        elif transaction.transaction_type == 'DIVIDEND':
            # Create dividend cash transaction
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

        # After creating all cash transactions, recalculate balances
        cash_account.recalculate_balances()

    def perform_destroy(self, instance):
        """Override to handle cash transaction cleanup when deleting a transaction"""

        # Store the transaction details for logging
        transaction_type = instance.transaction_type
        security_symbol = instance.security.symbol
        transaction_created_at = instance.created_at

        # Store cash account for later recalculation
        cash_account = instance.portfolio.cash_account

        # Check if there's a related cash transaction
        if hasattr(instance, 'cash_transaction'):
            cash_transaction = instance.cash_transaction

            # If this was a BUY transaction, we need to check for and delete any auto-deposits FIRST
            if transaction_type == 'BUY':
                # Look for auto-deposits created around the same time
                from datetime import timedelta

                # Define a time window (1 minute before and after)
                time_window_start = transaction_created_at - timedelta(minutes=1)
                time_window_end = transaction_created_at + timedelta(minutes=1)

                auto_deposits = CashTransaction.objects.filter(
                    cash_account=cash_account,
                    transaction_type='DEPOSIT',
                    is_auto_deposit=True,
                    created_at__gte=time_window_start,
                    created_at__lte=time_window_end,
                    description__icontains=security_symbol
                )

                # Delete auto-deposits
                for auto_deposit in auto_deposits:
                    logger.info(f"Deleting auto-deposit of {auto_deposit.amount} for {security_symbol}")
                    auto_deposit.delete()

            # Delete the related cash transaction manually since it's SET_NULL, not CASCADE
            cash_transaction.delete()

            logger.info(f"Deleted {transaction_type} cash transaction for {security_symbol}")

        # Delete the transaction itself
        super().perform_destroy(instance)

        # Recalculate all balances after deletion
        cash_account.recalculate_balances()


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
        """
        Create cash transaction and recalculate balances
        """
        # Save with the current user
        cash_transaction = serializer.save(user=self.request.user)

        # Recalculate all balances
        cash_transaction.cash_account.recalculate_balances()

    def destroy(self, request, *args, **kwargs):
        """
        Override destroy to recalculate balances after deletion
        """
        instance = self.get_object()
        cash_account = instance.cash_account

        # Check if this cash transaction is related to a security transaction
        if instance.related_transaction:
            return Response(
                {'error': 'Cannot delete cash transactions that are linked to security transactions. '
                          'Please delete the security transaction instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delete the transaction
        response = super().destroy(request, *args, **kwargs)

        # Recalculate balances after deletion
        cash_account.recalculate_balances()

        return Response({
            'message': 'Transaction deleted successfully',
            'new_balance': float(cash_account.balance)
        }, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        """
        Update cash transaction and recalculate balances
        """
        cash_transaction = serializer.save()

        # Recalculate all balances
        cash_transaction.cash_account.recalculate_balances()


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

    consolidated_assets = []
    portfolio_currency = portfolio.base_currency

    for security_id, data in holdings.items():
        # Build transactions list
        transactions = []

        # Calculate proper average costs in both currencies
        portfolio_base_currency = portfolio.base_currency
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
            elif transaction.transaction_type == 'SPLIT':
                # For SPLIT transactions in cost calculations:
                # Splits don't change the total cost, but they do affect the per-share cost basis
                # The total_cost_security_currency should remain the same
                # The average cost will be recalculated later by dividing by the new quantity
                pass  # No adjustment needed to total cost

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
                # For dividends, use the NET amount (after fees)
                dividend_amount = transaction.total_value_transaction_currency  # This now returns NET dividend

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
                    'value': float(dividend_base_currency),  # Converted NET dividend amount
                    'value_original': float(dividend_amount),  # Original NET dividend amount
                    'total_amount': float(dividend_amount),  # NET amount for display
                    'currency': transaction.currency,
                    'exchange_rate': float(transaction.exchange_rate or 1),
                    'stock_id': transaction.security.id,
                    'dividend_per_share': float(
                        transaction.dividend_per_share) if transaction.dividend_per_share else None,
                    'base_amount': float(dividend_base_currency),
                    # For dividends, the gain/loss is the NET dividend amount
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