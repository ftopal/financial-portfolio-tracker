import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Box
} from '@mui/material';

const PortfolioCurrencyView = ({ portfolio }) => {
  const [displayCurrency, setDisplayCurrency] = useState(portfolio?.base_currency || 'USD');
  const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY'];

  const formatCurrency = (amount, currency) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  if (!portfolio) return null;

  // The key fix: portfolio values are already in base currency
  const portfolioValue = portfolio.total_value_with_cash || portfolio.total_value || 0;

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

        <Typography variant="h4" fontWeight="bold" gutterBottom>
          {formatCurrency(portfolioValue, portfolio.base_currency)}
        </Typography>

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
        </Box>
      </CardContent>
    </Card>
  );
};

export default PortfolioCurrencyView;