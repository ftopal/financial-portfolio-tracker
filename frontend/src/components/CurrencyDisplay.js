import React, { useState, useEffect } from 'react';
import { Tooltip } from '@mui/material';
import api from '../services/api';

const CurrencyDisplay = ({
  amount,
  currency = 'USD',
  displayCurrency = null,
  showOriginal = true,
  showCode = false,
  className = '',
  colorize = false
}) => {
  const [convertedAmount, setConvertedAmount] = useState(null);
  const [exchangeRate, setExchangeRate] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (displayCurrency && displayCurrency !== currency) {
      convertCurrency();
    } else {
      setConvertedAmount(null);
      setExchangeRate(null);
    }
  }, [amount, currency, displayCurrency]);

  const convertCurrency = async () => {
    if (!amount || amount === 0) {
      setConvertedAmount(0);
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/api/currencies/convert/', {
        amount: amount,
        from_currency: currency,
        to_currency: displayCurrency
      });
      setConvertedAmount(response.data.converted_amount);
      setExchangeRate(response.data.converted_amount / amount);
    } catch (err) {
      console.error('Failed to convert currency:', err);
      setConvertedAmount(null);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value, currencyCode) => {
    if (value === null || value === undefined) return '-';

    const formatter = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: currencyCode === 'JPY' ? 0 : 2,
      maximumFractionDigits: currencyCode === 'JPY' ? 0 : 2,
    });

    return formatter.format(value);
  };

  const getColorClass = (value) => {
    if (!colorize || !value) return '';
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  // If no conversion needed
  if (!displayCurrency || displayCurrency === currency || loading) {
    const formattedAmount = formatCurrency(amount, currency);
    return (
      <span className={`${className} ${getColorClass(amount)}`}>
        {formattedAmount}
        {showCode && ` ${currency}`}
      </span>
    );
  }

  // If conversion is done
  if (convertedAmount !== null) {
    const formattedConverted = formatCurrency(convertedAmount, displayCurrency);
    const formattedOriginal = formatCurrency(amount, currency);

    if (showOriginal) {
      return (
        <Tooltip
          title={
            <div>
              <div>Original: {formattedOriginal}</div>
              {exchangeRate && (
                <div className="text-xs opacity-75">
                  Rate: 1 {currency} = {exchangeRate.toFixed(4)} {displayCurrency}
                </div>
              )}
            </div>
          }
        >
          <span className={`${className} ${getColorClass(convertedAmount)} cursor-help`}>
            {formattedConverted}
            {showCode && ` ${displayCurrency}`}
          </span>
        </Tooltip>
      );
    }

    return (
      <span className={`${className} ${getColorClass(convertedAmount)}`}>
        {formattedConverted}
        {showCode && ` ${displayCurrency}`}
      </span>
    );
  }

  // Fallback
  return <span className={className}>-</span>;
};

export default CurrencyDisplay;