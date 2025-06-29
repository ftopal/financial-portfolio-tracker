import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Box,
  Chip,
  CircularProgress
} from '@mui/material';
import CurrencyDisplay from './CurrencyDisplay';
import api from '../services/api';
import { currencyAPI, portfolioAPI } from '../services/api';

const PortfolioCurrencyView = ({ portfolio }) => {
  const [displayCurrency, setDisplayCurrency] = useState(portfolio.currency || 'USD');
  const [currencyExposure, setCurrencyExposure] = useState({});
  const [portfolioValue, setPortfolioValue] = useState(null);
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exposureLoading, setExposureLoading] = useState(false);

  useEffect(() => {
    fetchCurrencies();
    fetchCurrencyExposure();
  }, [portfolio.id]);

  useEffect(() => {
    if (portfolio.id) {
      fetchPortfolioValue();
    }
  }, [portfolio.id, displayCurrency]);

  const fetchCurrencies = async () => {
    try {
      // First, try to use a fallback list of common currencies
      const defaultCurrencies = [
        { code: 'USD', name: 'US Dollar', symbol: '$' },
        { code: 'EUR', name: 'Euro', symbol: '€' },
        { code: 'GBP', name: 'British Pound', symbol: '£' },
        { code: 'JPY', name: 'Japanese Yen', symbol: '¥' },
        { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$' },
        { code: 'AUD', name: 'Australian Dollar', symbol: 'A$' },
        { code: 'CHF', name: 'Swiss Franc', symbol: 'CHF' },
        { code: 'CNY', name: 'Chinese Yuan', symbol: '¥' },
      ];

      setCurrencies(defaultCurrencies);

      // Then try to fetch from API
      try {
        const response = await currencyAPI.list();
        if (response.data && response.data.length > 0) {
          setCurrencies(response.data);
        }
      } catch (apiError) {
        console.log('Using default currency list');
      }
    } catch (err) {
      console.error('Failed to fetch currencies:', err);
    }
  };

  const fetchCurrencyExposure = async () => {
    setExposureLoading(true);
    try {
      // Use the function from portfolioAPI if it exists
      if (portfolioAPI && portfolioAPI.getCurrencyExposure) {
        const response = await portfolioAPI.getCurrencyExposure(portfolio.id);
        // Extract exposure data from response
        if (response.data && response.data.exposure) {
          setCurrencyExposure(response.data.exposure);
        } else if (response.data && typeof response.data === 'object') {
          // If the response is the exposure object directly
          setCurrencyExposure(response.data);
        }
      } else {
        // Fallback to direct API call
        const response = await api.get(`portfolios/${portfolio.id}/currency_exposure/`);
        if (response.data && response.data.exposure) {
          setCurrencyExposure(response.data.exposure);
        } else if (response.data && typeof response.data === 'object') {
          setCurrencyExposure(response.data);
        }
      }
    } catch (err) {
      console.error('Failed to fetch currency exposure:', err);
      setCurrencyExposure({});
    } finally {
      setExposureLoading(false);
    }
  };

  const fetchPortfolioValue = async () => {
    setLoading(true);
    try {
      // Use the function from portfolioAPI if it exists
      if (portfolioAPI && portfolioAPI.getValueInCurrency) {
        const response = await portfolioAPI.getValueInCurrency(portfolio.id, displayCurrency);
        setPortfolioValue(response.data.value);
      } else {
        // Fallback to direct API call
        const response = await api.get(`portfolios/${portfolio.id}/value/`, {
          params: { currency: displayCurrency }
        });
        setPortfolioValue(response.data.value);
      }
    } catch (err) {
      console.error('Failed to fetch portfolio value:', err);

      // If conversion fails, show a message
      if (err.response && err.response.status === 400) {
        // Exchange rate not found
        setPortfolioValue(null);
        console.error('Exchange rate not available for conversion');
      } else if (portfolio.total_value && displayCurrency === portfolio.currency) {
        // If it's the same currency, use the original value
        setPortfolioValue(portfolio.total_value);
      }
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount, currencyCode) => {
    if (amount === null || amount === undefined) return '-';

    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currencyCode || 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(amount);
    } catch (error) {
      return `${currencyCode || 'USD'} ${amount.toFixed(2)}`;
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
          <Typography variant="h6">Portfolio Value</Typography>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Display Currency</InputLabel>
            <Select
              value={displayCurrency}
              onChange={(e) => setDisplayCurrency(e.target.value)}
              label="Display Currency"
            >
              {currencies.length === 0 ? (
                <MenuItem value={displayCurrency}>
                  {displayCurrency}
                </MenuItem>
              ) : (
                currencies.map((currency) => (
                  <MenuItem key={currency.code} value={currency.code}>
                    {currency.code} - {currency.symbol}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Box>

        <Typography variant="h4" gutterBottom>
          {loading ? (
            <CircularProgress size={24} />
          ) : portfolioValue !== null ? (
            formatCurrency(portfolioValue, displayCurrency)
          ) : (
            <Box>
              <Typography variant="body2" color="error">
                No exchange rate available
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Run 'python manage.py update_exchange_rates' to load rates
              </Typography>
            </Box>
          )}
        </Typography>

        {Object.keys(currencyExposure).length > 0 && (
          <>
            <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
              Currency Exposure
            </Typography>

            <Grid container spacing={1}>
              {exposureLoading ? (
                <Grid item>
                  <CircularProgress size={20} />
                </Grid>
              ) : (
                Object.entries(currencyExposure).map(([currency, amount]) => {
                  // Skip if not a valid currency code (3 uppercase letters)
                  if (!currency.match(/^[A-Z]{3}$/)) {
                    return null;
                  }

                  // Parse the amount - it could be a number or a Decimal string
                  let numericAmount = 0;
                  if (typeof amount === 'number') {
                    numericAmount = amount;
                  } else if (typeof amount === 'string') {
                    numericAmount = parseFloat(amount);
                  } else if (typeof amount === 'object' && amount !== null) {
                    // Handle case where amount might be an object with value property
                    numericAmount = parseFloat(amount.value || amount.amount || 0);
                  }

                  // Only show currencies with non-zero exposure
                  if (numericAmount === 0 || isNaN(numericAmount)) {
                    return null;
                  }

                  return (
                    <Grid item key={currency}>
                      <Chip
                        label={`${currency}: ${formatCurrency(numericAmount, currency)}`}
                        variant="outlined"
                        size="small"
                        sx={{
                          backgroundColor: currency === portfolio.currency ? 'action.selected' : 'background.paper',
                          fontWeight: currency === portfolio.currency ? 'bold' : 'normal',
                          borderColor: currency === portfolio.currency ? 'primary.main' : undefined
                        }}
                      />
                    </Grid>
                  );
                }).filter(Boolean)
              )}
            </Grid>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default PortfolioCurrencyView;