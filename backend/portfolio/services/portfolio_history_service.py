# backend/portfolio/services/portfolio_history_service.py
"""
Portfolio History Service - Phase 3 Implementation with Currency Fix

FIXED: Added proper GBp to GBP currency conversion for historical portfolio value calculations
This is the COMPLETE version preserving ALL existing functionality.
"""

from decimal import Decimal
from datetime import date, timedelta, datetime
from typing import Dict, List, Optional, Tuple
import logging
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, F, Max, Min
from django.utils import timezone
from django.core.cache import cache
import statistics

from ..models import (
    Portfolio, PortfolioValueHistory, Security, Transaction,
    PriceHistory, PortfolioCashAccount
)
from .price_history_service import PriceHistoryService
from .currency_service import CurrencyService  # ADDED: Import for currency conversion

logger = logging.getLogger(__name__)


class PortfolioHistoryService:
    """
    Service for managing portfolio value history and performance calculations
    """

    @staticmethod
    def calculate_portfolio_value_on_date(portfolio: Portfolio, target_date: date) -> Dict:
        """
        Calculate portfolio value for a specific date - FIXED VERSION WITH CURRENCY CONVERSION

        Args:
            portfolio: Portfolio instance
            target_date: Date to calculate value for

        Returns:
            Dict containing portfolio value data
        """
        try:
            from datetime import datetime
            from django.utils import timezone

            # Convert date to datetime with timezone for proper comparison
            if isinstance(target_date, date):
                target_datetime = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
            else:
                target_datetime = target_date

            # Get all transactions up to and including the target date
            transactions = Transaction.objects.filter(
                portfolio=portfolio,
                transaction_date__lte=target_datetime
            ).order_by('transaction_date')

            # Calculate holdings as of target date
            holdings = {}
            cash_balance = Decimal('0')

            # Get cash balance from cash account (up to target date)
            try:
                cash_account = PortfolioCashAccount.objects.get(portfolio=portfolio)
                # Get cash transactions up to target date
                cash_transactions = cash_account.transactions.filter(
                    transaction_date__lte=target_datetime
                ).order_by('transaction_date')

                for cash_tx in cash_transactions:
                    cash_balance += cash_tx.amount

            except PortfolioCashAccount.DoesNotExist:
                # Portfolio doesn't have cash account, start with zero
                cash_balance = Decimal('0')

            # Process security transactions
            for transaction in transactions:
                if transaction.transaction_type in ['BUY', 'SELL']:
                    security = transaction.security
                    if security.id not in holdings:
                        holdings[security.id] = {
                            'security': security,
                            'quantity': Decimal('0'),
                            'total_cost': Decimal('0')
                        }

                    if transaction.transaction_type == 'BUY':
                        holdings[security.id]['quantity'] += transaction.quantity

                        # FIXED: Use base_currency instead of currency
                        transaction_currency = security.currency or 'USD'
                        portfolio_currency = portfolio.base_currency or 'GBP'

                        # Calculate raw cost in transaction currency
                        raw_cost = transaction.quantity * transaction.price

                        # Convert to portfolio currency using TRANSACTION DATE for exchange rate
                        transaction_date = transaction.transaction_date.date() if hasattr(transaction.transaction_date,
                                                                                          'date') else transaction.transaction_date

                        # Convert to portfolio currency if needed
                        if transaction_currency != portfolio_currency:
                            try:
                                converted_cost = CurrencyService.convert_amount_with_normalization(
                                    raw_cost,
                                    transaction_currency,
                                    portfolio_currency,
                                    transaction_date  # Use transaction date, not target_date
                                )
                                holdings[security.id]['total_cost'] += converted_cost
                                logger.debug(f"Transaction cost conversion: {raw_cost} {transaction_currency} -> "
                                             f"{converted_cost} {portfolio_currency} on {transaction_date}")
                            except Exception as e:
                                logger.warning(f"Transaction cost conversion failed: {e}. Using raw cost.")
                                holdings[security.id]['total_cost'] += raw_cost
                        else:
                            # Same currency, but still apply normalization (handles GBp -> GBP)
                            try:
                                normalized_cost = CurrencyService.convert_amount_with_normalization(
                                    raw_cost,
                                    transaction_currency,
                                    portfolio_currency,
                                    transaction_date  # Use transaction date, not target_date
                                )
                                holdings[security.id]['total_cost'] += normalized_cost
                                logger.debug(f"Transaction cost normalization: {raw_cost} {transaction_currency} -> "
                                             f"{normalized_cost} {portfolio_currency} on {transaction_date}")
                            except Exception as e:
                                logger.warning(f"Transaction cost normalization failed: {e}. Using raw cost.")
                                holdings[security.id]['total_cost'] += raw_cost

                    elif transaction.transaction_type == 'SELL':
                        holdings[security.id]['quantity'] -= transaction.quantity
                        # Proportionally reduce total cost
                        if holdings[security.id]['quantity'] <= 0:
                            holdings[security.id]['total_cost'] = Decimal('0')
                        else:
                            cost_per_share = holdings[security.id]['total_cost'] / (
                                    holdings[security.id]['quantity'] + transaction.quantity)
                            holdings[security.id]['total_cost'] -= (cost_per_share * transaction.quantity)

            # Calculate current value of holdings WITH PROPER CURRENCY CONVERSION
            holdings_value = Decimal('0')
            holdings_count = 0
            holdings_list = []
            total_cost = Decimal('0')

            for security_id, holding in holdings.items():
                if holding['quantity'] > 0:
                    holdings_count += 1
                    total_cost += holding['total_cost']

                    # Get current price for this security
                    current_price = PortfolioHistoryService.get_security_price_on_date(
                        holding['security'], target_date
                    )

                    if current_price:
                        # FIXED: Apply currency conversion for security prices
                        security = holding['security']
                        security_currency = security.currency or 'USD'
                        portfolio_currency = portfolio.base_currency or 'GBP'

                        # Calculate raw current value in security's currency
                        raw_current_value = holding['quantity'] * current_price

                        # Convert to portfolio currency using CurrencyService
                        if security_currency != portfolio_currency:
                            try:
                                # Use the same currency conversion logic as other parts of the system
                                converted_current_value = CurrencyService.convert_amount_with_normalization(
                                    raw_current_value,
                                    security_currency,
                                    portfolio_currency,
                                    target_date
                                )
                                current_value = converted_current_value
                                logger.debug(f"Currency conversion for {security.symbol}: "
                                             f"{raw_current_value} {security_currency} -> "
                                             f"{converted_current_value} {portfolio_currency}")
                            except Exception as e:
                                logger.warning(f"Currency conversion failed for {security.symbol}: {e}. "
                                               f"Using raw value.")
                                current_value = raw_current_value
                        else:
                            # Same currency, but still apply normalization (handles GBp -> GBP)
                            try:
                                normalized_value = CurrencyService.convert_amount_with_normalization(
                                    raw_current_value,
                                    security_currency,
                                    portfolio_currency,
                                    target_date
                                )
                                current_value = normalized_value
                                logger.debug(f"Currency normalization for {security.symbol}: "
                                             f"{raw_current_value} {security_currency} -> "
                                             f"{normalized_value} {portfolio_currency}")
                            except Exception as e:
                                logger.warning(f"Currency normalization failed for {security.symbol}: {e}. "
                                               f"Using raw value.")
                                current_value = raw_current_value

                        holdings_value += current_value

                        holdings_list.append({
                            'security': holding['security'].symbol,
                            'quantity': holding['quantity'],
                            'current_price': current_price,
                            'current_value': current_value,  # This is now converted to portfolio currency
                            'total_cost': holding['total_cost']
                        })

            # Calculate total portfolio value
            total_value = cash_balance + holdings_value

            # Calculate performance metrics
            unrealized_gains = holdings_value - total_cost
            total_return_pct = (
                (unrealized_gains / total_cost * 100)
                if total_cost > 0 else Decimal('0')
            )

            return {
                'success': True,
                'date': target_date,
                'total_value': total_value,
                'cash_balance': cash_balance,
                'holdings_value': holdings_value,
                'total_cost': total_cost,
                'holdings_count': holdings_count,
                'unrealized_gains': unrealized_gains,
                'total_return_pct': total_return_pct,
                'holdings': holdings_list
            }

        except Exception as e:
            logger.error(f"Error calculating portfolio value for {portfolio.name} on {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date
            }

    @staticmethod
    def get_security_price_on_date(security, target_date: date) -> Decimal:
        """
        Get security price on a specific date

        Args:
            security: Security instance
            target_date: Date to get price for

        Returns:
            Decimal price or None if not found
        """
        try:
            from django.utils import timezone
            from datetime import datetime

            # Convert date to datetime for comparison
            if isinstance(target_date, date):
                target_datetime = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
            else:
                target_datetime = target_date

            # Try to get price on or before target date
            price_record = PriceHistory.objects.filter(
                security=security,
                date__lte=target_datetime
            ).order_by('-date').first()

            if price_record:
                return Decimal(str(price_record.close_price))

            # If no price history, try current price
            if security.current_price:
                return Decimal(str(security.current_price))

            return None

        except Exception as e:
            logger.error(f"Error getting price for {security.symbol} on {target_date}: {str(e)}")
            return None

    @staticmethod
    def save_daily_snapshot(portfolio: Portfolio, target_date: date = None,
                            calculation_source: str = 'daily') -> Dict:
        """
        Save daily portfolio value snapshot

        Args:
            portfolio: Portfolio instance
            target_date: Date for snapshot (defaults to today)
            calculation_source: Source of calculation

        Returns:
            Dict with operation result
        """
        if target_date is None:
            target_date = date.today()

        try:
            # Calculate portfolio value
            calculation_result = PortfolioHistoryService.calculate_portfolio_value_on_date(
                portfolio, target_date
            )

            if not calculation_result['success']:
                return calculation_result

            # Create or update snapshot
            snapshot, created = PortfolioValueHistory.objects.update_or_create(
                portfolio=portfolio,
                date=target_date,
                defaults={
                    'total_value': calculation_result['total_value'],
                    'total_cost': calculation_result['total_cost'],
                    'cash_balance': calculation_result['cash_balance'],
                    'holdings_count': calculation_result['holdings_count'],
                    'unrealized_gains': calculation_result['unrealized_gains'],
                    'total_return_pct': calculation_result['total_return_pct'],
                    'calculation_source': calculation_source
                }
            )

            logger.info(f"{'Created' if created else 'Updated'} portfolio snapshot for "
                        f"{portfolio.name} on {target_date}: ${calculation_result['total_value']:,.2f}")

            return {
                'success': True,
                'created': created,
                'snapshot': snapshot,
                'calculation_result': calculation_result
            }

        except Exception as e:
            logger.error(f"Error saving snapshot for {portfolio.name} on {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def get_portfolio_performance(portfolio: Portfolio, start_date: date, end_date: date) -> Dict:
        """
        Get portfolio performance data for charts and analysis - FIXED VERSION

        Args:
            portfolio: Portfolio instance
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dict with performance data
        """
        try:
            # Get snapshots for the date range
            snapshots = PortfolioValueHistory.objects.filter(
                portfolio=portfolio,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')

            if not snapshots.exists():
                return {
                    'success': False,
                    'error': 'No historical data found for the specified date range'
                }

            # Get first and last snapshots for period calculation
            first_snapshot = snapshots.first()
            last_snapshot = snapshots.last()

            # Calculate period-specific values
            start_value = first_snapshot.total_value
            end_value = last_snapshot.total_value
            period_return = end_value - start_value
            period_return_pct = (period_return / start_value * 100) if start_value > 0 else 0

            # Prepare chart data and calculate returns
            chart_data = []
            daily_returns = []
            previous_value = None

            for snapshot in snapshots:
                chart_data.append({
                    'date': snapshot.date.isoformat(),
                    'total_value': float(snapshot.total_value),
                    'total_cost': float(snapshot.total_cost),
                    'cash_balance': float(snapshot.cash_balance),
                    'unrealized_gains': float(snapshot.unrealized_gains),
                    'total_return_pct': float(snapshot.total_return_pct),
                    'holdings_count': snapshot.holdings_count
                })

                # Calculate daily return
                if previous_value is not None:
                    daily_return = (
                        (snapshot.total_value - previous_value) / previous_value * 100
                        if previous_value > 0 else 0
                    )
                    daily_returns.append(float(daily_return))

                previous_value = snapshot.total_value

            # Calculate volatility (standard deviation of daily returns)
            volatility = 0
            if len(daily_returns) > 1:
                import statistics
                volatility = statistics.stdev(daily_returns)

            # Calculate best and worst days
            best_day = max(daily_returns) if daily_returns else 0
            worst_day = min(daily_returns) if daily_returns else 0

            # Count positive and negative days
            positive_days = sum(1 for r in daily_returns if r > 0)
            negative_days = sum(1 for r in daily_returns if r < 0)

            # Build performance summary with CORRECT period calculations
            performance_summary = {
                'total_return_pct': float(period_return_pct),  # FIXED: Use period return
                'start_value': float(start_value),  # FIXED: Use start_value
                'end_value': float(end_value),  # FIXED: Use end_value
                'volatility': float(volatility),
                'best_day': float(best_day),
                'worst_day': float(worst_day),
                'total_days': len(daily_returns),
                'positive_days': positive_days,
                'negative_days': negative_days,
                'unrealized_gains': float(period_return),  # FIXED: Use period return
                'cash_balance': float(last_snapshot.cash_balance)
            }

            return {
                'success': True,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'chart_data': chart_data,
                'performance_summary': performance_summary
            }

        except Exception as e:
            logger.error(f"Error getting portfolio performance for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def calculate_daily_snapshots(target_date: date = None) -> Dict:
        """
        Calculate daily snapshots for all active portfolios

        Args:
            target_date: Date for snapshots (defaults to today)

        Returns:
            Dict with bulk operation results
        """
        if target_date is None:
            target_date = date.today()

        try:
            portfolios = Portfolio.objects.all()  # Get all portfolios since is_active doesn't exist
            successful_snapshots = 0
            failed_snapshots = 0
            results = []

            for portfolio in portfolios:
                result = PortfolioHistoryService.save_daily_snapshot(
                    portfolio, target_date, 'daily_batch'
                )

                if result['success']:
                    successful_snapshots += 1
                else:
                    failed_snapshots += 1

                results.append({
                    'portfolio_id': portfolio.id,
                    'portfolio_name': portfolio.name,
                    'success': result['success'],
                    'created': result.get('created', False),
                    'error': result.get('error')
                })

            logger.info(f"Daily snapshots complete for {target_date}: "
                        f"{successful_snapshots}/{len(portfolios)} successful")

            return {
                'success': True,
                'target_date': target_date,
                'total_portfolios': len(portfolios),
                'successful_snapshots': successful_snapshots,
                'failed_snapshots': failed_snapshots,
                'results': results
            }

        except Exception as e:
            logger.error(f"Error calculating daily snapshots for {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'target_date': target_date
            }

    @staticmethod
    def backfill_portfolio_history(portfolio: Portfolio, start_date: date,
                                   end_date: date = None, force_update: bool = False) -> Dict:
        """
        Backfill portfolio history for date range

        Args:
            portfolio: Portfolio instance
            start_date: Start date for backfill
            end_date: End date for backfill (defaults to today)
            force_update: Whether to overwrite existing snapshots

        Returns:
            Dict with backfill results
        """
        if end_date is None:
            end_date = date.today()

        try:
            successful_snapshots = 0
            failed_snapshots = 0
            skipped_snapshots = 0
            total_dates = 0
            errors = []

            current_date = start_date
            while current_date <= end_date:
                total_dates += 1

                # Skip weekends (optional - depends on your requirements)
                if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    current_date += timedelta(days=1)
                    continue

                try:
                    # Check if snapshot already exists and force_update is False
                    if not force_update and PortfolioValueHistory.objects.filter(
                            portfolio=portfolio, date=current_date
                    ).exists():
                        skipped_snapshots += 1
                        current_date += timedelta(days=1)
                        continue

                    result = PortfolioHistoryService.save_daily_snapshot(
                        portfolio, current_date, 'backfill'
                    )

                    if result['success']:
                        successful_snapshots += 1
                    else:
                        failed_snapshots += 1
                        errors.append(f"{current_date}: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    failed_snapshots += 1
                    errors.append(f"{current_date}: {str(e)}")

                current_date += timedelta(days=1)

            logger.info(f"Portfolio backfill completed for {portfolio.name}: "
                        f"{successful_snapshots} created, {skipped_snapshots} skipped, {failed_snapshots} failed")

            return {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_dates': total_dates,
                'successful_snapshots': successful_snapshots,
                'skipped_snapshots': skipped_snapshots,
                'failed_snapshots': failed_snapshots,
                'errors': errors[:10]  # Limit error list to first 10
            }

        except Exception as e:
            logger.error(f"Error backfilling portfolio history for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date
            }

    @staticmethod
    def trigger_portfolio_recalculation(portfolio: Portfolio, transaction_date: date = None) -> Dict:
        """
        Trigger portfolio recalculation when transactions are added/modified
        """
        try:
            # Find the earliest transaction date for comprehensive backfill
            earliest_transaction_query = Transaction.objects.filter(portfolio=portfolio).order_by('transaction_date')
            earliest_cash_query = None

            # Also check cash transactions
            if hasattr(portfolio, 'cash_account') and portfolio.cash_account:
                earliest_cash_query = portfolio.cash_account.transactions.order_by('transaction_date')

            # Find the absolute earliest date
            earliest_date = None

            if earliest_transaction_query.exists():
                earliest_date = earliest_transaction_query.first().transaction_date.date()

            if earliest_cash_query and earliest_cash_query.exists():
                earliest_cash_date = earliest_cash_query.first().transaction_date.date()
                if earliest_date is None or earliest_cash_date < earliest_date:
                    earliest_date = earliest_cash_date

            if earliest_date:
                logger.info(f"Starting backfill for {portfolio.name} from earliest transaction date: {earliest_date}")
                return PortfolioHistoryService.backfill_portfolio_history(
                    portfolio, earliest_date, None, force_update=True
                )
            else:
                return {
                    'success': False,
                    'error': 'No transactions found for portfolio'
                }

        except Exception as e:
            logger.error(f"Error triggering recalculation for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name
            }

    @staticmethod
    def get_portfolio_gaps(portfolio: Portfolio, start_date: date = None,
                           end_date: date = None) -> Dict:
        """
        Find gaps in portfolio value history

        Args:
            portfolio: Portfolio instance
            start_date: Start date for gap detection
            end_date: End date for gap detection

        Returns:
            Dict with gap information
        """
        try:
            if start_date is None:
                # Start from first transaction or 30 days ago
                oldest_transaction = Transaction.objects.filter(
                    portfolio=portfolio
                ).order_by('transaction_date').first()

                if oldest_transaction:
                    start_date = oldest_transaction.transaction_date.date()
                else:
                    start_date = date.today() - timedelta(days=30)

            if end_date is None:
                end_date = date.today()

            # Generate expected business days
            expected_dates = []
            current_date = start_date

            while current_date <= end_date:
                if current_date.weekday() < 5:  # Business days only
                    expected_dates.append(current_date)
                current_date += timedelta(days=1)

            # Get existing snapshots
            existing_snapshots = PortfolioValueHistory.objects.filter(
                portfolio=portfolio,
                date__gte=start_date,
                date__lte=end_date
            ).values_list('date', flat=True)

            existing_dates = set(existing_snapshots)
            expected_dates_set = set(expected_dates)
            missing_dates = sorted(expected_dates_set - existing_dates)

            coverage_percentage = (
                (len(existing_dates) / len(expected_dates) * 100)
                if expected_dates else 100
            )

            return {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_expected': len(expected_dates),
                'total_existing': len(existing_dates),
                'total_missing': len(missing_dates),
                'missing_dates': missing_dates,
                'coverage_percentage': coverage_percentage
            }

        except Exception as e:
            logger.error(f"Error detecting gaps for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name
            }

    @staticmethod
    def bulk_portfolio_processing(portfolios: List[Portfolio], operation: str, **kwargs) -> Dict:
        """
        Process multiple portfolios in bulk

        Args:
            portfolios: List of Portfolio instances
            operation: Operation to perform ('daily_snapshot', 'backfill', 'gap_fill')
            **kwargs: Additional arguments for the operation

        Returns:
            Dict with bulk operation results
        """
        try:
            successful_operations = 0
            failed_operations = 0
            results = []

            for portfolio in portfolios:
                try:
                    if operation == 'daily_snapshot':
                        target_date = kwargs.get('target_date', date.today())
                        result = PortfolioHistoryService.save_daily_snapshot(
                            portfolio, target_date, 'bulk_daily'
                        )
                    elif operation == 'backfill':
                        start_date = kwargs.get('start_date')
                        end_date = kwargs.get('end_date', date.today())
                        force_update = kwargs.get('force_update', False)
                        result = PortfolioHistoryService.backfill_portfolio_history(
                            portfolio, start_date, end_date, force_update
                        )
                    elif operation == 'gap_fill':
                        gaps_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)
                        if gaps_result['success'] and gaps_result['missing_dates']:
                            # Fill gaps
                            result = {'success': True, 'filled_gaps': 0}
                            for gap_date in gaps_result['missing_dates']:
                                gap_result = PortfolioHistoryService.save_daily_snapshot(
                                    portfolio, gap_date, 'gap_fill'
                                )
                                if gap_result['success']:
                                    result['filled_gaps'] += 1
                        else:
                            result = {'success': True, 'filled_gaps': 0}
                    else:
                        result = {'success': False, 'error': f'Unknown operation: {operation}'}

                    if result['success']:
                        successful_operations += 1
                    else:
                        failed_operations += 1

                    results.append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'operation': operation,
                        'success': result['success'],
                        'result': result
                    })

                except Exception as e:
                    failed_operations += 1
                    results.append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'operation': operation,
                        'success': False,
                        'error': str(e)
                    })

            logger.info(f"Bulk {operation} completed: {successful_operations} successful, "
                        f"{failed_operations} failed")

            return {
                'success': True,
                'operation': operation,
                'total_portfolios': len(portfolios),
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'results': results
            }

        except Exception as e:
            logger.error(f"Error in bulk {operation} operation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation
            }

    @staticmethod
    def calculate_daily_snapshots_for_all_portfolios(target_date: date = None) -> Dict:
        """
        Calculate daily snapshots for all active portfolios
        (Alias for calculate_daily_snapshots for backward compatibility)

        Args:
            target_date: Date to calculate for (defaults to today)

        Returns:
            Dict with results for all portfolios
        """
        return PortfolioHistoryService.calculate_daily_snapshots(target_date)