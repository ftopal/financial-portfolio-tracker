import React, { useState, useEffect } from 'react';
import {
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tooltip,
  CircularProgress
} from '@mui/material';
import { HelpOutline } from '@mui/icons-material';
import api from '../services/api';

const CurrencySelector = ({
  value,
  onChange,
  label = "Currency",
  showHelper = false,
  fullWidth = false,
  size = "medium",
  disabled = false
}) => {
  const [currencies, setCurrencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCurrencies();
  }, []);

  const fetchCurrencies = async () => {
    try {
      // Use api.currencies.list() which is the method you defined
      const response = await api.currencies.list();
      console.log('Currency API response:', response);

      // Handle different response structures
      let currencyData;
      if (Array.isArray(response.data)) {
        currencyData = response.data;
      } else if (response.data && Array.isArray(response.data.results)) {
        // Handle paginated response
        currencyData = response.data.results;
      } else if (response.data && response.data.currencies) {
        // Handle wrapped response
        currencyData = response.data.currencies;
      } else {
        console.error('Unexpected response structure:', response);
        throw new Error('Invalid response structure');
      }

      // Filter out GBp from transaction currency selections too
      const filteredCurrencies = currencyData.filter(currency => {
        // Remove GBp (British Pence) from currency selector dropdowns
        // Users shouldn't manually select GBp - it should be handled automatically for UK securities
        return currency.code !== 'GBp';
      });

      setCurrencies(filteredCurrencies);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch currencies:', err);
      setError('Failed to load currencies');
      // Fallback to common currencies
      setCurrencies([
        { code: 'USD', name: 'US Dollar', symbol: '$', decimal_places: 2 },
        { code: 'EUR', name: 'Euro', symbol: '€', decimal_places: 2 },
        { code: 'GBP', name: 'British Pound', symbol: '£', decimal_places: 2 },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <FormControl fullWidth={fullWidth} size={size} disabled>
        <InputLabel>{label}</InputLabel>
        <Select value="">
          <MenuItem value="">
            <CircularProgress size={20} />
          </MenuItem>
        </Select>
      </FormControl>
    );
  }

  return (
    <FormControl fullWidth={fullWidth} size={size} disabled={disabled}>
      <InputLabel id={`currency-select-${label}`}>{label}</InputLabel>
      <Select
        labelId={`currency-select-${label}`}
        value={value || 'USD'}
        onChange={(e) => onChange(e.target.value)}
        label={label}
        endAdornment={
          showHelper && (
            <Tooltip title="Select the currency for this item">
              <HelpOutline fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
            </Tooltip>
          )
        }
      >
        {currencies.map((currency) => (
          <MenuItem key={currency.code} value={currency.code}>
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <span>{currency.symbol} {currency.code}</span>
              <span style={{ fontSize: '0.875rem', color: '#6b7280', marginLeft: '8px' }}>
                {currency.name}
              </span>
            </div>
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

export default CurrencySelector;