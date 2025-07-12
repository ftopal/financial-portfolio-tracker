# backend/portfolio/services/xirr_service.py - FINAL FIXED VERSION

import pyxirr
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Max
from ..models import Transaction, Portfolio, Security
import logging

logger = logging.getLogger(__name__)


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
    def _calculate_portfolio_xirr(cls, portfolio):
        """Calculate portfolio XIRR from scratch"""
        current_date = date.today()

        # Get all transactions for portfolio in chronological order
        transactions = Transaction.objects.filter(
            portfolio=portfolio
        ).select_related('security').order_by('transaction_date')

        if not transactions.exists():
            logger.info(f"No transactions found for portfolio {portfolio.name}")
            return None

        # Check minimum time span
        first_date = transactions.first().transaction_date.date()
        days_span = (current_date - first_date).days
        if days_span < cls.MIN_DAYS_SPAN:
            logger.info(f"Portfolio {portfolio.name}: Only {days_span} days of data, need {cls.MIN_DAYS_SPAN}")
            return None

        # Build cash flows grouped by date
        cash_flows_by_date = {}

        for txn in transactions:
            txn_date = txn.transaction_date.date()
            amount = cls._get_transaction_cash_flow(txn)

            if amount is not None:
                if txn_date not in cash_flows_by_date:
                    cash_flows_by_date[txn_date] = 0.0
                cash_flows_by_date[txn_date] += amount

        # Add current portfolio value as final cash flow
        total_current_value = cls._calculate_portfolio_current_value(portfolio)

        if total_current_value > 0:
            cash_flows_by_date[current_date] = total_current_value

        # Convert to lists for pyxirr
        if len(cash_flows_by_date) < 2:
            logger.info(f"Portfolio {portfolio.name}: Not enough cash flow data points")
            return None

        # Sort by date and create parallel lists - ENSURE CLEAN NUMERIC TYPES
        sorted_items = sorted(cash_flows_by_date.items())
        dates = [item[0] for item in sorted_items]
        cash_flows = [round(float(item[1]), 2) for item in sorted_items]  # Clean conversion

        logger.info(f"Portfolio {portfolio.name} cash flows: {list(zip(dates, cash_flows))}")

        try:
            xirr_result = pyxirr.xirr(cash_flows, dates)
            logger.info(f"Portfolio {portfolio.name} XIRR: {xirr_result}")
            return Decimal(str(xirr_result)) if xirr_result is not None else None

        except Exception as e:
            logger.error(f"Portfolio XIRR calculation failed for {portfolio.name}: {e}")
            return None

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

        logger.info(f"Asset {security.symbol} cash flows: {list(zip(dates, cash_flows))}")

        try:
            xirr_result = pyxirr.xirr(cash_flows, dates)
            logger.info(f"Asset {security.symbol} XIRR: {xirr_result}")
            return Decimal(str(xirr_result)) if xirr_result is not None else None

        except Exception as e:
            logger.error(f"Asset XIRR calculation failed for {security.symbol}: {e}")
            return None

    @classmethod
    def _get_transaction_cash_flow(cls, transaction):
        """Convert transaction to cash flow amount - CLEAN NUMERIC HANDLING"""

        # Calculate base amount with clean numeric conversion
        if transaction.base_amount:
            base_amount = round(float(transaction.base_amount), 2)
        else:
            # Calculate base amount manually
            txn_amount = float(transaction.quantity) * float(transaction.price)
            exchange_rate = float(transaction.exchange_rate or 1)
            base_amount = round(txn_amount * exchange_rate, 2)

        if transaction.transaction_type == 'BUY':
            # Money out (negative)
            return -base_amount

        elif transaction.transaction_type == 'SELL':
            # Money in (positive) - subtract fees
            fees_in_base = round(float(transaction.fees or 0) * float(transaction.exchange_rate or 1), 2)
            return round(base_amount - fees_in_base, 2)

        elif transaction.transaction_type == 'DIVIDEND':
            # Income (positive) - subtract fees
            fees_in_base = round(float(transaction.fees or 0) * float(transaction.exchange_rate or 1), 2)
            return round(base_amount - fees_in_base, 2)

        else:
            # Skip other transaction types (SPLIT, etc.)
            return None

    @classmethod
    def _calculate_portfolio_current_value(cls, portfolio):
        """Calculate current portfolio value without using get_holdings to avoid conflicts"""
        total_value = 0.0

        # Calculate value for each security
        securities_with_transactions = Transaction.objects.filter(
            portfolio=portfolio
        ).values_list('security_id', flat=True).distinct()

        for security_id in securities_with_transactions:
            try:
                security = Security.objects.get(id=security_id)
                asset_value = cls._calculate_asset_current_value(portfolio, security)
                total_value += asset_value
            except Security.DoesNotExist:
                continue

        # Add cash balance
        if hasattr(portfolio, 'cash_account') and portfolio.cash_account:
            total_value += float(portfolio.cash_account.balance)

        return round(total_value, 2)

    @classmethod
    def _calculate_asset_current_value(cls, portfolio, security):
        """Calculate current value of a specific asset without using get_holdings"""

        # Calculate total quantity from transactions
        transactions = Transaction.objects.filter(
            portfolio=portfolio,
            security=security
        ).order_by('transaction_date')

        total_quantity = 0.0

        for txn in transactions:
            if txn.transaction_type == 'BUY':
                total_quantity += float(txn.quantity)
            elif txn.transaction_type == 'SELL':
                total_quantity -= float(txn.quantity)

        if total_quantity <= 0:
            return 0.0

        # Calculate current value
        current_price = float(security.current_price)
        current_value = total_quantity * current_price

        return round(current_value, 2)

    @classmethod
    def _should_recalculate_portfolio(cls, portfolio, cache_obj):
        """Check if portfolio XIRR cache is stale"""
        latest_txn = Transaction.objects.filter(
            portfolio=portfolio
        ).aggregate(max_id=Max('id'))['max_id']

        return latest_txn != cache_obj.last_transaction_id

    @classmethod
    def _should_recalculate_asset(cls, portfolio, security, cache_obj):
        """Check if asset XIRR cache is stale"""
        latest_txn = Transaction.objects.filter(
            portfolio=portfolio,
            security=security
        ).aggregate(max_id=Max('id'))['max_id']

        return latest_txn != cache_obj.last_transaction_id

    @classmethod
    def _cache_portfolio_xirr(cls, portfolio, xirr_value):
        """Cache portfolio XIRR result"""
        from ..models import PortfolioXIRRCache

        latest_txn_id = Transaction.objects.filter(
            portfolio=portfolio
        ).aggregate(max_id=Max('id'))['max_id']

        cache_obj, created = PortfolioXIRRCache.objects.update_or_create(
            portfolio=portfolio,
            defaults={
                'xirr_value': xirr_value,
                'last_transaction_id': latest_txn_id,
            }
        )

        logger.info(f"{'Created' if created else 'Updated'} portfolio XIRR cache for {portfolio.name}")

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
    def invalidate_portfolio_cache(cls, portfolio):
        """Manually invalidate portfolio XIRR cache"""
        from ..models import PortfolioXIRRCache, AssetXIRRCache

        PortfolioXIRRCache.objects.filter(portfolio=portfolio).delete()
        AssetXIRRCache.objects.filter(portfolio=portfolio).delete()

        logger.info(f"Invalidated all XIRR cache for portfolio {portfolio.name}")

    @classmethod
    def invalidate_asset_cache(cls, portfolio, security):
        """Manually invalidate asset XIRR cache"""
        from ..models import AssetXIRRCache

        AssetXIRRCache.objects.filter(portfolio=portfolio, security=security).delete()

        logger.info(f"Invalidated XIRR cache for {security.symbol} in {portfolio.name}")