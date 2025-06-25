// frontend/src/components/TransactionForm.js

import React, { useState, useEffect } from 'react';
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
  Chip,
  CircularProgress,
  InputAdornment
} from '@mui/material';
import { api } from '../services/api';
import StockAutocomplete from './StockAutocomplete';

const TransactionForm = ({ open, onClose, portfolioId, security, onSuccess }) => {
  const [formData, setFormData] = useState({
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    fees: '0',
    transaction_date: new Date().toISOString().split('T')[0],
    notes: ''
  });

  const [selectedSecurity, setSelectedSecurity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cashInfo, setCashInfo] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [validationMessage, setValidationMessage] = useState('');
  const [portfolioHoldings, setPortfolioHoldings] = useState([]); // Add this

  useEffect(() => {
    if (security) {
      setSelectedSecurity(security);
      setFormData(prev => ({
        ...prev,
        price: security.current_price ? security.current_price.toString() : '',
        // Auto-fill quantity for dividends if security has total_quantity
        quantity: prev.transaction_type === 'DIVIDEND' && security.total_quantity
          ? security.total_quantity.toString()
          : prev.quantity
      }));
    }
  }, [security]);

  useEffect(() => {
    if (open && portfolioId) {
      fetchPortfolioCash();
      fetchUserPreferences();
      fetchPortfolioHoldings(); // Add this
    }
  }, [open, portfolioId]);

  useEffect(() => {
    validateTransaction();
  }, [formData.quantity, formData.price, formData.fees, formData.transaction_type]);

  const fetchPortfolioHoldings = async () => {
    try {
      const response = await api.portfolios.getConsolidatedView(portfolioId);
      setPortfolioHoldings(response.data.consolidated_assets || []);
    } catch (err) {
      console.error('Error fetching portfolio holdings:', err);
    }
  };

  const fetchPortfolioCash = async () => {
    try {
      const response = await api.portfolios.get(portfolioId);
      setCashInfo({
        balance: response.data.cash_balance || 0,
        currency: response.data.currency || 'USD'
      });
    } catch (err) {
      console.error('Error fetching cash info:', err);
    }
  };

  const fetchUserPreferences = async () => {
    try {
      const response = await api.preferences.get();
      if (response.data.results && response.data.results.length > 0) {
        setPreferences(response.data.results[0]);
      }
    } catch (err) {
      console.error('Error fetching preferences:', err);
    }
  };

  const validateTransaction = () => {
    if (formData.transaction_type !== 'BUY' || !cashInfo) {
      setValidationMessage('');
      return;
    }

    const quantity = parseFloat(formData.quantity) || 0;
    const price = parseFloat(formData.price) || 0;
    const fees = parseFloat(formData.fees) || 0;
    const totalCost = (quantity * price) + fees;

    if (totalCost > 0 && totalCost > cashInfo.balance) {
      const shortfall = totalCost - cashInfo.balance;

      if (preferences?.auto_deposit_enabled) {
        const depositAmount = preferences.auto_deposit_mode === 'EXACT' ? totalCost : shortfall;
        setValidationMessage(
          `Insufficient cash. An auto-deposit of ${formatCurrency(depositAmount)} will be created.`
        );
      } else {
        setValidationMessage(
          `Insufficient cash. You need ${formatCurrency(shortfall)} more. Current balance: ${formatCurrency(cashInfo.balance)}`
        );
      }
    } else {
      setValidationMessage('');
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: cashInfo?.currency || 'USD'
    }).format(amount);
  };

  const handleChange = (field) => (event) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  const handleSecuritySelect = (security) => {
    // Find if we already own this security in our portfolio
    const existingHolding = portfolioHoldings.find(
      holding => holding.symbol === security.symbol
    );

    const securityWithQuantity = {
      ...security,
      total_quantity: existingHolding ? existingHolding.total_quantity : 0
    };

    setSelectedSecurity(securityWithQuantity);
    setFormData(prev => ({
      ...prev,
      price: security.current_price ? security.current_price.toString() : prev.price,
      // Auto-fill quantity for dividends
      quantity: prev.transaction_type === 'DIVIDEND' && existingHolding
        ? existingHolding.total_quantity.toString()
        : prev.quantity
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedSecurity) {
      setError('Please select a security');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const data = {
        portfolio: portfolioId,
        security: selectedSecurity.id,
        ...formData,
        quantity: parseFloat(formData.quantity),
        price: parseFloat(formData.price),
        fees: parseFloat(formData.fees) || 0
      };

      // For dividends, calculate and set dividend_per_share
      if (formData.transaction_type === 'DIVIDEND') {
        const totalDividend = parseFloat(formData.price);
        const quantity = parseFloat(formData.quantity);

        if (quantity > 0) {
          data.dividend_per_share = totalDividend / quantity;
          data.price = data.dividend_per_share;
        }
      }

      await api.transactions.create(data);

      if (onSuccess) {
        onSuccess();
      }

      handleClose();
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to create transaction');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFormData({
      transaction_type: 'BUY',
      quantity: '',
      price: '',
      fees: '0',
      transaction_date: new Date().toISOString().split('T')[0],
      notes: ''
    });
    setSelectedSecurity(null);
    setError('');
    setValidationMessage('');
    onClose();
  };

  const getTotalAmount = () => {
    const quantity = parseFloat(formData.quantity) || 0;
    const price = parseFloat(formData.price) || 0;
    const fees = parseFloat(formData.fees) || 0;

    if (formData.transaction_type === 'BUY') {
      return (quantity * price) + fees;
    } else if (formData.transaction_type === 'SELL') {
      return (quantity * price) - fees;
    } else if (formData.transaction_type === 'DIVIDEND') {
      return price; // For dividends, price is the total amount
    }
    return 0;
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          Add Transaction
          {selectedSecurity && (
            <Typography variant="subtitle2" color="textSecondary">
              {selectedSecurity.symbol} - {selectedSecurity.name}
            </Typography>
          )}
        </DialogTitle>

        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {cashInfo && (
            <Box mb={2} p={2} bgcolor="grey.100" borderRadius={1}>
              <Typography variant="body2" color="textSecondary">
                Current Cash Balance: <strong>{formatCurrency(cashInfo.balance)}</strong>
              </Typography>
            </Box>
          )}

          {/* Security Selection - only show if not pre-selected */}
          {!security && (
            <Box mb={2}>
              <StockAutocomplete
                onSelectStock={(selectedStock) => {
                  // Try to find if we already have this security in our portfolio
                  // This would need to be passed from parent or fetched
                  const stockWithQuantity = {
                    ...selectedStock,
                    total_quantity: selectedStock.total_quantity || 0
                  };
                  handleSecuritySelect(stockWithQuantity);
                }}
                label="Select Security"
                required
              />
            </Box>
          )}

          {/* Show selected security */}
          {selectedSecurity && (
            <Box mb={2} p={2} bgcolor="primary.light" borderRadius={1}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="body1" fontWeight="medium">
                    {selectedSecurity.symbol} - {selectedSecurity.name}
                  </Typography>
                  <Typography variant="body2">
                    Current Price: {formatCurrency(selectedSecurity.current_price || 0)}
                  </Typography>
                  {selectedSecurity.total_quantity !== undefined && (
                    <Typography variant="body2">
                      Current Holdings: {selectedSecurity.total_quantity} shares
                    </Typography>
                  )}
                </Box>
                {!security && (
                  <Button
                    size="small"
                    onClick={() => {
                      setSelectedSecurity(null);
                      setFormData(prev => ({ ...prev, price: '' }));
                    }}
                  >
                    Change
                  </Button>
                )}
              </Box>
            </Box>
          )}

          <FormControl fullWidth margin="dense" sx={{ mb: 2 }}>
            <InputLabel>Transaction Type</InputLabel>
            <Select
              value={formData.transaction_type}
              onChange={(e) => {
                const newType = e.target.value;
                handleChange('transaction_type')(e);
                // Auto-fill quantity when switching to DIVIDEND
                if (newType === 'DIVIDEND' && selectedSecurity) {
                  // Find if we own this security
                  const existingHolding = portfolioHoldings.find(
                    holding => holding.symbol === selectedSecurity.symbol
                  );
                  if (existingHolding) {
                    setFormData(prev => ({
                      ...prev,
                      quantity: existingHolding.total_quantity.toString()
                    }));
                  }
                }
              }}
              label="Transaction Type"
            >
              <MenuItem value="BUY">Buy</MenuItem>
              <MenuItem value="SELL">Sell</MenuItem>
              <MenuItem value="DIVIDEND">Dividend</MenuItem>
            </Select>
          </FormControl>

          <TextField
            margin="dense"
            label={formData.transaction_type === 'DIVIDEND' ? 'Number of Shares' : 'Quantity'}
            type="number"
            fullWidth
            required
            value={formData.quantity}
            onChange={handleChange('quantity')}
            inputProps={{ step: "0.0001" }}
            helperText={
              formData.transaction_type === 'DIVIDEND'
                ? (() => {
                    const existingHolding = portfolioHoldings.find(
                      holding => selectedSecurity && holding.symbol === selectedSecurity.symbol
                    );
                    return existingHolding && existingHolding.total_quantity > 0
                      ? `You currently own ${existingHolding.total_quantity} shares`
                      : 'Number of shares for dividend calculation';
                  })()
                : ''
            }
            sx={{ mb: 2 }}
          />

          <TextField
            margin="dense"
            label={formData.transaction_type === 'DIVIDEND' ? 'Total Dividend Amount' : 'Price per Share'}
            type="number"
            fullWidth
            required
            value={formData.price}
            onChange={handleChange('price')}
            inputProps={{ step: "0.01" }}
            InputProps={{
              startAdornment: <InputAdornment position="start">$</InputAdornment>
            }}
            helperText={
              formData.transaction_type === 'DIVIDEND' && formData.quantity && formData.price
                ? `Dividend per share: ${formatCurrency(parseFloat(formData.price) / parseFloat(formData.quantity) || 0)}`
                : ''
            }
            sx={{ mb: 2 }}
          />

          {formData.transaction_type !== 'DIVIDEND' && (
            <TextField
              margin="dense"
              label="Fees"
              type="number"
              fullWidth
              value={formData.fees}
              onChange={handleChange('fees')}
              inputProps={{ step: "0.01" }}
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>
              }}
              sx={{ mb: 2 }}
            />
          )}

          <TextField
            margin="dense"
            label="Date"
            type="date"
            fullWidth
            required
            value={formData.transaction_date}
            onChange={handleChange('transaction_date')}
            InputLabelProps={{ shrink: true }}
            sx={{ mb: 2 }}
          />

          <TextField
            margin="dense"
            label="Notes (Optional)"
            fullWidth
            multiline
            rows={2}
            value={formData.notes}
            onChange={handleChange('notes')}
            sx={{ mb: 2 }}
          />

          {validationMessage && (
            <Alert
              severity={preferences?.auto_deposit_enabled ? "info" : "warning"}
              sx={{ mb: 2 }}
            >
              {validationMessage}
            </Alert>
          )}

          {getTotalAmount() > 0 && (
            <Box p={2} bgcolor="primary.main" color="primary.contrastText" borderRadius={1}>
              <Typography variant="body1" fontWeight="bold">
                Total {formData.transaction_type === 'BUY' ? 'Cost' : formData.transaction_type === 'SELL' ? 'Proceeds' : 'Dividend'}:
                {' '}{formatCurrency(getTotalAmount())}
              </Typography>
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading || !selectedSecurity || !formData.quantity || !formData.price}
          >
            {loading ? <CircularProgress size={24} /> : 'Add Transaction'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default TransactionForm;