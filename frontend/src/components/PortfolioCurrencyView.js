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
  Chip
} from '@mui/material';
import CurrencyDisplay from './CurrencyDisplay';
import api from '../services/api';

const PortfolioCurrencyView = ({ portfolio }) => {
  const [displayCurrency, setDisplayCurrency] = useState(portfolio.currency);
  const [currencyExposure, setCurrencyExposure] = useState({});
  const [portfolioValue, setPortfolioValue] = useState(null);
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCurrencies();
    fetchCurrencyExposure();
  }, [portfolio.id]);

  useEffect(() => {
    fetchPortfolioValue();
  }, [portfolio.id, displayCurrency]);

  const fetchCurrencies = async () => {
    try {
      const response = await api.currencies.list();
      setCurrencies(response.data);
    } catch (err) {
      console.error('Failed to fetch currencies:', err);
    }
  };

  const fetchCurrencyExposure = async () => {
    try {
      const response = await api.get(`/api/portfolios/${portfolio.id}/currency_exposure/`);
      setCurrencyExposure(response.data);
    } catch (err) {
      console.error('Failed to fetch currency exposure:', err);
    }
  };

  const fetchPortfolioValue = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/portfolios/${portfolio.id}/value/`, {
        params: { currency: displayCurrency }
      });
      setPortfolioValue(response.data.value);
    } catch (err) {
      console.error('Failed to fetch portfolio value:', err);
    } finally {
      setLoading(false);
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
              {currencies.map((currency) => (
                <MenuItem key={currency.code} value={currency.code}>
                  {currency.code} - {currency.symbol}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Typography variant="h4" gutterBottom>
          {loading ? (
            '...'
          ) : (
            <CurrencyDisplay
              amount={portfolioValue}
              currency={displayCurrency}
              showCode={true}
            />
          )}
        </Typography>

        <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
          Currency Exposure
        </Typography>

        <Grid container spacing={1}>
          {Object.entries(currencyExposure).map(([currency, data]) => (
            <Grid item key={currency}>
              <Chip
                label={`${currency}: ${new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: displayCurrency,
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                }).format(data.converted_amount || data.amount)}`}
                variant="outlined"
              />
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
};

export default PortfolioCurrencyView;