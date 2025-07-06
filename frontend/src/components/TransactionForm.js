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
  onTransactionSaved,
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

  const [exchangeRateField, setExchangeRateField] = useState(''); // Manual exchange rate input
  const [baseAmountField, setBaseAmountField] = useState(''); // Manual base amount input
  const [autoExchangeRate, setAutoExchangeRate] = useState(null); // Fetched exchange rate
  const [autoBaseAmount, setAutoBaseAmount] = useState(null); // Calculated base amount
  const [isExchangeRateManual, setIsExchangeRateManual] = useState(false); // Track if user modified rate
  const [isBaseAmountManual, setIsBaseAmountManual] = useState(false); // Track if user modified base amount

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await api.portfolios.get(portfolioId);
      setPortfolioData(response.data);

      // ONLY set default currency for completely new transactions
      // Check if we have a transaction being edited
      if (!transaction && !formData.currency) {
        console.log('Setting default currency from portfolio');
        setFormData(prev => ({
          ...prev,
          currency: response.data.base_currency || 'USD'
        }));
      }
    } catch (err) {
      console.error('Failed to fetch portfolio:', err);
    }
  }, [portfolioId]);

  const fetchPortfolioHoldings = useCallback(async () => {
    try {
      const response = await api.portfolios.getHoldings(portfolioId);
      const holdings = {};

      // Handle different response structures safely
      const holdingsArray = response?.data?.results || response?.data || [];

      if (Array.isArray(holdingsArray)) {
        holdingsArray.forEach(holding => {
          if (holding?.security?.symbol) {
            holdings[holding.security.symbol] = holding.quantity;
          }
        });
      }

      setPortfolioHoldings(holdings);
    } catch (err) {
      console.error('Failed to fetch holdings:', err);
      setPortfolioHoldings({});
    }
  }, [portfolioId]);

  // Initialize form
  useEffect(() => {
    if (open) {
      console.log('Form opened with transaction:', transaction);
      console.log('Transaction currency:', transaction?.currency);

      // Fetch data first
      fetchPortfolio();
      fetchPortfolioHoldings();

      // Handle editing existing transaction FIRST (highest priority)
      if (transaction) {
        console.log('Setting form data for transaction edit');
        setFormData({
          transaction_type: transaction.transaction_type,
          quantity: transaction.quantity.toString(),
          price: transaction.price.toString(),
          currency: transaction.currency || 'USD', // This should be USD
          transaction_date: transaction.transaction_date.split('T')[0],
          fees: transaction.fees?.toString() || '0',
          notes: transaction.notes || '',
          split_ratio: transaction.split_ratio || ''
        });

        if (transaction.exchange_rate) {
          setExchangeRateField(transaction.exchange_rate.toString());
          setIsExchangeRateManual(true);
        }

        setSelectedSecurity(transaction.security);
        return; // IMPORTANT: Return early to prevent other logic from running
      }

      // Handle pre-selected security (for new transactions only)
      if (security && !transaction) {
        setSelectedSecurity(security);
        setFormData(prev => ({
          ...prev,
          currency: security.currency || prev.currency
        }));
        return; // Return early
      }

      // Handle new transaction (reset form) - only if no transaction and no security
      if (!transaction && !security) {
        setFormData(prev => ({
          ...prev,
          transaction_type: 'BUY',
          quantity: '',
          price: '',
          transaction_date: new Date().toISOString().split('T')[0],
          fees: '0',
          notes: '',
          split_ratio: ''
        }));

        setExchangeRateField('');
        setBaseAmountField('');
        setIsExchangeRateManual(false);
        setIsBaseAmountManual(false);
        setSelectedSecurity(null);
      }
    }
  }, [open, transaction, security]);


  // Auto-set currency when security is selected
  useEffect(() => {
    // Only auto-set currency from security if:
    // 1. NOT editing an existing transaction
    // 2. Form is open
    // 3. No existing currency is set
    if (selectedSecurity && selectedSecurity.currency && !transaction && open && !formData.currency) {
      console.log('Auto-setting currency from security:', selectedSecurity.currency);
      setFormData(prev => ({
        ...prev,
        currency: selectedSecurity.currency
      }));
    }
  }, [selectedSecurity, transaction, open]);

  // Calculate exchange rate when currency or amount changes
    const fetchExchangeRate = useCallback(async () => {
      try {
        const currentPortfolio = portfolioData || portfolio;
        const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

        if (formData.currency === portfolioCurrency) {
          setExchangeRate(1);
          setAutoExchangeRate(1);
          setExchangeRateField('1.0000');
          setConvertedAmount(null);
          setConvertedAmountWithFees(null);
          setAutoBaseAmount(null);
          setBaseAmountField('');
          return;
        }

        // Calculate amount based on transaction type with proper decimal handling
        const quantity = parseFloat(formData.quantity || 0);
        const price = parseFloat(formData.price || 0);
        const fees = parseFloat(formData.fees || 0);

        // Round to 8 decimal places to prevent precision issues
        const amount = formData.transaction_type === 'DIVIDEND'
          ? Math.round(price * 100000000) / 100000000
          : Math.round((price * quantity) * 100000000) / 100000000;

        // Don't proceed if amount is 0 or invalid
        if (!amount || amount === 0 || isNaN(amount)) {
          setExchangeRate(null);
          setAutoExchangeRate(null);
          setExchangeRateField('');
          setConvertedAmount(null);
          setConvertedAmountWithFees(null);
          setAutoBaseAmount(null);
          setBaseAmountField('');
          return;
        }

        // Fetch exchange rate for the transaction date
        const response = await currencyAPI.convert({
          amount: 1,
          from_currency: formData.currency,
          to_currency: portfolioCurrency,
          date: formData.transaction_date
        });

        const rate = response.data.converted_amount;
        setExchangeRate(rate);
        setAutoExchangeRate(rate);

        // Set exchange rate field only if user hasn't manually modified it
        if (!isExchangeRateManual) {
          setExchangeRateField(rate.toFixed(4));
        }

        // Calculate base amount
        let totalInTransactionCurrency;
        if (formData.transaction_type === 'BUY' || formData.transaction_type === 'DIVIDEND') {
          totalInTransactionCurrency = amount + fees;
        } else if (formData.transaction_type === 'SELL') {
          totalInTransactionCurrency = amount - fees;
        } else {
          totalInTransactionCurrency = amount;
        }

        const currentRate = isExchangeRateManual ? parseFloat(exchangeRateField) : rate;
        const calculatedBaseAmount = totalInTransactionCurrency * currentRate;

        setAutoBaseAmount(calculatedBaseAmount);

        if (!isBaseAmountManual) {
          setBaseAmountField(calculatedBaseAmount.toFixed(2));
        }

        setConvertedAmount(amount * currentRate);
        setConvertedAmountWithFees(calculatedBaseAmount);

      } catch (error) {
        console.error('Failed to fetch exchange rate:', error);
        setExchangeRate(null);
        setAutoExchangeRate(null);
        setExchangeRateField('');
        setConvertedAmount(null);
        setConvertedAmountWithFees(null);
        setAutoBaseAmount(null);
        setBaseAmountField('');
      }
    }, [
      formData.currency,
      formData.quantity,
      formData.price,
      formData.fees,
      formData.transaction_date,
      formData.transaction_type,
      portfolioData,
      portfolio,
      exchangeRateField,
      isExchangeRateManual,
      isBaseAmountManual
    ]);

  // Trigger exchange rate calculation
  useEffect(() => {
    const currentPortfolio = portfolioData || portfolio;
    const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

    if (currentPortfolio && formData.currency !== portfolioCurrency && formData.price && formData.quantity && open) {
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
  }, [
    formData.currency,
    formData.price,
    formData.quantity,
    formData.fees,
    formData.transaction_date,
    portfolioData,
    portfolio,
    open
  ]);

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

  const handleExchangeRateChange = (event) => {
    const value = event.target.value;
    setExchangeRateField(value);
    setIsExchangeRateManual(true);

    // Recalculate base amount with new rate
    if (value && !isNaN(parseFloat(value))) {
      const quantity = parseFloat(formData.quantity || 0);
      const price = parseFloat(formData.price || 0);
      const fees = parseFloat(formData.fees || 0);

      let totalInTransactionCurrency;
      if (formData.transaction_type === 'BUY' || formData.transaction_type === 'DIVIDEND') {
        totalInTransactionCurrency = (quantity * price) + fees;
      } else if (formData.transaction_type === 'SELL') {
        totalInTransactionCurrency = (quantity * price) - fees;
      } else {
        totalInTransactionCurrency = quantity * price;
      }

      const newBaseAmount = totalInTransactionCurrency * parseFloat(value);

      if (!isBaseAmountManual) {
        setBaseAmountField(newBaseAmount.toFixed(2));
      }

      setConvertedAmountWithFees(newBaseAmount);
    }
  };

  const handleBaseAmountChange = (event) => {
    const value = event.target.value;
    setBaseAmountField(value);
    setIsBaseAmountManual(true);

    // Update converted amount display
    if (value && !isNaN(parseFloat(value))) {
      setConvertedAmountWithFees(parseFloat(value));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const currentPortfolio = portfolioData || portfolio;
      const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

      const transactionData = {
        portfolio: portfolioId,
        security: selectedSecurity.id,
        transaction_type: formData.transaction_type,
        transaction_date: formData.transaction_date,
        quantity: parseFloat(formData.quantity),
        price: parseFloat(formData.price),
        fees: parseFloat(formData.fees) || 0,
        notes: formData.notes || '',
        currency: formData.currency,

        // Include custom exchange rate and base amount if different currency
        ...(formData.currency !== portfolioCurrency && {
          exchange_rate: parseFloat(exchangeRateField),
          base_amount: parseFloat(baseAmountField)
        }),

        // Handle split ratio for SPLIT transactions
        ...(formData.transaction_type === 'SPLIT' && {
          split_ratio: formData.split_ratio
        }),

        // Handle dividend per share for DIVIDEND transactions
        ...(formData.transaction_type === 'DIVIDEND' && {
          dividend_per_share: parseFloat(formData.price)
        })
      };

      let response;
      if (transaction) {
        response = await api.transactions.update(transaction.id, transactionData);
      } else {
        response = await api.transactions.create(transactionData);
      }

      console.log('Transaction saved:', response.data);

      // Call the appropriate callback function
      if (onTransactionSaved) {
        onTransactionSaved();
      } else if (onSuccess) {
        onSuccess(); // Fallback to onSuccess if onTransactionSaved is not provided
      }

      onClose();

      // Reset form
      setFormData({
        transaction_type: 'BUY',
        quantity: '',
        price: '',
        currency: currentPortfolio?.base_currency || 'USD',
        transaction_date: new Date().toISOString().split('T')[0], // Reset to current date
        fees: '0',
        notes: '',
        split_ratio: ''
      });
      setSelectedSecurity(null);
      setExchangeRateField('');
      setBaseAmountField('');
      setIsExchangeRateManual(false);
      setIsBaseAmountManual(false);

    } catch (err) {
      console.error('Error saving transaction:', err);
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
              onChange={(value) => {
                // Allow currency changes for new transactions, but be careful with edited transactions
                if (!transaction || (transaction && window.confirm('Changing currency will reset exchange rate calculations. Continue?'))) {
                  setFormData({ ...formData, currency: value });
                  // Reset exchange rate fields when currency changes
                  setExchangeRateField('');
                  setBaseAmountField('');
                  setIsExchangeRateManual(false);
                  setIsBaseAmountManual(false);
                }
              }}
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

          {/* Exchange Rate Field - NEW (separate row) */}
          {formData.currency !== portfolioCurrency && (
            <TextField
              type="number"
              label={`Exchange Rate (1 ${formData.currency} = ? ${portfolioCurrency})`}
              value={exchangeRateField}
              onChange={handleExchangeRateChange}
              inputProps={{ step: "0.0001", min: "0" }}
              fullWidth
              sx={{ mb: 2 }}
              helperText={autoExchangeRate ? `Historical rate: ${autoExchangeRate.toFixed(4)}` : ''}
            />
          )}

          {/* Total Cost in Portfolio Currency Field - NEW (separate row) */}
          {formData.currency !== portfolioCurrency && formData.transaction_type !== 'SPLIT' && (
            <TextField
              type="number"
              label={`Total Cost (${portfolioCurrency})`}
              value={baseAmountField}
              onChange={handleBaseAmountChange}
              inputProps={{ step: "0.01", min: "0" }}
              fullWidth
              sx={{ mb: 2 }}
              helperText={autoBaseAmount ? `Auto calculated: ${formatCurrency(autoBaseAmount, portfolioCurrency)}` : ''}
            />
          )}

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