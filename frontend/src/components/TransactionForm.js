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
  InputAdornment,
  Tooltip,
  Chip
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { Search as SearchIcon, TrendingUp } from '@mui/icons-material';
import CurrencySelector from './CurrencySelector';
import CurrencyDisplay from './CurrencyDisplay';
import api, { currencyAPI } from '../services/api';
import debounce from 'lodash.debounce';

const TransactionForm = ({
  open,
  onClose,
  onSuccess,
  portfolioId,
  security = null,
  transaction = null,
  existingHoldings = null,
  portfolio = null
}) => {
  const [formData, setFormData] = useState({
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    currency: 'USD',
    transaction_date: new Date().toISOString().split('T')[0],
    fees: '0',
    notes: '',
    split_ratio: ''
  });

  const [selectedSecurity, setSelectedSecurity] = useState(null);
  const [portfolioData, setPortfolioData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exchangeRate, setExchangeRate] = useState(null);
  const [convertedAmount, setConvertedAmount] = useState(null);
  const [convertedAmountWithFees, setConvertedAmountWithFees] = useState(null);

  // Security search states
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchOptions, setSearchOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [portfolioHoldings, setPortfolioHoldings] = useState({});

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await api.portfolios.get(portfolioId);
      setPortfolioData(response.data);
      // Set default currency to portfolio's base currency
      setFormData(prev => ({
        ...prev,
        currency: response.data.base_currency || 'USD'
      }));
    } catch (err) {
      console.error('Failed to fetch portfolio:', err);
    }
  }, [portfolioId]);

  const fetchPortfolioHoldings = useCallback(async () => {
    try {
      const response = await api.portfolios.getHoldings(portfolioId);
      const holdings = {};
      response.data.forEach(holding => {
        holdings[holding.security.symbol] = holding.quantity;
      });
      setPortfolioHoldings(holdings);
    } catch (err) {
      console.error('Failed to fetch holdings:', err);
    }
  }, [portfolioId]);

  // Initialize form
  useEffect(() => {
    if (open) {
      fetchPortfolio();
      fetchPortfolioHoldings();

      if (security) {
        setSelectedSecurity(security);
        // Auto-set currency to security's currency when a security is pre-selected
        setFormData(prev => ({
          ...prev,
          currency: security.currency || prev.currency
        }));
      }

      if (transaction) {
        // Editing existing transaction
        setFormData({
          transaction_type: transaction.transaction_type,
          quantity: transaction.quantity.toString(),
          price: transaction.price.toString(),
          currency: transaction.currency || 'USD',
          transaction_date: transaction.transaction_date.split('T')[0],
          fees: transaction.fees?.toString() || '0',
          notes: transaction.notes || '',
          split_ratio: transaction.split_ratio || ''
        });
        setSelectedSecurity(transaction.security);
      }
    }
  }, [open, security, transaction, fetchPortfolio, fetchPortfolioHoldings]);

  // Auto-set currency when security is selected
  useEffect(() => {
    if (selectedSecurity && selectedSecurity.currency) {
      setFormData(prev => ({
        ...prev,
        currency: selectedSecurity.currency
      }));
    }
  }, [selectedSecurity]);

  // Calculate exchange rate when currency or amount changes
    const fetchExchangeRate = useCallback(async () => {
      try {
        const currentPortfolio = portfolioData || portfolio;
        const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

        if (formData.currency === portfolioCurrency) {
          setExchangeRate(1);
          setConvertedAmount(null);
          setConvertedAmountWithFees(null);
          return;
        }

        // Calculate amount based on transaction type with proper decimal handling
        const quantity = parseFloat(formData.quantity || 0);
        const price = parseFloat(formData.price || 0);

        // Round to 8 decimal places to prevent precision issues
        const amount = formData.transaction_type === 'DIVIDEND'
          ? Math.round(price * 100000000) / 100000000  // Round to 8 decimals
          : Math.round((price * quantity) * 100000000) / 100000000;  // Round to 8 decimals

        const fees = Math.round((parseFloat(formData.fees || 0)) * 100000000) / 100000000;

        // Don't proceed if amount is 0 or invalid
        if (!amount || amount === 0 || isNaN(amount)) {
          setExchangeRate(null);
          setConvertedAmount(null);
          setConvertedAmountWithFees(null);
          return;
        }

        // Convert the base amount with proper precision
        const response = await currencyAPI.convert({
          amount: Number(amount.toFixed(8)), // Limit to 8 decimal places
          from_currency: formData.currency,
          to_currency: portfolioCurrency,
          date: formData.transaction_date
        });

        const rate = response.data.converted_amount / amount;
        setExchangeRate(rate);
        setConvertedAmount(response.data.converted_amount);

        // Calculate total with fees
        let totalInTransactionCurrency;
        if (formData.transaction_type === 'BUY' || formData.transaction_type === 'DIVIDEND') {
          totalInTransactionCurrency = amount + fees;
        } else if (formData.transaction_type === 'SELL') {
          totalInTransactionCurrency = amount - fees;
        } else {
          totalInTransactionCurrency = amount;
        }

        // Round the total to prevent precision issues
        totalInTransactionCurrency = Math.round(totalInTransactionCurrency * 100000000) / 100000000;

        // Convert total with fees
        if (fees > 0) {
          const totalResponse = await currencyAPI.convert({
            amount: Number(totalInTransactionCurrency.toFixed(8)),
            from_currency: formData.currency,
            to_currency: portfolioCurrency,
            date: formData.transaction_date
          });
          setConvertedAmountWithFees(totalResponse.data.converted_amount);
        } else {
          setConvertedAmountWithFees(response.data.converted_amount);
        }

      } catch (error) {
        console.error('Failed to fetch exchange rate:', error);
        setExchangeRate(null);
        setConvertedAmount(null);
        setConvertedAmountWithFees(null);
      }
    }, [formData.currency, formData.quantity, formData.price, formData.fees, formData.transaction_date, formData.transaction_type, portfolio, portfolioData]);

  // Trigger exchange rate calculation
  useEffect(() => {
    const currentPortfolio = portfolioData || portfolio;
    const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

    if (currentPortfolio && formData.currency !== portfolioCurrency && formData.price && formData.quantity) {
      fetchExchangeRate();
    } else if (formData.currency === portfolioCurrency) {
      setExchangeRate(1);
      setConvertedAmount(null);
      setConvertedAmountWithFees(null);
    } else {
      setExchangeRate(null);
      setConvertedAmount(null);
      setConvertedAmountWithFees(null);
    }
  }, [formData.currency, formData.price, formData.quantity, formData.fees, portfolioData, portfolio, fetchExchangeRate]);

  // Security search functionality
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
        // Set currency to the imported security's currency
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
        price: parseFloat(formData.price || 0),
        fees: parseFloat(formData.fees || 0),
        currency: formData.currency,
        split_ratio: formData.transaction_type === 'SPLIT' ? formData.split_ratio : undefined
      };

      if (transaction) {
        await api.transactions.update(transaction.id, data);
      } else {
        await api.transactions.create(data);
      }

      onSuccess();
      onClose();
    } catch (err) {
      console.error('Transaction error:', err);
      setError(err.response?.data?.detail || 'Failed to save transaction');
    } finally {
      setLoading(false);
    }
  };

  // Calculate totals
  const totalAmount = formData.transaction_type === 'DIVIDEND'
    ? parseFloat(formData.price || 0)
    : formData.transaction_type === 'SPLIT'
    ? 0
    : parseFloat(formData.price || 0) * parseFloat(formData.quantity || 0);

  const totalWithFees = formData.transaction_type === 'DIVIDEND'
    ? totalAmount + parseFloat(formData.fees || 0)
    : formData.transaction_type === 'SPLIT'
    ? 0
    : formData.transaction_type === 'BUY'
      ? totalAmount + parseFloat(formData.fees || 0)
      : totalAmount - parseFloat(formData.fees || 0);

  const currentPortfolio = portfolioData || portfolio;
  const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              {transaction ? 'Edit Transaction' : 'New Transaction'}
            </Typography>
            {portfolioCurrency && (
              <Chip
                label={`Portfolio: ${portfolioCurrency}`}
                color="primary"
                variant="outlined"
                size="small"
              />
            )}
          </Box>
        </DialogTitle>

        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
              {error}
            </Alert>
          )}

          {/* Security Selection */}
          {!security && !transaction && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" gutterBottom>
                Search Security
              </Typography>
              <Autocomplete
                open={searchOpen}
                onOpen={() => setSearchOpen(true)}
                onClose={() => setSearchOpen(false)}
                value={selectedSecurity}
                onChange={(event, newValue) => {
                  setSelectedSecurity(newValue);
                  if (newValue) {
                    setFormData(prev => ({
                      ...prev,
                      price: newValue.current_price?.toString() || '',
                      currency: newValue.currency || 'USD' // Auto-set currency
                    }));
                  }
                }}
                inputValue={searchInput}
                onInputChange={(event, newInputValue) => {
                  setSearchInput(newInputValue);
                }}
                options={searchOptions}
                getOptionLabel={(option) => `${option.symbol} - ${option.name}`}
                renderOption={(props, option) => (
                  <Box component="li" {...props}>
                    <Box>
                      <Typography variant="body1">
                        {option.symbol} - {option.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {option.exchange} | {option.currency} | Current: {option.current_price}
                      </Typography>
                    </Box>
                  </Box>
                )}
                loading={searchLoading}
                fullWidth
                renderInput={(params) => (
                  <TextField
                    {...params}
                    placeholder="Search by symbol or name..."
                    InputProps={{
                      ...params.InputProps,
                      startAdornment: <SearchIcon color="action" sx={{ mr: 1 }} />,
                      endAdornment: (
                        <>
                          {searchLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
                noOptionsText={
                  searchInput.length >= 2 ? (
                    <Box sx={{ p: 2 }}>
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
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Type at least 2 characters to search
                    </Typography>
                  )
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
                    price: newType === 'SPLIT' ? '0' : prev.price,
                    fees: newType === 'SPLIT' ? '0' : prev.fees
                  }));
                }}
                label="Transaction Type"
              >
                <MenuItem value="BUY">Buy</MenuItem>
                <MenuItem value="SELL">Sell</MenuItem>
                <MenuItem value="DIVIDEND">Dividend</MenuItem>
                <MenuItem value="SPLIT">Stock Split</MenuItem>
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
          </Box>

          {/* Quantity and Price */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
            <TextField
              type="number"
              label="Quantity"
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
              inputProps={{ step: "0.00000001", min: "0" }}
              fullWidth
              required
            />

            {formData.transaction_type !== 'SPLIT' && (
              <TextField
                type="number"
                label={`Price per Unit (${formData.currency})`}
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                inputProps={{ step: "0.00000001", min: "0" }}
                fullWidth
                required
                helperText={`Enter price in ${formData.currency}`}
              />
            )}
          </Box>

          {/* Currency and Fees */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
            <CurrencySelector
              value={formData.currency}
              onChange={(value) => setFormData({ ...formData, currency: value })}
              fullWidth
              label="Transaction Currency"
              helperText={
                formData.currency !== portfolioCurrency
                  ? `Will be converted to ${portfolioCurrency} (portfolio currency)`
                  : `Same as portfolio currency`
              }
            />

            {formData.transaction_type !== 'SPLIT' && (
              <TextField
                type="number"
                label={`Fees (${formData.currency})`}
                value={formData.fees}
                onChange={(e) => setFormData({ ...formData, fees: e.target.value })}
                inputProps={{ step: "0.01", min: "0" }}
                fullWidth
              />
            )}
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

            {formData.transaction_type !== 'SPLIT' && (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Subtotal:</Typography>
                  <CurrencyDisplay
                    amount={totalAmount}
                    currency={formData.currency}
                    showCode={true}
                  />
                </Box>

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

                {currentPortfolio && formData.currency !== portfolioCurrency && convertedAmountWithFees && (
                  <>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                      <Typography variant="body2" color="text.secondary">
                        Portfolio Currency ({portfolioCurrency}):
                      </Typography>
                      <Typography variant="body2" color="text.secondary" fontWeight="bold">
                        <CurrencyDisplay
                          amount={convertedAmountWithFees}
                          currency={portfolioCurrency}
                          showCode={true}
                        />
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" textAlign="right">
                      Exchange Rate: 1 {formData.currency} = {exchangeRate?.toFixed(4)} {portfolioCurrency}
                    </Typography>
                  </>
                )}
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