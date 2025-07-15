# backend/portfolio/services/portfolio_history_service.py
"""
Portfolio History Service - Phase 3 Implementation

This service handles automated portfolio value calculations, backfill operations,
and performance metrics for the Portfolio Historical Graphs feature.

Key Features:
- Automated daily portfolio value snapshots
- Intelligent backfill system for historical data
- Performance metrics calculation
- Bulk processing optimization
- Transaction-triggered recalculation
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

logger = logging.getLogger(__name__)


class PortfolioHistoryService:
    """
    Service for managing portfolio value history and performance calculations
    """

    @staticmethod
    def calculate_portfolio_value_on_date(portfolio: Portfolio, target_date: date) -> Dict:
        """
        Calculate portfolio value for a specific date

        Args:
            portfolio: Portfolio instance
            target_date: Date to calculate value for

        Returns:
            Dict containing portfolio value data
        """
        try:
            # Get all transactions up to and including the target date
            transactions = Transaction.objects.filter(
                portfolio=portfolio,
                transaction_date__date__lte=target_date
            ).order_by('transaction_date')

            # Calculate holdings as of target date
            holdings = {}
            cash_balance = Decimal('0')

            # Get initial cash balance if cash account exists
            try:
                cash_account = PortfolioCashAccount.objects.get(portfolio=portfolio)
                cash_balance = cash_account.balance
            except PortfolioCashAccount.DoesNotExist:
                # Portfolio doesn't have cash account, start with zero
                cash_balance = Decimal('0')

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
                        holdings[security.id]['total_cost'] += (
                                transaction.quantity * transaction.price
                        )
                        cash_balance -= (transaction.quantity * transaction.price)
                    else:  # SELL
                        # Calculate average cost for sold shares
                        if holdings[security.id]['quantity'] > 0:
                            avg_cost = (holdings[security.id]['total_cost'] /
                                        holdings[security.id]['quantity'])
                            cost_reduction = avg_cost * transaction.quantity
                            holdings[security.id]['total_cost'] -= cost_reduction

                        holdings[security.id]['quantity'] -= transaction.quantity
                        cash_balance += (transaction.quantity * transaction.price)

                        # Remove zero or negative positions
                        if holdings[security.id]['quantity'] <= 0:
                            del holdings[security.id]

                elif transaction.transaction_type == 'DIVIDEND':
                    cash_balance += transaction.quantity * transaction.price
                elif transaction.transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
                    cash_balance += transaction.quantity * transaction.price

            # Calculate current value of holdings
            total_value = cash_balance
            total_cost = Decimal('0')
            holdings_count = 0

            for holding_data in holdings.values():
                security = holding_data['security']
                quantity = holding_data['quantity']
                cost = holding_data['total_cost']

                if quantity > 0:
                    # Get current price for the security
                    current_price = PriceHistoryService.get_price_for_date(
                        security, target_date
                    )

                    if current_price and current_price > 0:
                        market_value = quantity * current_price
                        total_value += market_value
                        total_cost += cost
                        holdings_count += 1

            # Calculate derived metrics
            unrealized_gains = total_value - total_cost - cash_balance
            total_return_pct = (
                (unrealized_gains / total_cost * 100)
                if total_cost > 0 else Decimal('0')
            )

            return {
                'success': True,
                'date': target_date,
                'total_value': total_value,
                'total_cost': total_cost,
                'cash_balance': cash_balance,
                'holdings_count': holdings_count,
                'unrealized_gains': unrealized_gains,
                'total_return_pct': total_return_pct,
                'holdings': holdings
            }

        except Exception as e:
            logger.error(f"Error calculating portfolio value for {portfolio.name} on {target_date}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date
            }

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
                'error': str(e),
                'date': target_date
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
            force_update: Force update existing snapshots

        Returns:
            Dict with backfill results
        """
        if end_date is None:
            end_date = date.today()

        try:
            # Generate date range (business days only)
            current_date = start_date
            dates_to_process = []

            while current_date <= end_date:
                if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                    # Check if snapshot already exists (unless force update)
                    if force_update or not PortfolioValueHistory.objects.filter(
                            portfolio=portfolio, date=current_date
                    ).exists():
                        dates_to_process.append(current_date)
                current_date += timedelta(days=1)

            successful_snapshots = 0
            failed_snapshots = 0
            skipped_snapshots = 0

            for date_to_process in dates_to_process:
                result = PortfolioHistoryService.save_daily_snapshot(
                    portfolio, date_to_process, 'backfill'
                )

                if result['success']:
                    successful_snapshots += 1
                else:
                    failed_snapshots += 1

            # Count existing snapshots that were skipped
            if not force_update:
                existing_snapshots = PortfolioValueHistory.objects.filter(
                    portfolio=portfolio,
                    date__gte=start_date,
                    date__lte=end_date
                ).count()
                skipped_snapshots = existing_snapshots - successful_snapshots

            logger.info(f"Backfill complete for {portfolio.name} ({start_date} to {end_date}): "
                        f"{successful_snapshots}/{len(dates_to_process)} successful")

            return {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_dates': len(dates_to_process),
                'successful_snapshots': successful_snapshots,
                'failed_snapshots': failed_snapshots,
                'skipped_snapshots': skipped_snapshots
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
    def get_portfolio_performance(portfolio: Portfolio, start_date: date, end_date: date) -> Dict:
        """
        Get portfolio performance data for charts and analysis

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
                    daily_returns.append(float(daily_return))  # Convert to float

                previous_value = snapshot.total_value

            # Calculate summary statistics
            first_snapshot = snapshots.first()
            last_snapshot = snapshots.last()

            total_return = (
                (last_snapshot.total_value - first_snapshot.total_value) /
                first_snapshot.total_value * 100
                if first_snapshot.total_value > 0 else 0
            )

            # Calculate volatility (standard deviation of daily returns)
            volatility = 0
            if len(daily_returns) > 1:
                # Convert all values to float to avoid Decimal/float mixing
                avg_return = sum(daily_returns) / len(daily_returns)
                variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
                volatility = variance ** 0.5

            # Find best and worst performing days
            best_day = max(daily_returns) if daily_returns else 0
            worst_day = min(daily_returns) if daily_returns else 0

            performance_summary = {
                'total_return_pct': float(total_return),
                'start_value': float(first_snapshot.total_value),
                'end_value': float(last_snapshot.total_value),
                'volatility': float(volatility),
                'best_day': float(best_day),
                'worst_day': float(worst_day),
                'total_days': len(chart_data),
                'unrealized_gains': float(last_snapshot.unrealized_gains),
                'cash_balance': float(last_snapshot.cash_balance)
            }

            return {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'chart_data': chart_data,
                'performance_summary': performance_summary,
                'daily_returns': daily_returns
            }

        except Exception as e:
            logger.error(f"Error getting performance data for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date
            }

    @staticmethod
    def trigger_portfolio_recalculation(portfolio: Portfolio,
                                        transaction_date: date = None) -> Dict:
        """
        Trigger portfolio recalculation when transactions are added/modified

        Args:
            portfolio: Portfolio instance
            transaction_date: Date of transaction (for targeted recalculation)

        Returns:
            Dict with recalculation results
        """
        try:
            if transaction_date:
                # Recalculate from transaction date to today
                return PortfolioHistoryService.backfill_portfolio_history(
                    portfolio, transaction_date, None, force_update=True
                )
            else:
                # Full recalculation
                oldest_transaction = Transaction.objects.filter(
                    portfolio=portfolio
                ).order_by('transaction_date').first()

                if oldest_transaction:
                    return PortfolioHistoryService.backfill_portfolio_history(
                        portfolio, oldest_transaction.transaction_date.date(), None, force_update=True
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
                        end_date = kwargs.get('end_date')
                        force_update = kwargs.get('force_update', False)
                        result = PortfolioHistoryService.backfill_portfolio_history(
                            portfolio, start_date, end_date, force_update
                        )
                    elif operation == 'gap_fill':
                        gaps_result = PortfolioHistoryService.get_portfolio_gaps(portfolio)
                        if gaps_result['success'] and gaps_result['total_missing'] > 0:
                            result = PortfolioHistoryService.backfill_portfolio_history(
                                portfolio, gaps_result['start_date'], gaps_result['end_date'], True
                            )
                        else:
                            result = {'success': True, 'message': 'No gaps found'}
                    else:
                        result = {'success': False, 'error': f'Unknown operation: {operation}'}

                    if result['success']:
                        successful_operations += 1
                    else:
                        failed_operations += 1

                    results.append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'success': result['success'],
                        'error': result.get('error'),
                        'details': result
                    })

                except Exception as e:
                    failed_operations += 1
                    results.append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'success': False,
                        'error': str(e)
                    })

            return {
                'success': True,
                'operation': operation,
                'total_portfolios': len(portfolios),
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'details': results
            }

        except Exception as e:
            logger.error(f"Error in bulk portfolio processing: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation
            }