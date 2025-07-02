import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Box,
  CircularProgress
} from '@mui/material';
import axios from 'axios';

const PortfolioCurrencyView = ({ portfolio }) => {
  const [displayCurrency, setDisplayCurrency] = useState(portfolio?.base_currency || 'USD');
  const [convertedValue, setConvertedValue] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY'];

  const formatCurrency = (amount, currency) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  // Convert currency when display currency changes
  useEffect(() => {
    if (!portfolio) return;

    const portfolioValue = portfolio.total_value_with_cash || portfolio.total_value || 0;

    // If display currency is same as base currency, no conversion needed
    if (displayCurrency === portfolio.base_currency) {
      setConvertedValue(portfolioValue);
      setError(null);
      return;
    }

    // Perform currency conversion
    const convertCurrency = async () => {
      setLoading(true);
      setError(null);

      try {
        // Get the token from localStorage
        const token = localStorage.getItem('token');
        const BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/';

        const response = await axios.post(
          `${BASE_URL}api/currencies/convert/`,
          {
            amount: portfolioValue,
            from_currency: portfolio.base_currency,
            to_currency: displayCurrency
          },
          {
            headers: {
              'Authorization': `Token ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );

        setConvertedValue(response.data.converted_amount);
      } catch (err) {
        console.error('Currency conversion failed:', err);
        setError('Failed to convert currency');
        // Fallback to showing original value
        setConvertedValue(portfolioValue);
      } finally {
        setLoading(false);
      }
    };

    convertCurrency();
  }, [displayCurrency, portfolio]);

  if (!portfolio) return null;

  const portfolioValue = portfolio.total_value_with_cash || portfolio.total_value || 0;
  const displayValue = convertedValue !== null ? convertedValue : portfolioValue;

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6">Portfolio Value</Typography>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Display Currency</InputLabel>
            <Select
              value={displayCurrency}
              onChange={(e) => setDisplayCurrency(e.target.value)}
              label="Display Currency"
            >
              {currencies.map((currency) => (
                <MenuItem key={currency} value={currency}>
                  {currency} {currency === portfolio.base_currency ? '(Base)' : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {loading ? (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={30} />
          </Box>
        ) : (
          <>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              {formatCurrency(displayValue, displayCurrency)}
            </Typography>

            {/* Show original value if converted */}
            {displayCurrency !== portfolio.base_currency && !error && (
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {formatCurrency(portfolioValue, portfolio.base_currency)} (base currency)
              </Typography>
            )}

            {error && (
              <Typography variant="caption" color="error" display="block" mb={2}>
                {error}
              </Typography>
            )}

            <Box mt={3}>
              <Typography variant="subtitle2" gutterBottom>
                Currency Exposure
              </Typography>
              <Box display="flex" justifyContent="space-between" my={1}>
                <Typography variant="body2">{portfolio.base_currency}:</Typography>
                <Typography variant="body2" fontWeight="medium">
                  {formatCurrency(portfolioValue, portfolio.base_currency)}
                </Typography>
              </Box>

              {/* Show converted value in exposure if different currency selected */}
              {displayCurrency !== portfolio.base_currency && convertedValue && !error && (
                <Box display="flex" justifyContent="space-between" my={1}>
                  <Typography variant="body2">{displayCurrency} (converted):</Typography>
                  <Typography variant="body2" fontWeight="medium">
                    {formatCurrency(convertedValue, displayCurrency)}
                  </Typography>
                </Box>
              )}
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default PortfolioCurrencyView;