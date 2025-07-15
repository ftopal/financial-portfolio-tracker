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
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, F
from django.utils import timezone
from django.core.cache import cache

from ..models import (
    Portfolio, PortfolioValueHistory, Security, Transaction,
    PriceHistory
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
                        # Calculate average cost per share
                        if holdings[security.id]['quantity'] > 0:
                            avg_cost = (
                                    holdings[security.id]['total_cost'] /
                                    holdings[security.id]['quantity']
                            )
                            sold_cost = transaction.quantity * avg_cost
                            holdings[security.id]['total_cost'] -= sold_cost

                        holdings[security.id]['quantity'] -= transaction.quantity
                        cash_balance += (transaction.quantity * transaction.price)

                        # Remove holdings with zero quantity
                        if holdings[security.id]['quantity'] <= 0:
                            del holdings[security.id]

                elif transaction.transaction_type == 'DIVIDEND':
                    # Handle dividends - add to cash
                    cash_balance += (transaction.quantity * transaction.price)
                # Note: Your model doesn't seem to have DEPOSIT/WITHDRAWAL transaction types
                # so I'm removing those cases

            # Get cash account balance instead of calculating from transactions
            try:
                if hasattr(portfolio, 'cash_account'):
                    cash_balance = portfolio.cash_account.balance
                else:
                    cash_balance = Decimal('0')
            except:
                cash_balance = Decimal('0')

            # Calculate current market value of holdings
            total_value = cash_balance
            total_cost = cash_balance
            holdings_count = len(holdings)

            for holding_data in holdings.values():
                if holding_data['quantity'] > 0:
                    # Get price for the target date
                    price = PriceHistoryService.get_price_for_date(
                        holding_data['security'], target_date
                    )

                    if price:
                        market_value = holding_data['quantity'] * price
                        total_value += market_value
                        total_cost += holding_data['total_cost']

            # Calculate performance metrics
            unrealized_gains = total_value - total_cost
            total_return_pct = (
                ((total_value - total_cost) / total_cost * 100)
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
            Dict with batch operation results
        """
        if target_date is None:
            target_date = date.today()

        try:
            # Get all portfolios (assuming active by default)
            portfolios = Portfolio.objects.all()

            results = {
                'success': True,
                'date': target_date,
                'total_portfolios': len(portfolios),
                'successful_snapshots': 0,
                'failed_snapshots': 0,
                'details': []
            }

            for portfolio in portfolios:
                snapshot_result = PortfolioHistoryService.save_daily_snapshot(
                    portfolio, target_date, 'daily'
                )

                if snapshot_result['success']:
                    results['successful_snapshots'] += 1
                else:
                    results['failed_snapshots'] += 1

                results['details'].append({
                    'portfolio_id': portfolio.id,
                    'portfolio_name': portfolio.name,
                    'success': snapshot_result['success'],
                    'error': snapshot_result.get('error', 'Unknown error') if not snapshot_result['success'] else None
                })

            logger.info(f"Daily snapshots complete for {target_date}: "
                        f"{results['successful_snapshots']}/{results['total_portfolios']} successful")

            return results

        except Exception as e:
            logger.error(f"Error in daily snapshots calculation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date
            }

    @staticmethod
    def backfill_portfolio_history(portfolio: Portfolio, start_date: date,
                                   end_date: date = None, force_update: bool = False) -> Dict:
        """
        Backfill historical portfolio data

        Args:
            portfolio: Portfolio instance
            start_date: Start date for backfill
            end_date: End date for backfill (defaults to today)
            force_update: Whether to overwrite existing data

        Returns:
            Dict with backfill operation results
        """
        if end_date is None:
            end_date = date.today()

        try:
            # Validate date range
            if start_date > end_date:
                return {
                    'success': False,
                    'error': 'Start date must be before end date'
                }

            # Get existing snapshots if not forcing update
            existing_snapshots = set()
            if not force_update:
                existing_snapshots = set(
                    PortfolioValueHistory.objects.filter(
                        portfolio=portfolio,
                        date__gte=start_date,
                        date__lte=end_date
                    ).values_list('date', flat=True)
                )

            # Generate date range (business days only)
            current_date = start_date
            dates_to_process = []

            while current_date <= end_date:
                # Skip weekends for stock markets
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    if force_update or current_date not in existing_snapshots:
                        dates_to_process.append(current_date)
                current_date += timedelta(days=1)

            results = {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_dates': len(dates_to_process),
                'successful_snapshots': 0,
                'failed_snapshots': 0,
                'skipped_snapshots': len(existing_snapshots) if not force_update else 0,
                'details': []
            }

            # Process dates in batches for performance
            batch_size = 50
            for i in range(0, len(dates_to_process), batch_size):
                batch_dates = dates_to_process[i:i + batch_size]

                for target_date in batch_dates:
                    snapshot_result = PortfolioHistoryService.save_daily_snapshot(
                        portfolio, target_date, 'backfill'
                    )

                    if snapshot_result['success']:
                        results['successful_snapshots'] += 1
                    else:
                        results['failed_snapshots'] += 1

                    results['details'].append({
                        'date': target_date,
                        'success': snapshot_result['success'],
                        'error': snapshot_result.get('error')
                    })

                # Small delay between batches to avoid overwhelming the database
                if i + batch_size < len(dates_to_process):
                    import time
                    time.sleep(0.1)

            logger.info(f"Backfill complete for {portfolio.name} ({start_date} to {end_date}): "
                        f"{results['successful_snapshots']}/{results['total_dates']} successful")

            return results

        except Exception as e:
            logger.error(f"Error in backfill for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date
            }

    @staticmethod
    def get_portfolio_performance(portfolio: Portfolio, start_date: date,
                                  end_date: date = None) -> Dict:
        """
        Get performance data for charts

        Args:
            portfolio: Portfolio instance
            start_date: Start date for performance data
            end_date: End date for performance data (defaults to today)

        Returns:
            Dict with performance data
        """
        if end_date is None:
            end_date = date.today()

        try:
            # Get portfolio value history
            snapshots = PortfolioValueHistory.objects.filter(
                portfolio=portfolio,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')

            if not snapshots.exists():
                return {
                    'success': False,
                    'error': 'No historical data found for the specified period'
                }

            # Prepare chart data
            chart_data = []
            daily_returns = []

            previous_value = None
            for snapshot in snapshots:
                chart_data.append({
                    'date': snapshot.date,
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
                    daily_returns.append(daily_return)

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
                # Find earliest transaction date
                earliest_transaction = Transaction.objects.filter(
                    portfolio=portfolio
                ).order_by('transaction_date').first()
                start_date = earliest_transaction.transaction_date.date() if earliest_transaction else date.today()

            if end_date is None:
                end_date = date.today()

            # Get existing snapshots
            existing_dates = set(
                PortfolioValueHistory.objects.filter(
                    portfolio=portfolio,
                    date__gte=start_date,
                    date__lte=end_date
                ).values_list('date', flat=True)
            )

            # Generate expected business days
            expected_dates = []
            current_date = start_date

            while current_date <= end_date:
                if current_date.weekday() < 5:  # Business days only
                    expected_dates.append(current_date)
                current_date += timedelta(days=1)

            # Find missing dates
            missing_dates = [d for d in expected_dates if d not in existing_dates]

            return {
                'success': True,
                'portfolio': portfolio.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_expected': len(expected_dates),
                'total_existing': len(existing_dates),
                'total_missing': len(missing_dates),
                'missing_dates': missing_dates,
                'coverage_percentage': (len(existing_dates) / len(expected_dates) * 100) if expected_dates else 100
            }

        except Exception as e:
            logger.error(f"Error finding gaps for {portfolio.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'portfolio': portfolio.name
            }

    @staticmethod
    def bulk_portfolio_processing(portfolios: List[Portfolio],
                                  operation: str, **kwargs) -> Dict:
        """
        Process multiple portfolios in bulk

        Args:
            portfolios: List of Portfolio instances
            operation: Operation to perform ('daily_snapshot', 'backfill', 'performance')
            **kwargs: Additional arguments for the operation

        Returns:
            Dict with bulk operation results
        """
        try:
            results = {
                'success': True,
                'operation': operation,
                'total_portfolios': len(portfolios),
                'successful_operations': 0,
                'failed_operations': 0,
                'details': []
            }

            for portfolio in portfolios:
                try:
                    if operation == 'daily_snapshot':
                        result = PortfolioHistoryService.save_daily_snapshot(
                            portfolio, kwargs.get('target_date'), kwargs.get('calculation_source', 'bulk')
                        )
                    elif operation == 'backfill':
                        result = PortfolioHistoryService.backfill_portfolio_history(
                            portfolio, kwargs.get('start_date'), kwargs.get('end_date'),
                            kwargs.get('force_update', False)
                        )
                    elif operation == 'performance':
                        result = PortfolioHistoryService.get_portfolio_performance(
                            portfolio, kwargs.get('start_date'), kwargs.get('end_date')
                        )
                    else:
                        result = {'success': False, 'error': f'Unknown operation: {operation}'}

                    if result['success']:
                        results['successful_operations'] += 1
                    else:
                        results['failed_operations'] += 1

                    results['details'].append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'success': result['success'],
                        'error': result.get('error')
                    })

                except Exception as e:
                    results['failed_operations'] += 1
                    results['details'].append({
                        'portfolio_id': portfolio.id,
                        'portfolio_name': portfolio.name,
                        'success': False,
                        'error': str(e)
                    })

            logger.info(f"Bulk {operation} complete: "
                        f"{results['successful_operations']}/{results['total_portfolios']} successful")

            return results

        except Exception as e:
            logger.error(f"Error in bulk portfolio processing: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation
            }