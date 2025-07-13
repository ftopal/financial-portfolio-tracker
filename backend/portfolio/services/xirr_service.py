import pyxirr
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Max
from ..models import Transaction, Portfolio, Security
import logging

logger = logging.getLogger(__name__)

# Fallback imports for when pyxirr fails
try:
    import numpy as np
    import numpy_financial as npf
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy-financial not available as fallback for XIRR calculations")


class XIRRService:
    """Service for calculating Extended Internal Rate of Return (XIRR)"""

    MIN_DAYS_SPAN = 30  # Minimum days between first transaction and today

    @classmethod
    def get_portfolio_xirr(cls, portfolio, force_recalculate=False):
        """Get portfolio XIRR with caching"""
        from ..models import PortfolioXIRRCache

        # Check cache first (unless force recalculate)
        if not force_recalculate:
            cache_obj = PortfolioXIRRCache.objects.filter(portfolio=portfolio).first()
            if cache_obj and not cls._should_recalculate_portfolio(portfolio, cache_obj):
                logger.info(f"Using cached portfolio XIRR for {portfolio.name}")
                return cache_obj.xirr_value

        # Calculate fresh XIRR
        logger.info(f"Calculating fresh portfolio XIRR for {portfolio.name}")
        xirr_value = cls._calculate_portfolio_xirr(portfolio)

        # Cache the result
        cls._cache_portfolio_xirr(portfolio, xirr_value)

        return xirr_value

    @classmethod
    def get_asset_xirr(cls, portfolio, security, force_recalculate=False):
        """Get asset XIRR with caching"""
        from ..models import AssetXIRRCache

        # Check cache first (unless force recalculate)
        if not force_recalculate:
            cache_obj = AssetXIRRCache.objects.filter(
                portfolio=portfolio,
                security=security
            ).first()
            if cache_obj and not cls._should_recalculate_asset(portfolio, security, cache_obj):
                logger.info(f"Using cached asset XIRR for {security.symbol}")
                return cache_obj.xirr_value

        # Calculate fresh XIRR
        logger.info(f"Calculating fresh asset XIRR for {security.symbol}")
        xirr_value = cls._calculate_asset_xirr(portfolio, security)

        # Cache the result
        cls._cache_asset_xirr(portfolio, security, xirr_value)

        return xirr_value

    @classmethod
    def get_all_asset_xirrs(cls, portfolio, force_recalculate=False):
        """Get XIRR for all assets in portfolio"""
        holdings = portfolio.get_holdings()
        xirr_results = {}

        for security_id, holding_data in holdings.items():
            if holding_data['quantity'] > 0:
                security = holding_data['security']
                xirr = cls.get_asset_xirr(portfolio, security, force_recalculate)
                xirr_results[security_id] = xirr

        return xirr_results

    @classmethod
    def _calculate_xirr_with_fallback(cls, cash_flows, dates, identifier=""):
        """Calculate XIRR with multiple methods and fallbacks"""

        logger.info(f"{identifier} cash flows: {list(zip(dates, cash_flows))}")

        # Try pyxirr first (multiple methods)
        xirr_result = cls._try_pyxirr(cash_flows, dates, identifier)
        if xirr_result is not None:
            return xirr_result

        # Fallback to numpy-financial if available
        if NUMPY_AVAILABLE:
            logger.info(f"{identifier}: pyxirr failed, trying numpy-financial fallback")
            return cls._try_numpy_xirr(cash_flows, dates, identifier)

        logger.error(f"{identifier}: All XIRR calculation methods failed")
        return None

    @classmethod
    def _try_pyxirr(cls, cash_flows, dates, identifier=""):
        """Try pyxirr with multiple parameter formats"""

        logger.info(f"{identifier} trying pyxirr with {len(cash_flows)} cash flows")
        logger.info(f"{identifier} cash flows: {cash_flows}")
        logger.info(f"{identifier} dates: {dates}")

        # Validate input data
        if len(cash_flows) != len(dates):
            logger.error(f"{identifier} cash flows and dates length mismatch")
            return None

        if len(cash_flows) < 2:
            logger.error(f"{identifier} need at least 2 cash flows, got {len(cash_flows)}")
            return None

        # Check for all zeros
        if all(cf == 0 for cf in cash_flows):
            logger.error(f"{identifier} all cash flows are zero")
            return None

        # Check for sign changes (needed for IRR)
        has_negative = any(cf < 0 for cf in cash_flows)
        has_positive = any(cf > 0 for cf in cash_flows)
        if not (has_negative and has_positive):
            logger.error(
                f"{identifier} need both positive and negative cash flows. Has negative: {has_negative}, Has positive: {has_positive}")
            return None

        # Method 1: Named parameters (most reliable)
        try:
            logger.debug(f"{identifier} trying pyxirr method 1: named parameters")
            result = pyxirr.xirr(amounts=cash_flows, dates=dates)
            if result is not None:
                logger.info(f"{identifier} XIRR (pyxirr method 1): {result}")
                return Decimal(str(result))
            else:
                logger.debug(f"{identifier} pyxirr method 1 returned None")
        except Exception as e1:
            logger.debug(f"{identifier} pyxirr method 1 failed: {e1}")

        # Method 2: Positional parameters with explicit types
        try:
            logger.debug(f"{identifier} trying pyxirr method 2: positional parameters")
            clean_flows = [float(x) for x in cash_flows]
            clean_dates = list(dates)
            result = pyxirr.xirr(clean_flows, clean_dates)
            if result is not None:
                logger.info(f"{identifier} XIRR (pyxirr method 2): {result}")
                return Decimal(str(result))
            else:
                logger.debug(f"{identifier} pyxirr method 2 returned None")
        except Exception as e2:
            logger.debug(f"{identifier} pyxirr method 2 failed: {e2}")

        # Method 3: Dictionary format
        try:
            logger.debug(f"{identifier} trying pyxirr method 3: dictionary format")
            transactions = [{"amount": float(cf), "date": dt} for cf, dt in zip(cash_flows, dates)]
            result = pyxirr.xirr(transactions)
            if result is not None:
                logger.info(f"{identifier} XIRR (pyxirr method 3): {result}")
                return Decimal(str(result))
            else:
                logger.debug(f"{identifier} pyxirr method 3 returned None")
        except Exception as e3:
            logger.debug(f"{identifier} pyxirr method 3 failed: {e3}")

        logger.error(f"{identifier} all pyxirr methods failed or returned None")
        return None

    @classmethod
    def _try_numpy_xirr(cls, cash_flows, dates, identifier=""):
        """Fallback XIRR calculation using numpy-financial"""
        try:
            # Convert dates to years from start date for numpy calculation
            start_date = min(dates)
            periods = [(d - start_date).days / 365.25 for d in dates]

            # Use numpy IRR with periods
            flows_array = np.array(cash_flows, dtype=np.float64)
            periods_array = np.array(periods, dtype=np.float64)

            # Simple approach: use numpy's IRR for annual periods
            # This is an approximation but should be close to XIRR
            if len(set(periods)) == len(periods):  # All periods are unique
                # Calculate using interpolation method
                result = cls._numpy_xirr_approximation(flows_array, periods_array)
                if result is not None:
                    logger.info(f"{identifier} XIRR (numpy fallback): {result}")
                    return Decimal(str(result))

        except Exception as e:
            logger.error(f"{identifier} numpy XIRR fallback failed: {e}")

        return None

    @classmethod
    def _numpy_xirr_approximation(cls, cash_flows, periods):
        """Approximate XIRR using numpy IRR calculation"""
        try:
            # Simple Newton-Raphson method for XIRR approximation
            def npv(rate, cash_flows, periods):
                return sum(cf / (1 + rate) ** period for cf, period in zip(cash_flows, periods))

            def npv_derivative(rate, cash_flows, periods):
                return sum(-period * cf / (1 + rate) ** (period + 1) for cf, period in zip(cash_flows, periods))

            # Initial guess
            rate = 0.1
            tolerance = 1e-6
            max_iterations = 100

            for i in range(max_iterations):
                npv_value = npv(rate, cash_flows, periods)
                if abs(npv_value) < tolerance:
                    return rate

                npv_deriv = npv_derivative(rate, cash_flows, periods)
                if abs(npv_deriv) < 1e-12:
                    break

                rate = rate - npv_value / npv_deriv

                # Prevent extreme values
                if rate < -0.99 or rate > 10:
                    break

            # Final check
            if abs(npv(rate, cash_flows, periods)) < tolerance:
                return rate

        except Exception as e:
            logger.debug(f"numpy XIRR approximation failed: {e}")

        return None

    @classmethod
    def _get_transaction_cash_flow(cls, transaction):
        """Use existing total_value property - much simpler and consistent!"""
        try:
            if transaction.transaction_type == 'BUY':
                # Money out (negative) - use existing total_value property
                return -float(transaction.total_value)
            elif transaction.transaction_type in ['SELL', 'DIVIDEND']:
                # Money in (positive) - use existing total_value property
                return float(transaction.total_value)
            else:
                # Skip other transaction types (SPLIT, etc.)
                return None
        except Exception as e:
            logger.error(f"Failed to get cash flow for transaction {transaction.id}: {e}")
            return None

    @classmethod
    def _calculate_portfolio_current_value(cls, portfolio):
        """Use existing get_total_value method - much simpler and consistent!"""
        try:
            total_value = float(portfolio.get_total_value())
            logger.debug(f"Portfolio {portfolio.name} total value: £{total_value}")
            return round(total_value, 2)
        except Exception as e:
            logger.error(f"Failed to get portfolio total value: {e}")
            return 0.0

    @classmethod
    def _cache_portfolio_xirr(cls, portfolio, xirr_value):
        """Cache portfolio XIRR result - now based on CashTransaction"""
        from ..models import PortfolioXIRRCache, CashTransaction

        latest_cash_txn_id = CashTransaction.objects.filter(
            cash_account=portfolio.cash_account
        ).aggregate(max_id=Max('id'))['max_id']

        cache_obj, created = PortfolioXIRRCache.objects.update_or_create(
            portfolio=portfolio,
            defaults={
                'xirr_value': xirr_value,
                'last_transaction_id': latest_cash_txn_id,
            }
        )

        logger.info(f"{'Created' if created else 'Updated'} portfolio XIRR cache for {portfolio.name}")

    @classmethod
    def _calculate_asset_current_value(cls, portfolio, security):
        """Calculate current value using holdings calculation with currency conversion"""
        try:
            holdings = portfolio.get_holdings()

            if security.id in holdings:
                holding_info = holdings[security.id]

                # Use the CONVERTED value that's already calculated
                if 'current_value_base_currency' in holding_info:
                    converted_value = float(holding_info['current_value_base_currency'])
                    logger.debug(f"Asset {security.symbol}: Using converted value = £{converted_value}")
                    return round(converted_value, 2)
                else:
                    # Fallback to raw value
                    raw_value = float(holding_info['current_value'])
                    logger.debug(f"Asset {security.symbol}: Using raw value = {raw_value}")
                    return round(raw_value, 2)
            else:
                logger.debug(f"Asset {security.symbol}: Not found in holdings")
                return 0.0

        except Exception as e:
            logger.error(f"Failed to get current value for {security.symbol}: {e}")
            return 0.0

    @classmethod
    def _should_recalculate_portfolio(cls, portfolio, cache_obj):
        """Check if portfolio XIRR cache is stale - now based on CashTransaction"""
        from ..models import CashTransaction

        latest_cash_txn = CashTransaction.objects.filter(
            cash_account=portfolio.cash_account
        ).aggregate(max_id=Max('id'))['max_id']

        return latest_cash_txn != cache_obj.last_transaction_id

    @classmethod
    def _should_recalculate_asset(cls, portfolio, security, cache_obj):
        """Check if asset XIRR cache is stale"""
        latest_txn = Transaction.objects.filter(
            portfolio=portfolio,
            security=security
        ).aggregate(max_id=Max('id'))['max_id']

        return latest_txn != cache_obj.last_transaction_id

    @classmethod
    def _calculate_portfolio_xirr_weighted_fallback(cls, portfolio):
        """Calculate portfolio XIRR as weighted average of asset XIRRs (fallback method)"""
        try:
            holdings = portfolio.get_holdings()
            total_portfolio_value = 0.0
            weighted_xirr_sum = 0.0

            logger.info(f"Using weighted fallback XIRR calculation for {portfolio.name}")

            for security_id, holding_data in holdings.items():
                if holding_data['quantity'] > 0:
                    security = holding_data['security']
                    asset_value = cls._calculate_asset_current_value(portfolio, security)
                    asset_xirr = cls.get_asset_xirr(portfolio, security)

                    if asset_xirr is not None and asset_value > 0:
                        total_portfolio_value += asset_value
                        weighted_xirr_sum += float(asset_xirr) * asset_value
                        logger.debug(f"{security.symbol}: £{asset_value} at {asset_xirr * 100:.2f}% XIRR")

            if total_portfolio_value > 0:
                portfolio_weighted_xirr = weighted_xirr_sum / total_portfolio_value
                logger.info(f"Portfolio weighted XIRR: {portfolio_weighted_xirr * 100:.2f}%")
                return Decimal(str(portfolio_weighted_xirr))
            else:
                logger.warning("No portfolio value to calculate weighted XIRR")
                return None

        except Exception as e:
            logger.error(f"Weighted XIRR calculation failed: {e}")
            return None

    @classmethod
    def _calculate_portfolio_xirr(cls, portfolio):
        """Calculate portfolio XIRR from external cash flows only with correct signs"""
        from ..models import CashTransaction

        current_date = date.today()

        # Get only EXTERNAL cash movements (deposits/withdrawals)
        external_cash_transactions = CashTransaction.objects.filter(
            cash_account=portfolio.cash_account,
            transaction_type__in=['DEPOSIT', 'WITHDRAWAL']
        ).order_by('transaction_date')

        if not external_cash_transactions.exists():
            logger.info(f"No external cash transactions found for portfolio {portfolio.name}")
            return None

        # Check minimum time span
        first_date = external_cash_transactions.first().transaction_date.date()
        days_span = (current_date - first_date).days
        if days_span < cls.MIN_DAYS_SPAN:
            logger.info(f"Portfolio {portfolio.name}: Only {days_span} days of data, need {cls.MIN_DAYS_SPAN}")
            return None

        # Build cash flows with CORRECT signs for XIRR
        cash_flows_by_date = {}

        for cash_txn in external_cash_transactions:
            txn_date = cash_txn.transaction_date.date()
            amount = float(cash_txn.amount)

            # CORRECT SIGNS for XIRR:
            if cash_txn.transaction_type == 'DEPOSIT':
                amount = -abs(amount)  # DEPOSITS are negative (money OUT of your bank)
            elif cash_txn.transaction_type == 'WITHDRAWAL':
                amount = abs(amount)  # WITHDRAWALS are positive (money TO your bank)

            if txn_date not in cash_flows_by_date:
                cash_flows_by_date[txn_date] = 0.0
            cash_flows_by_date[txn_date] += amount

        # Add current portfolio value (positive - what you'd get back if liquidated)
        total_current_value = cls._calculate_portfolio_current_value(portfolio)
        if total_current_value > 0:
            cash_flows_by_date[current_date] = abs(total_current_value)

        # Filter out zero cash flows
        cash_flows_by_date = {date: amount for date, amount in cash_flows_by_date.items() if amount != 0.0}

        # Convert to lists for pyxirr
        if len(cash_flows_by_date) < 2:
            logger.info(f"Portfolio {portfolio.name}: Not enough external cash flow data points")
            return None

        # Sort by date and create parallel lists
        sorted_items = sorted(cash_flows_by_date.items())
        dates = [item[0] for item in sorted_items]
        cash_flows = [round(float(item[1]), 2) for item in sorted_items]

        logger.info(f"Portfolio {portfolio.name} external cash flows: {list(zip(dates, cash_flows))}")

        return cls._calculate_xirr_with_fallback(cash_flows, dates, f"Portfolio {portfolio.name}")

    @classmethod
    def _cache_asset_xirr(cls, portfolio, security, xirr_value):
        """Cache asset XIRR result"""
        from ..models import AssetXIRRCache

        latest_txn_id = Transaction.objects.filter(
            portfolio=portfolio,
            security=security
        ).aggregate(max_id=Max('id'))['max_id']

        cache_obj, created = AssetXIRRCache.objects.update_or_create(
            portfolio=portfolio,
            security=security,
            defaults={
                'xirr_value': xirr_value,
                'last_transaction_id': latest_txn_id,
            }
        )

        logger.info(f"{'Created' if created else 'Updated'} asset XIRR cache for {security.symbol}")

    @classmethod
    def _calculate_asset_xirr(cls, portfolio, security):
        """Calculate asset XIRR from scratch"""
        current_date = date.today()

        # Get transactions for this specific asset
        transactions = Transaction.objects.filter(
            portfolio=portfolio,
            security=security
        ).order_by('transaction_date')

        if not transactions.exists():
            return None

        # Check minimum time span
        first_date = transactions.first().transaction_date.date()
        days_span = (current_date - first_date).days
        if days_span < cls.MIN_DAYS_SPAN:
            logger.info(f"Asset {security.symbol}: Only {days_span} days of data, need {cls.MIN_DAYS_SPAN}")
            return None

        # Build cash flows - CLEAN NUMERIC CONVERSION
        cash_flows = []
        dates = []

        for txn in transactions:
            amount = cls._get_transaction_cash_flow(txn)
            if amount is not None:
                cash_flows.append(round(float(amount), 2))  # Clean conversion
                dates.append(txn.transaction_date.date())

        # Add current value of this asset as final cash flow
        current_value = cls._calculate_asset_current_value(portfolio, security)

        if current_value > 0:
            cash_flows.append(round(float(current_value), 2))  # Clean conversion
            dates.append(current_date)

        if len(cash_flows) < 2:
            logger.info(f"Asset {security.symbol}: Not enough cash flow data points")
            return None

        # ADD THIS LINE - this was missing in your file:
        return cls._calculate_xirr_with_fallback(cash_flows, dates, f"Asset {security.symbol}")
