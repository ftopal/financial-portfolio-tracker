// frontend/src/components/TransactionForm.js - Updated with MUI Autocomplete + Yahoo Import

import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Box,
  Typography,
  Autocomplete,
  CircularProgress,
  Paper,
  InputAdornment
} from '@mui/material';
import { Search as SearchIcon, TrendingUp } from '@mui/icons-material';
import CurrencySelector from './CurrencySelector';
import CurrencyDisplay from './CurrencyDisplay';
import api from '../services/api';
import debounce from 'lodash.debounce';

const TransactionForm = ({
  open,
  onClose,
  onSuccess,
  portfolioId,
  security = null,
  transaction = null,
  existingHoldings = null  // Add this prop to pass holdings from parent
}) => {
  const [formData, setFormData] = useState({
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    currency: 'USD',
    transaction_date: new Date().toISOString().split('T')[0],
    fees: '0',
    notes: ''
  });

  const [selectedSecurity, setSelectedSecurity] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exchangeRate, setExchangeRate] = useState(null);
  const [convertedAmount, setConvertedAmount] = useState(null);

  // Security search states
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchOptions, setSearchOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [portfolioHoldings, setPortfolioHoldings] = useState({});

  useEffect(() => {
    if (open) {
      fetchPortfolio();

      // Only fetch holdings if not provided via props
      if (!existingHoldings) {
        fetchPortfolioHoldings();
      } else {
        setPortfolioHoldings(existingHoldings);
      }

      if (security) {
        // Get the quantity for this security
        const securityQuantity = existingHoldings
          ? (existingHoldings[security.symbol] || security.total_quantity || 0)
          : (security.total_quantity || 0);

        setSelectedSecurity(security);
        setFormData(prev => ({
          ...prev,
          price: security.current_price?.toString() || '',
          currency: security.currency || 'USD',
          // Auto-fill quantity for dividends
          quantity: prev.transaction_type === 'DIVIDEND' && securityQuantity > 0
            ? securityQuantity.toString()
            : prev.quantity
        }));
      }
      if (transaction) {
        // Load transaction data for editing
        setFormData({
          transaction_type: transaction.transaction_type,
          quantity: transaction.quantity.toString(),
          price: transaction.price.toString(),
          currency: transaction.currency || transaction.security.currency,
          transaction_date: transaction.transaction_date.split('T')[0],
          fees: transaction.fees?.toString() || '0',
          notes: transaction.notes || ''
        });
        setSelectedSecurity(transaction.security);
      }
    }
  }, [open, security, transaction, existingHoldings, fetchPortfolio, fetchPortfolioHoldings]);

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await api.portfolios.get(portfolioId);
      setPortfolio(response.data);
    } catch (err) {
      console.error('Failed to fetch portfolio:', err);
    }
  }, [portfolioId]);

  const fetchPortfolioHoldings = useCallback(async () => {
    try {
      const response = await api.portfolios.getHoldings(portfolioId);
      const holdings = {};
      if (response.data) {
        // Create a map of symbol to quantity for easy lookup
        Object.values(response.data).forEach(holding => {
          holdings[holding.security.symbol] = holding.quantity;
        });
      }
      setPortfolioHoldings(holdings);
    } catch (err) {
      console.error('Failed to fetch holdings:', err);
    }
  }, [portfolioId]);

  // Also update the form data when transaction type changes to DIVIDEND
  useEffect(() => {
    if (formData.transaction_type === 'DIVIDEND' && selectedSecurity) {
      const holdingQuantity = portfolioHoldings[selectedSecurity.symbol] || selectedSecurity.total_quantity || 0;
      if (holdingQuantity > 0 && !formData.quantity) {
        setFormData(prev => ({
          ...prev,
          quantity: holdingQuantity.toString()
        }));
      }
    }
  }, [formData.transaction_type, formData.quantity, selectedSecurity, portfolioHoldings]);

  const searchSecurities = React.useMemo(
    () =>
      debounce(async (query) => {
        if (!query || query.length < 2) {
          setSearchOptions([]);
          return;
        }

        setSearchLoading(true);
        try {
          const response = await api.securities.search(query);
          setSearchOptions(response.data || []);
        } catch (err) {
          console.error('Search error:', err);
          setSearchOptions([]);
        } finally {
          setSearchLoading(false);
        }
      }, 300),
    []
  );

  useEffect(() => {
    if (searchInput && searchOpen) {
      searchSecurities(searchInput);
    }
  }, [searchInput, searchOpen, searchSecurities]);

  const handleImportFromYahoo = async () => {
    if (!searchInput || searchInput.length < 1) return;

    setSearchLoading(true);
    setError('');

    try {
      const response = await api.securities.import(searchInput.toUpperCase());

      if (response.data.security) {
        const imported = response.data.security;
        setSelectedSecurity(imported);
        setSearchOptions([imported]);
        setFormData(prev => ({
          ...prev,
          price: imported.current_price?.toString() || '',
          currency: imported.currency || 'USD'
        }));
        setSearchOpen(false);
        setError('');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to import from Yahoo Finance');
    } finally {
      setSearchLoading(false);
    }
  };

  // Calculate exchange rate when currency changes
  useEffect(() => {
    if (portfolio && formData.currency !== portfolio.currency && formData.price && formData.quantity) {
      fetchExchangeRate();
    } else {
      setExchangeRate(null);
      setConvertedAmount(null);
    }
  }, [formData.currency, formData.price, formData.quantity, portfolio, fetchExchangeRate]);

  const fetchExchangeRate = useCallback(async () => {
    try {
      const amount = parseFloat(formData.price) * parseFloat(formData.quantity);
      const response = await api.currencies.convert({
        amount: amount,
        from_currency: formData.currency,
        to_currency: portfolio.currency,
        date: formData.transaction_date
      });

      setExchangeRate(response.data.converted_amount / amount);
      setConvertedAmount(response.data.converted_amount);
    } catch (err) {
      console.error('Failed to fetch exchange rate:', err);
      setExchangeRate(null);
      setConvertedAmount(null);
    }
  }, [formData.price, formData.quantity, formData.currency, formData.transaction_date, portfolio]);

  const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  setError('');

  try {
    const data = {
      portfolio: portfolioId,
      security: selectedSecurity.id,
      ...formData,
      quantity: parseFloat(formData.quantity),
      price: parseFloat(formData.price),
      fees: parseFloat(formData.fees || 0),
      currency: formData.currency
    };

    if (transaction) {
      await api.transactions.update(transaction.id, data);
    } else {
      await api.transactions.create(data);
    }

    onSuccess();
    onClose();
    // Remove resetForm() call since the form is closing anyway
  } catch (err) {
    console.error('Transaction error:', err);
    setError(err.response?.data?.detail || 'Failed to save transaction');
  } finally {
    setLoading(false);
  }
};

  const resetForm = () => {
    setFormData({
      transaction_type: 'BUY',
      quantity: '',
      price: '',
      currency: 'USD',
      transaction_date: new Date().toISOString().split('T')[0],
      fees: '0',
      notes: ''
    });
    setSelectedSecurity(null);
    setSearchInput('');
    setSearchOptions([]);
    setExchangeRate(null);
    setConvertedAmount(null);
  };

  const totalAmount = parseFloat(formData.price || 0) * parseFloat(formData.quantity || 0);
  const totalWithFees = totalAmount + parseFloat(formData.fees || 0);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          {transaction ? 'Edit Transaction' : 'New Transaction'}
        </DialogTitle>

        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Security Selection with Yahoo Import */}
          {!security && (
            <Box sx={{ mb: 3, mt: 2 }}>
              <Autocomplete
                value={selectedSecurity}
                onChange={(event, newValue) => {
                  setSelectedSecurity(newValue);
                  if (newValue) {
                    // Check if we have holdings for this security
                    const holdingQuantity = portfolioHoldings[newValue.symbol] || 0;

                    setFormData(prev => ({
                      ...prev,
                      price: newValue.current_price?.toString() || '',
                      currency: newValue.currency || 'USD',
                      // Auto-fill quantity for dividends
                      quantity: prev.transaction_type === 'DIVIDEND' && holdingQuantity > 0
                        ? holdingQuantity.toString()
                        : prev.quantity
                    }));
                  }
                }}
                inputValue={searchInput}
                onInputChange={(event, newInputValue) => {
                  setSearchInput(newInputValue);
                }}
                options={searchOptions}
                getOptionLabel={(option) =>
                  option ? `${option.symbol} - ${option.name}` : ''
                }
                loading={searchLoading}
                open={searchOpen}
                onOpen={() => setSearchOpen(true)}
                onClose={() => setSearchOpen(false)}
                isOptionEqualToValue={(option, value) => option.id === value.id}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Search Security"
                    placeholder="Enter symbol or name..."
                    fullWidth
                    required={!selectedSecurity}
                    InputProps={{
                      ...params.InputProps,
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <React.Fragment>
                          {searchLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </React.Fragment>
                      ),
                    }}
                  />
                )}
                renderOption={(props, option) => (
                  <Box component="li" {...props}>
                    <Box sx={{ width: '100%' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body1">
                          <strong>{option.symbol}</strong> - {option.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          <CurrencyDisplay
                            amount={option.current_price}
                            currency={option.currency}
                            showCode={true}
                          />
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {option.exchange} • {option.security_type} • {option.currency}
                      </Typography>
                    </Box>
                  </Box>
                )}
                noOptionsText={
                  <Box sx={{ p: 2 }}>
                    {searchInput.length >= 2 ? (
                      <>
                        <Typography variant="body2" gutterBottom>
                          No results found for "{searchInput}"
                        </Typography>
                        <Button
                          variant="contained"
                          startIcon={<TrendingUp />}
                          onClick={handleImportFromYahoo}
                          disabled={searchLoading}
                          fullWidth
                          sx={{ mt: 1 }}
                        >
                          Import {searchInput.toUpperCase()} from Yahoo Finance
                        </Button>
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        Type at least 2 characters to search
                      </Typography>
                    )}
                  </Box>
                }
                PaperComponent={(props) => (
                  <Paper {...props} elevation={8} />
                )}
              />
            </Box>
          )}

          {/* Selected Security Display */}
          {selectedSecurity && (
            <Box sx={{ mb: 3, p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
              <Typography variant="subtitle1" fontWeight="bold">
                {selectedSecurity.symbol} - {selectedSecurity.name}
              </Typography>
              <Typography variant="body2">
                Current Price: <CurrencyDisplay
                  amount={selectedSecurity.current_price}
                  currency={selectedSecurity.currency}
                  showCode={true}
                />
              </Typography>
            </Box>
          )}

          {/* Transaction Details */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Transaction Type</InputLabel>
              <Select
                value={formData.transaction_type}
                onChange={(e) => {
                  const newType = e.target.value;
                  setFormData(prev => ({
                    ...prev,
                    transaction_type: newType,
                    // Auto-fill quantity when switching to DIVIDEND
                    quantity: newType === 'DIVIDEND' && selectedSecurity && portfolioHoldings[selectedSecurity.symbol]
                      ? portfolioHoldings[selectedSecurity.symbol].toString()
                      : prev.quantity
                  }));
                }}
                label="Transaction Type"
              >
                <MenuItem value="BUY">Buy</MenuItem>
                <MenuItem value="SELL">Sell</MenuItem>
                <MenuItem value="DIVIDEND">Dividend</MenuItem>
              </Select>
            </FormControl>

            <TextField
              type="date"
              label="Transaction Date"
              value={formData.transaction_date}
              onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
              required
            />

            <TextField
              type="number"
              label={formData.transaction_type === 'DIVIDEND' ? 'Number of Shares' : 'Quantity'}
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
              inputProps={{ step: "0.0001", min: "0" }}
              fullWidth
              required
              helperText={
                formData.transaction_type === 'DIVIDEND' && selectedSecurity && portfolioHoldings[selectedSecurity.symbol]
                  ? `You currently own ${portfolioHoldings[selectedSecurity.symbol]} shares`
                  : ''
              }
            />

            <TextField
              type="number"
              label={formData.transaction_type === 'DIVIDEND' ? 'Total Dividend Amount' : 'Price per Unit'}
              value={formData.price}
              onChange={(e) => setFormData({ ...formData, price: e.target.value })}
              inputProps={{ step: "0.01", min: "0" }}
              fullWidth
              required
              helperText={
                formData.transaction_type === 'DIVIDEND'
                  ? formData.quantity && formData.price
                    ? <span>Dividend per share: <CurrencyDisplay
                        amount={parseFloat(formData.price) / parseFloat(formData.quantity)}
                        currency={formData.currency}
                        showCode={false}
                      /></span>
                    : 'Enter the total dividend amount received'
                  : ''
              }
            />

            <CurrencySelector
              value={formData.currency}
              onChange={(value) => setFormData({ ...formData, currency: value })}
              fullWidth
              label="Transaction Currency"
            />

            <TextField
              type="number"
              label="Fees"
              value={formData.fees}
              onChange={(e) => setFormData({ ...formData, fees: e.target.value })}
              inputProps={{ step: "0.01", min: "0" }}
              fullWidth
            />
          </Box>

          <TextField
            multiline
            rows={2}
            label="Notes"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            fullWidth
            sx={{ mb: 2 }}
          />

          {/* Transaction Summary */}
          <Box sx={{ p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Transaction Summary
            </Typography>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2">Subtotal:</Typography>
              <CurrencyDisplay
                amount={totalAmount}
                currency={formData.currency}
                showCode={true}
              />
            </Box>

            {formData.transaction_type === 'DIVIDEND' && formData.quantity && formData.price && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Dividend per share:</Typography>
                <CurrencyDisplay
                  amount={parseFloat(formData.price) / parseFloat(formData.quantity)}
                  currency={formData.currency}
                  showCode={true}
                />
              </Box>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2">Fees:</Typography>
              <CurrencyDisplay
                amount={parseFloat(formData.fees || 0)}
                currency={formData.currency}
                showCode={true}
              />
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" fontWeight="bold">Total:</Typography>
              <Typography variant="body2" fontWeight="bold">
                <CurrencyDisplay
                  amount={totalWithFees}
                  currency={formData.currency}
                  showCode={true}
                />
              </Typography>
            </Box>

            {portfolio && formData.currency !== portfolio.currency && convertedAmount && (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Portfolio Currency ({portfolio.currency}):
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    <CurrencyDisplay
                      amount={convertedAmount}
                      currency={portfolio.currency}
                      showCode={true}
                    />
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Exchange Rate: 1 {formData.currency} = {exchangeRate?.toFixed(4)} {portfolio.currency}
                </Typography>
              </>
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !selectedSecurity}
          >
            {loading ? 'Saving...' : (transaction ? 'Update' : 'Create')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default TransactionForm;