import yfinance as yf
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db import IntegrityError
from ..models import Security, PriceHistory
import logging
import time
import pandas as pd

logger = logging.getLogger(__name__)


class PriceHistoryService:
    """Clean service for managing historical price data"""

    REQUEST_DELAY = 0.5  # seconds between requests

    @classmethod
    def bulk_fetch_historical_prices(cls, security, start_date, end_date, force_update=False):
        """
        Fetch and store historical prices for a date range
        """
        try:
            # Convert dates to date objects if needed
            if isinstance(start_date, datetime):
                start_date = start_date.date()
            if isinstance(end_date, datetime):
                end_date = end_date.date()

            logger.info(f"Fetching historical prices for {security.symbol} from {start_date} to {end_date}")

            # Check if we already have data for this range (unless forcing update)
            if not force_update:
                existing_data = PriceHistory.objects.filter(
                    security=security,
                    date__date__gte=start_date,
                    date__date__lte=end_date
                ).exists()

                if existing_data:
                    logger.info(f"Historical data already exists for {security.symbol} in this range")
                    return {
                        'success': True,
                        'message': 'Data already exists',
                        'records_created': 0,
                        'records_updated': 0
                    }

            # Prepare symbol for Yahoo Finance
            symbol = security.symbol
            if security.security_type == 'CRYPTO' and not symbol.endswith('-USD'):
                symbol = f"{symbol}-USD"

            logger.info(f"Using Yahoo Finance symbol: {symbol}")

            # Fetch data from Yahoo Finance
            ticker = yf.Ticker(symbol)

            # Try to get historical data
            try:
                hist = ticker.history(start=start_date, end=end_date + timedelta(days=1))
                logger.info(f"Retrieved {len(hist)} price records from Yahoo Finance")

            except Exception as e:
                logger.error(f"Failed to fetch Yahoo Finance data for {security.symbol}: {str(e)}")
                return {
                    'success': False,
                    'error': f'Yahoo Finance API error: {str(e)}',
                    'records_created': 0,
                    'records_updated': 0
                }

            if hist.empty:
                logger.warning(f"No historical data available for {security.symbol}")
                return {
                    'success': False,
                    'error': 'No historical data available',
                    'records_created': 0,
                    'records_updated': 0
                }

            # Process and save the data
            records_created, records_updated = cls._save_historical_data(security, hist, force_update)

            # Rate limiting
            time.sleep(cls.REQUEST_DELAY)

            logger.info(
                f"Successfully processed {security.symbol}: {records_created} created, {records_updated} updated")

            return {
                'success': True,
                'records_created': records_created,
                'records_updated': records_updated,
                'date_range': f"{start_date} to {end_date}"
            }

        except Exception as e:
            logger.error(f"Error fetching historical prices for {security.symbol}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'records_created': 0,
                'records_updated': 0
            }

    @classmethod
    def _save_historical_data(cls, security, hist_data, force_update=False):
        """
        Save historical data to database
        """
        records_created = 0
        records_updated = 0

        # Process each record individually to avoid transaction conflicts
        for date_index, row in hist_data.iterrows():
            try:
                # Convert pandas timestamp to datetime
                price_date = timezone.make_aware(
                    datetime.combine(date_index.date(), datetime.min.time())
                )

                # Get close price
                close_price = row.get('Close')
                if pd.isna(close_price) or close_price <= 0:
                    logger.warning(
                        f"Skipping invalid close price for {security.symbol} on {date_index.date()}: {close_price}")
                    continue

                # Convert to Decimal
                close_decimal = Decimal(str(float(close_price)))

                # Prepare data - only use fields that exist in the clean model
                price_data = {
                    'security': security,
                    'date': price_date,
                    'currency': security.currency,
                    'close_price': close_decimal,
                    'data_source': 'yahoo'
                }

                # Add optional fields if available
                if not pd.isna(row.get('Open')):
                    price_data['open_price'] = Decimal(str(float(row.get('Open'))))
                if not pd.isna(row.get('High')):
                    price_data['high_price'] = Decimal(str(float(row.get('High'))))
                if not pd.isna(row.get('Low')):
                    price_data['low_price'] = Decimal(str(float(row.get('Low'))))
                if not pd.isna(row.get('Adj Close')):
                    price_data['adjusted_close'] = Decimal(str(float(row.get('Adj Close'))))
                if not pd.isna(row.get('Volume')):
                    price_data['volume'] = int(float(row.get('Volume')))

                # Save to database
                if force_update:
                    # Update or create
                    price_history, created = PriceHistory.objects.update_or_create(
                        security=security,
                        date=price_date,
                        defaults=price_data
                    )
                    if created:
                        records_created += 1
                    else:
                        records_updated += 1
                else:
                    # Only create if doesn't exist
                    try:
                        price_history = PriceHistory.objects.create(**price_data)
                        records_created += 1
                    except IntegrityError:
                        # Record already exists, skip
                        logger.debug(f"Price record already exists for {security.symbol} on {date_index.date()}")
                        continue

            except Exception as e:
                logger.error(f"Error saving price data for {security.symbol} on {date_index.date()}: {str(e)}")
                continue

        return records_created, records_updated

    @classmethod
    def backfill_security_prices(cls, security, days_back=365, force_update=False):
        """
        Backfill missing historical data for a security
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        logger.info(f"Backfilling {days_back} days of price data for {security.symbol}")

        return cls.bulk_fetch_historical_prices(security, start_date, end_date, force_update)

    @classmethod
    def validate_price_data(cls, security):
        """
        Validate price data integrity for a security
        """
        try:
            total_records = PriceHistory.objects.filter(security=security).count()

            if total_records == 0:
                return {'valid': False, 'message': 'No price data found'}

            # Check for invalid prices (negative or zero)
            invalid_prices = PriceHistory.objects.filter(
                security=security,
                close_price__lte=0
            ).count()

            # Check for recent data
            recent_date = date.today() - timedelta(days=30)
            recent_records = PriceHistory.objects.filter(
                security=security,
                date__date__gte=recent_date
            ).count()

            return {
                'valid': invalid_prices == 0,
                'total_records': total_records,
                'invalid_prices': invalid_prices,
                'recent_records': recent_records,
                'gaps': 0  # Simplified for now
            }

        except Exception as e:
            logger.error(f"Error validating price data for {security.symbol}: {str(e)}")
            return {'valid': False, 'error': str(e)}

    @classmethod
    def detect_price_gaps(cls, security, max_gap_days=7):
        """
        Detect gaps in historical price data
        """
        try:
            # Get all price history dates for this security
            price_dates = PriceHistory.objects.filter(
                security=security
            ).values_list('date__date', flat=True).order_by('date')

            if not price_dates:
                logger.info(f"No price history found for {security.symbol}")
                return []

            price_dates = list(price_dates)
            gaps = []

            for i in range(1, len(price_dates)):
                prev_date = price_dates[i - 1]
                curr_date = price_dates[i]
                gap_days = (curr_date - prev_date).days - 1

                # Skip weekends (gaps of 2 days from Friday to Monday)
                if gap_days > max_gap_days:
                    # Check if this is just a weekend
                    if not (gap_days <= 3 and prev_date.weekday() == 4):  # Friday
                        gaps.append({
                            'start_date': prev_date,
                            'end_date': curr_date,
                            'gap_days': gap_days
                        })

            if gaps:
                logger.info(f"Found {len(gaps)} gaps in price data for {security.symbol}")

            return gaps

        except Exception as e:
            logger.error(f"Error detecting price gaps for {security.symbol}: {str(e)}")
            return []