import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
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
import { Search as SearchIcon, AttachMoney as AttachMoneyIcon } from '@mui/icons-material';
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

  const [autoDepositInfo, setAutoDepositInfo] = useState(null);
  const [checkingAutoDeposit, setCheckingAutoDeposit] = useState(false);
  const [showAutoDepositConfirm, setShowAutoDepositConfirm] = useState(false);

  // Security search states
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchOptions, setSearchOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [portfolioHoldings, setPortfolioHoldings] = useState({});

  // Manual exchange rate and base amount states
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
  }, [portfolioId, transaction]);

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

  // Initialize form when dialog opens
  useEffect(() => {
    if (open) {
      // Use provided portfolio or fetch it
      if (portfolio) {
        setPortfolioData(portfolio);
      } else {
        fetchPortfolio();
      }

      // Only fetch holdings if not provided via props
      if (!existingHoldings) {
        fetchPortfolioHoldings();
      } else {
        setPortfolioHoldings(existingHoldings);
      }

      // Handle editing existing transaction
      if (transaction) {
        setFormData({
          transaction_type: transaction.transaction_type,
          quantity: transaction.quantity.toString(),
          price: transaction.price.toString(),
          currency: transaction.currency || transaction.security.currency,
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
  }, [open, transaction, security, portfolio, fetchPortfolio, fetchPortfolioHoldings, existingHoldings]);

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
      if (formData.transaction_type === 'BUY') {
        totalInTransactionCurrency = amount + fees;
      } else if (formData.transaction_type === 'SELL') {
        totalInTransactionCurrency = amount - fees;
      } else if (formData.transaction_type === 'DIVIDEND') {
        totalInTransactionCurrency = amount - fees;  // SUBTRACT fees for dividends
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
    open,
    fetchExchangeRate
  ]);

  const checkAutoDepositNeeded = useCallback(async () => {
    // Only check for BUY transactions with valid amounts
    if (formData.transaction_type !== 'BUY' || !formData.quantity || !formData.price || !selectedSecurity) {
      setAutoDepositInfo(null);
      return;
    }

    const quantity = parseFloat(formData.quantity || 0);
    const price = parseFloat(formData.price || 0);
    const fees = parseFloat(formData.fees || 0);

    if (quantity <= 0 || price <= 0) {
      setAutoDepositInfo(null);
      return;
    }

    // Calculate total cost in portfolio currency
    let totalCost = (quantity * price) + fees;

    // If transaction is in different currency, convert to portfolio currency
    if (convertedAmountWithFees !== null) {
      totalCost = convertedAmountWithFees;
    }

    try {
      setCheckingAutoDeposit(true);
      const response = await api.portfolios.checkAutoDeposit(portfolioId, {
        transaction_type: formData.transaction_type,
        total_cost: totalCost
      });

      setAutoDepositInfo(response.data);
    } catch (error) {
      console.error('Error checking auto-deposit:', error);
      setAutoDepositInfo(null);
    } finally {
      setCheckingAutoDeposit(false);
    }
  }, [
    formData.transaction_type,
    formData.quantity,
    formData.price,
    formData.fees,
    selectedSecurity,
    portfolioId,
    convertedAmountWithFees
  ]);

  // Add this function to handle auto-deposit confirmation
  const handleAutoDepositConfirm = () => {
    setShowAutoDepositConfirm(false);
    // Continue with transaction creation
    handleSubmit({ preventDefault: () => {} });
  };

  // Add this function to handle auto-deposit cancellation
  const handleAutoDepositCancel = () => {
    setShowAutoDepositConfirm(false);
  };

  // Add this component for the Transaction Summary with auto-deposit warning
  const TransactionSummaryWithAutoDeposit = () => {
    const currentPortfolio = portfolioData || portfolio;
    const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

    return (
      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          Transaction Summary
        </Typography>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography>Subtotal:</Typography>
          <Typography>
            <CurrencyDisplay
              amount={totalAmount}
              currency={formData.currency}
              showCode={true}
            />
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography>Fees:</Typography>
          <Typography>
            <CurrencyDisplay
              amount={formData.fees || 0}
              currency={formData.currency}
              showCode={true}
            />
          </Typography>
        </Box>

         <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography fontWeight="bold">Total:</Typography>
          <Typography fontWeight="bold">
            <CurrencyDisplay
              amount={totalWithFees}
              currency={formData.currency}
              showCode={true}
            />
          </Typography>
        </Box>

        {/* Auto-deposit warning */}
        {checkingAutoDeposit && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Box display="flex" alignItems="center" gap={1}>
              <CircularProgress size={16} />
              <Typography variant="body2">Checking cash balance...</Typography>
            </Box>
          </Alert>
        )}

        {autoDepositInfo && autoDepositInfo.auto_deposit_needed && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2" fontWeight="bold" gutterBottom>
              Auto-Deposit Required
            </Typography>
            <Typography variant="body2" gutterBottom>
              Current cash balance: <strong>{formatCurrency(autoDepositInfo.current_balance, autoDepositInfo.currency)}</strong>
            </Typography>
            <Typography variant="body2" gutterBottom>
              Transaction total: <strong>{formatCurrency(autoDepositInfo.total_cost, autoDepositInfo.currency)}</strong>
            </Typography>
            <Typography variant="body2" gutterBottom>
              Shortfall: <strong>{formatCurrency(autoDepositInfo.shortfall, autoDepositInfo.currency)}</strong>
            </Typography>
            <Typography variant="body2" color="warning.main" fontWeight="bold">
              An auto-deposit of <strong>{formatCurrency(autoDepositInfo.deposit_amount, autoDepositInfo.currency)}</strong> will be created to cover this transaction.
            </Typography>
          </Alert>
        )}

        {autoDepositInfo && autoDepositInfo.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="body2" fontWeight="bold" gutterBottom>
              Insufficient Cash Balance
            </Typography>
            <Typography variant="body2">
              {autoDepositInfo.message}
            </Typography>
          </Alert>
        )}

        {/* Exchange rate and converted amount display */}
        {formData.currency !== portfolioCurrency && formData.transaction_type !== 'SPLIT' && (
          <>
            <Divider sx={{ my: 2 }} />
            {exchangeRate && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Exchange Rate:
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  1 {formData.currency} = {exchangeRate.toFixed(4)} {portfolioCurrency}
                </Typography>
              </Box>
            )}
            {convertedAmountWithFees !== null && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" fontWeight="bold">
                  Total in {portfolioCurrency}:
                </Typography>
                <Typography variant="body2" fontWeight="bold" color="primary">
                  <CurrencyDisplay
                    amount={convertedAmountWithFees}
                    currency={portfolioCurrency}
                    showCode={true}
                  />
                </Typography>
              </Box>
            )}
          </>
        )}
      </Box>
    );
  };

  const AutoDepositConfirmDialog = () => {
    if (!autoDepositInfo || !autoDepositInfo.auto_deposit_needed) return null;

    return (
      <Dialog open={showAutoDepositConfirm} onClose={handleAutoDepositCancel} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <AttachMoneyIcon color="warning" />
            <Typography variant="h6">Auto-Deposit Required</Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" gutterBottom>
            Your current cash balance is insufficient for this transaction. An automatic deposit will be created.
          </Typography>

          <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="body2" gutterBottom>
              <strong>Current Balance:</strong> {formatCurrency(autoDepositInfo.current_balance, autoDepositInfo.currency)}
            </Typography>
            <Typography variant="body2" gutterBottom>
              <strong>Transaction Total:</strong> {formatCurrency(autoDepositInfo.total_cost, autoDepositInfo.currency)}
            </Typography>
            <Typography variant="body2" gutterBottom>
              <strong>Shortfall:</strong> {formatCurrency(autoDepositInfo.shortfall, autoDepositInfo.currency)}
            </Typography>
            <Typography variant="body2" color="warning.main" fontWeight="bold">
              <strong>Auto-Deposit Amount:</strong> {formatCurrency(autoDepositInfo.deposit_amount, autoDepositInfo.currency)}
            </Typography>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Mode: {autoDepositInfo.auto_deposit_mode === 'EXACT' ? 'Deposit exact amount needed' : 'Deposit only shortfall'}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleAutoDepositCancel}>Cancel</Button>
          <Button onClick={handleAutoDepositConfirm} variant="contained" color="warning">
            Create Auto-Deposit & Transaction
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  // Add this useEffect to trigger auto-deposit check when values change
  useEffect(() => {
    // Debounce the check to avoid too many API calls
    const timeoutId = setTimeout(() => {
      checkAutoDepositNeeded();
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [checkAutoDepositNeeded]);

  const handleExchangeRateChange = (event) => {
    const value = event.target.value;
    setExchangeRateField(value);
    setIsExchangeRateManual(true);

    // Recalculate base amount when exchange rate changes
    if (value && !isNaN(parseFloat(value))) {
      const quantity = parseFloat(formData.quantity || 0);
      const price = parseFloat(formData.price || 0);
      const fees = parseFloat(formData.fees || 0);

      let totalInTransactionCurrency;
      if (formData.transaction_type === 'BUY') {
        totalInTransactionCurrency = (quantity * price) + fees;
      } else if (formData.transaction_type === 'SELL') {
        totalInTransactionCurrency = (quantity * price) - fees;
      } else if (formData.transaction_type === 'DIVIDEND') {
        totalInTransactionCurrency = price - fees;  // For dividends, price is total amount, subtract fees
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

  // Auto-calculate additional shares when split ratio changes
  useEffect(() => {
    if (formData.transaction_type === 'SPLIT' && formData.split_ratio && selectedSecurity) {
      try {
        // Parse the split ratio (e.g., "2:1" means 2 new shares for every 1 old share)
        const [newShares, oldShares] = formData.split_ratio.split(':').map(Number);

        if (!isNaN(newShares) && !isNaN(oldShares) && oldShares > 0) {
          // Get current holdings for this security
          const currentHolding = portfolioHoldings[selectedSecurity.symbol] || 0;

          if (currentHolding > 0) {
            // Calculate total shares after split
            const totalSharesAfterSplit = (currentHolding * newShares) / oldShares;
            // Additional shares = total after split - current holdings
            const additionalShares = totalSharesAfterSplit - currentHolding;

            // Only update if the calculated value is different from current value
            // This prevents overwriting manual edits unless the ratio changes
            if (additionalShares >= 0 && additionalShares !== parseFloat(formData.quantity)) {
              setFormData(prev => ({
                ...prev,
                quantity: additionalShares.toFixed(8) // Use 8 decimal places for precision
              }));
            }
          }
        }
      } catch (error) {
        console.error('Error calculating split shares:', error);
      }
    }
  }, [formData.split_ratio, formData.transaction_type, selectedSecurity, portfolioHoldings]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // If auto-deposit is needed, show confirmation dialog first
    if (autoDepositInfo && autoDepositInfo.auto_deposit_needed && !showAutoDepositConfirm) {
      setShowAutoDepositConfirm(true);
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Build the transaction data
      const transactionData = {
        portfolio: portfolioId,
        security: selectedSecurity.id,
        transaction_type: formData.transaction_type,
        quantity: parseFloat(formData.quantity),
        price: parseFloat(formData.price),
        fees: parseFloat(formData.fees || 0),
        transaction_date: formData.transaction_date,
        notes: formData.notes,
        currency: formData.currency,

        // Include custom exchange rate and base amount if provided
        ...(isExchangeRateManual && exchangeRateField && {
          exchange_rate: parseFloat(exchangeRateField)
        }),

        // Include manual base amount if provided (regardless of exchange rate)
        ...(isBaseAmountManual && baseAmountField && {
          base_amount: parseFloat(baseAmountField)
        }),

        // Handle split ratio for SPLIT transactions
        ...(formData.transaction_type === 'SPLIT' && {
          split_ratio: formData.split_ratio
        }),

        // Handle dividend per share for DIVIDEND transactions
        ...(formData.transaction_type === 'DIVIDEND' && {
          // Calculate and round to 4 decimal places to match backend model
          dividend_per_share: Math.round((parseFloat(formData.price) / parseFloat(formData.quantity)) * 10000) / 10000
        })
      };

      // Log the data being sent for debugging
      console.log('Sending transaction data:', transactionData);

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

      // Enhanced error handling for better debugging
      if (err.response?.data) {
        console.error('Error response data:', err.response.data);

        // Handle specific field errors
        if (err.response.data.dividend_per_share) {
          setError(`Dividend per share error: ${err.response.data.dividend_per_share}`);
        } else if (err.response.data.detail) {
          setError(err.response.data.detail);
        } else if (err.response.data.error) {
          setError(err.response.data.error);
        } else {
          // Try to extract any field-specific errors
          const fieldErrors = Object.entries(err.response.data)
            .filter(([key, value]) => typeof value === 'string' || Array.isArray(value))
            .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
            .join('; ');

          setError(fieldErrors || 'Failed to save transaction');
        }
      } else {
        setError('Failed to save transaction. Please check your input.');
      }
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
    ? totalAmount - parseFloat(formData.fees || 0)
    : formData.transaction_type === 'SPLIT'
    ? 0
    : formData.transaction_type === 'BUY'
      ? totalAmount + parseFloat(formData.fees || 0)
      : totalAmount - parseFloat(formData.fees || 0);

  const currentPortfolio = portfolioData || portfolio;
  const portfolioCurrency = currentPortfolio?.base_currency || currentPortfolio?.currency || 'USD';

  const dividendPerShare = formData.transaction_type === 'DIVIDEND' && formData.price && formData.quantity
    ? Math.round((parseFloat(formData.price) / parseFloat(formData.quantity)) * 10000) / 10000
    : null;

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
                    // Check if we have holdings for this security
                    const holdingQuantity = portfolioHoldings[newValue.symbol] || 0;

                    setFormData(prev => ({
                      ...prev,
                      price: newValue.current_price?.toString() || '',
                      currency: newValue.currency || 'USD', // Auto-set currency
                      // Auto-fill quantity for dividends
                      quantity: prev.transaction_type === 'DIVIDEND' && holdingQuantity > 0
                        ? holdingQuantity.toString()
                        : prev.quantity,
                    }));
                  }
                }}
                options={searchOptions}
                getOptionLabel={(option) => `${option.symbol} - ${option.name}`}
                renderOption={(props, option) => (
                  <Box component="li" {...props}>
                    <Box>
                      <Typography variant="body2" fontWeight="bold">{option.symbol}</Typography>
                      <Typography variant="caption" color="text.secondary">{option.name}</Typography>
                      <Typography variant="caption" display="block" color="text.secondary">
                        {option.current_price ? `Price: ${formatCurrency(option.current_price, option.currency)}` : 'No price data'}
                      </Typography>
                    </Box>
                  </Box>
                )}
                loading={searchLoading}
                onInputChange={(event, value) => setSearchInput(value)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    placeholder="Search by symbol or name (e.g., AAPL, Apple)"
                    InputProps={{
                      ...params.InputProps,
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon />
                        </InputAdornment>
                      ),
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
                  <Box sx={{ p: 2 }}>
                    {searchInput.length >= 2 ? (
                      <Typography variant="body2" gutterBottom>
                        No results found for "{searchInput}". Contact administrator to add new securities.
                      </Typography>
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
                      : prev.quantity,
                    // Clear price for splits as they don't have monetary value
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
            {formData.transaction_type === 'SPLIT' && (
              <TextField
                type="text"
                label="Split Ratio (e.g., 2:1)"
                value={formData.split_ratio || ''}
                onChange={(e) => {
                  const value = e.target.value;
                  // Allow only numbers, colons, and spaces
                  if (/^[\d\s:]*$/.test(value)) {
                    setFormData({ ...formData, split_ratio: value.replace(/\s/g, '') });
                  }
                }}
                fullWidth
                required
                helperText={
                  selectedSecurity && portfolioHoldings[selectedSecurity.symbol]
                    ? `Format: new:old (e.g., 2:1). You currently own ${portfolioHoldings[selectedSecurity.symbol]} shares.`
                    : "Format: new:old (e.g., 2:1 means each share becomes 2 shares)"
                }
                placeholder="2:1"
                error={formData.split_ratio && !/^\d+:\d+$/.test(formData.split_ratio)}
              />
            )}

            <TextField
              type="number"
              label={
                formData.transaction_type === 'DIVIDEND' ? 'Number of Shares' :
                formData.transaction_type === 'SPLIT' ? 'Additional Shares Received' :
                'Quantity'
              }
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
              inputProps={{ step: "0.00000001", min: "0" }}
              fullWidth
              required
              helperText={
                formData.transaction_type === 'DIVIDEND' && selectedSecurity && portfolioHoldings[selectedSecurity.symbol]
                  ? `You currently own ${portfolioHoldings[selectedSecurity.symbol]} shares`
                  : formData.transaction_type === 'SPLIT' && selectedSecurity && portfolioHoldings[selectedSecurity.symbol]
                  ? formData.split_ratio && /^\d+:\d+$/.test(formData.split_ratio)
                    ? '✓ Auto-calculated from split ratio. You can edit if needed.'
                    : `You currently own ${portfolioHoldings[selectedSecurity.symbol]} shares. Enter split ratio above to auto-calculate.`
                  : ''
              }
              // Add visual indicator that it's auto-calculated
              InputProps={formData.transaction_type === 'SPLIT' && formData.split_ratio ? {
                startAdornment: (
                  <InputAdornment position="start">
                    <Tooltip title="Auto-calculated from split ratio. You can still edit this value.">
                      <InfoIcon color="action" fontSize="small" />
                    </Tooltip>
                  </InputAdornment>
                ),
              } : undefined}
            />

            {formData.transaction_type !== 'SPLIT' && (
              <TextField
                type="number"
                label={`${formData.transaction_type === 'DIVIDEND' ? 'Total Dividend Amount' : 'Price per Unit'} (${formData.currency})`}
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                inputProps={{ step: "0.00000001", min: "0" }}
                fullWidth
                required
                helperText={
                  formData.transaction_type === 'DIVIDEND'
                    ? formData.quantity && formData.price
                      ? `Dividend per share: ${formatCurrency(dividendPerShare, formData.currency)}`
                      : 'Enter the total dividend amount received'
                    : formData.transaction_type === 'SPLIT'
                    ? 'Stock splits have no monetary value'
                    : `Enter price in ${formData.currency}`
                }
              />
            )}
          </Box>

          {/* Currency and Fees */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
            <CurrencySelector
              value={formData.currency}
              onChange={(currency) => setFormData({ ...formData, currency })}
              label="Transaction Currency"
              required
            />

            <TextField
              type="number"
              label={`Fees (${formData.currency})`}
              value={formData.fees}
              onChange={(e) => setFormData({ ...formData, fees: e.target.value })}
              inputProps={{ step: "0.01", min: "0" }}
              fullWidth
              helperText={`Enter fees in ${formData.currency}`}
            />
          </Box>

          {/* Manual Exchange Rate and Base Amount Override */}
          {formData.currency !== portfolioCurrency && formData.transaction_type !== 'SPLIT' && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Currency Conversion Override (Optional)
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                <TextField
                  type="number"
                  label={`Exchange Rate (1 ${formData.currency} = ? ${portfolioCurrency})`}
                  value={exchangeRateField}
                  onChange={handleExchangeRateChange}
                  inputProps={{ step: "0.00000001", min: "0" }}
                  fullWidth
                  helperText={
                    autoExchangeRate
                      ? `Historical rate: ${autoExchangeRate.toFixed(4)}`
                      : 'Leave blank to use historical rate'
                  }
                />

                <TextField
                  type="number"
                  label={`Total Cost (${portfolioCurrency})`}
                  value={baseAmountField}
                  onChange={handleBaseAmountChange}
                  inputProps={{ step: "0.01", min: "0" }}
                  fullWidth
                  helperText={
                    autoBaseAmount
                      ? `Auto calculated: ${autoBaseAmount.toFixed(2)}`
                      : 'Leave blank to use exchange rate calculation'
                  }
                />
              </Box>
            </Box>
          )}

          {/* Notes */}
          <TextField
            label="Notes"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            multiline
            rows={2}
            fullWidth
            sx={{ mb: 2 }}
          />

          {/* NEW: Transaction Summary with Auto-Deposit Warning */}
          <TransactionSummaryWithAutoDeposit />
        </DialogContent>

        {/* Add the Auto-Deposit Confirmation Dialog */}
        <AutoDepositConfirmDialog />

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