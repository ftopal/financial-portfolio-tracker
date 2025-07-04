import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Box,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  CircularProgress,
  InputAdornment,
  Tooltip,
  Stack
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  History as HistoryIcon,
  TrendingUp,
  TrendingDown,
  AttachMoney,
  Delete as DeleteIcon,
  CurrencyExchange as CurrencyExchangeIcon
} from '@mui/icons-material';
import api from '../services/api';
import { extractDataArray } from '../utils/apiHelpers';

const CashManagement = ({ portfolioId, cashBalance = 0, currency = 'USD', onBalanceUpdate, portfolio = null }) => {
  const [open, setOpen] = useState(false);
  const [transactionType, setTransactionType] = useState('DEPOSIT');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tabValue, setTabValue] = useState(0);
  const [cashHistory, setCashHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [transactionToDelete, setTransactionToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);

  // Get the portfolio currency from portfolio prop or use the currency prop
  const portfolioCurrency = portfolio?.base_currency || currency || 'USD';

  useEffect(() => {
    if (tabValue === 1) {
      fetchCashHistory();
    }
  }, [tabValue, portfolioId]);

  const fetchCashHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await api.portfolios.getCashHistory(portfolioId);
      // Use the helper to extract data array
      const cashHistoryData = extractDataArray(response);
      setCashHistory(cashHistoryData);
    } catch (err) {
      console.error('Error fetching cash history:', err);
      setCashHistory([]); // Set empty array on error
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleOpen = (type) => {
    setTransactionType(type);
    setOpen(true);
    setError('');
    setSuccess('');
    setAmount('');
    setDescription('');
    setTransactionDate(new Date().toISOString().split('T')[0]); // Reset to today
  };

  const handleClose = () => {
    setOpen(false);
    setError('');
    setSuccess('');
  };

  const handleDeleteClick = (transaction) => {
    setTransactionToDelete(transaction);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!transactionToDelete) return;

    setDeleting(true);
    try {
      const response = await api.cash.delete(transactionToDelete.id);

      if (response.data && response.data.new_balance !== undefined) {
        setSuccess(`Transaction deleted successfully. New balance: ${formatCurrency(response.data.new_balance)}`);
      } else {
        setSuccess(`Transaction deleted successfully`);
      }

      // Refresh data
      if (onBalanceUpdate) {
        onBalanceUpdate();
      }
      fetchCashHistory();

      setDeleteConfirmOpen(false);
      setTransactionToDelete(null);
    } catch (err) {
      console.error('Delete error:', err);
      const errorMessage = err.response?.data?.error || err.response?.data?.message || 'Failed to delete transaction';
      setError(errorMessage);
    } finally {
      setDeleting(false);
    }
  };

  const handleRecalculateBalance = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await api.portfolios.recalculateBalance(portfolioId);

      if (response.data) {
        const { old_balance, new_balance, difference } = response.data;

        if (Math.abs(difference) < 0.01) {
          setSuccess('Balance verification passed - no adjustment needed');
        } else {
          setSuccess(`Balance recalculated: ${formatCurrency(old_balance)} → ${formatCurrency(new_balance)}`);
        }

        if (onBalanceUpdate) {
          onBalanceUpdate();
        }
        fetchCashHistory();
      }
    } catch (err) {
      setError('Failed to recalculate balance: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyBalance = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await api.portfolios.verifyBalance(portfolioId);

      if (response.data) {
        const { is_consistent, stored_balance, calculated_balance, difference } = response.data;

        if (is_consistent) {
          setSuccess(`✅ Balance is consistent: ${formatCurrency(stored_balance)}`);
        } else {
          setError(`❌ Balance inconsistency detected! Difference: ${formatCurrency(difference)}`);
        }
      }
    } catch (err) {
      setError('Failed to verify balance: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
    setTransactionToDelete(null);
  };

  const handleSubmit = async () => {
    setError('');
    setSuccess('');
    setLoading(true);

    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      setError('Please enter a valid amount');
      setLoading(false);
      return;
    }

    try {
      const endpoint = transactionType === 'DEPOSIT'
        ? api.portfolios.depositCash
        : api.portfolios.withdrawCash;

      await endpoint(portfolioId, {
        amount: numAmount,
        description: description || `Cash ${transactionType.toLowerCase()}`,
        transaction_date: transactionDate,
        currency: portfolioCurrency // Pass the portfolio currency
      });

      setSuccess(`Successfully ${transactionType === 'DEPOSIT' ? 'deposited' : 'withdrew'} ${formatCurrency(numAmount)}`);

      // Reset form
      setAmount('');
      setDescription('');
      setTransactionDate(new Date().toISOString().split('T')[0]);

      // Refresh data
      if (onBalanceUpdate) {
        onBalanceUpdate();
      }

      if (tabValue === 1) {
        fetchCashHistory();
      }

      // Close dialog after delay
      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.error || 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount, currencyCode = null) => {
    const displayCurrency = currencyCode || portfolioCurrency;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: displayCurrency
    }).format(amount);
  };

  const getTransactionTypeChip = (type) => {
    const config = {
      'DEPOSIT': { color: 'success', icon: <AddIcon fontSize="small" /> },
      'WITHDRAWAL': { color: 'error', icon: <RemoveIcon fontSize="small" /> },
      'BUY': { color: 'primary', icon: <TrendingDown fontSize="small" /> },
      'SELL': { color: 'secondary', icon: <TrendingUp fontSize="small" /> },
      'DIVIDEND': { color: 'info', icon: <AttachMoney fontSize="small" /> },
      'FEE': { color: 'warning', icon: <RemoveIcon fontSize="small" /> },
      'CURRENCY_CONVERSION': { color: 'default', icon: <CurrencyExchangeIcon fontSize="small" /> },
    };

    const { color, icon } = config[type] || { color: 'default', icon: null };

    return (
      <Chip
        label={type.replace('_', ' ')}
        color={color}
        size="small"
        icon={icon}
      />
    );
  };

  const canDeleteTransaction = (transaction) => {
    // Don't allow deletion of auto-generated transactions (like from stock trades)
    return transaction.transaction_type === 'DEPOSIT' || transaction.transaction_type === 'WITHDRAWAL';
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Stack direction="row" alignItems="center" spacing={2}>
            <AccountBalanceIcon color="primary" />
            <Box>
              <Typography variant="h6">Cash Account</Typography>
              <Typography variant="caption" color="text.secondary">
                Portfolio Currency: {portfolioCurrency}
              </Typography>
            </Box>
          </Stack>
          <Typography variant="h5" fontWeight="bold" color="primary">
            {formatCurrency(cashBalance)}
          </Typography>
        </Stack>

        <Box display="flex" gap={2} mb={3}>
          <Button
            variant="contained"
            color="success"
            startIcon={<AddIcon />}
            onClick={() => handleOpen('DEPOSIT')}
            size="small"
          >
            Deposit
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<RemoveIcon />}
            onClick={() => handleOpen('WITHDRAWAL')}
            size="small"
          >
            Withdraw
          </Button>
        </Box>

        {/* Success/Error Messages */}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

        {/* Tabs for Overview/History */}
        <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)}>
          <Tab label="Overview" />
          <Tab label="History" icon={<HistoryIcon fontSize="small" />} iconPosition="end" />
        </Tabs>

        {/* Tab Content */}
        {tabValue === 0 && (
          <Box py={2}>
            <Typography variant="body2" color="textSecondary">
              Manage your portfolio's cash balance. Deposit funds to buy securities or withdraw excess cash.
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              All transactions are recorded in {portfolioCurrency}.
            </Typography>
          </Box>
        )}

        {tabValue === 1 && (
          <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
            <Box sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom>Balance Management</Typography>
              <Stack direction="row" spacing={2}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={handleVerifyBalance}
                  disabled={loading}
                  startIcon={<AccountBalanceIcon />}
                >
                  Verify Balance
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={handleRecalculateBalance}
                  disabled={loading}
                  startIcon={<AccountBalanceIcon />}
                  color="warning"
                >
                  Recalculate Balance
                </Button>
              </Stack>
            </Box>
            {historyLoading ? (
              <Box display="flex" justifyContent="center" p={3}>
                <CircularProgress />
              </Box>
            ) : cashHistory.length === 0 ? (
              <Box p={3} textAlign="center">
                <Typography color="textSecondary">No cash transactions yet</Typography>
              </Box>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell align="right">Amount ({portfolioCurrency})</TableCell>
                    <TableCell align="right">Balance After ({portfolioCurrency})</TableCell>
                    <TableCell align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {cashHistory.map((transaction) => (
                    <TableRow key={transaction.id}>
                      <TableCell>
                        {new Date(transaction.transaction_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell>{getTransactionTypeChip(transaction.transaction_type)}</TableCell>
                      <TableCell>
                        <Typography variant="body2">{transaction.description}</Typography>
                        {transaction.is_auto_deposit && (
                          <Chip label="Auto-deposit" size="small" color="info" sx={{ ml: 1 }} />
                        )}
                        {transaction.related_transaction && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Related: {transaction.related_transaction.symbol || 'Security Transaction'}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          color={transaction.amount > 0 ? 'success.main' : 'error.main'}
                          fontWeight="medium"
                        >
                          {transaction.amount > 0 ? '+' : ''}{formatCurrency(Math.abs(transaction.amount))}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{formatCurrency(transaction.balance_after)}</TableCell>
                      <TableCell align="center">
                        {canDeleteTransaction(transaction) ? (
                          <Tooltip title="Delete transaction">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDeleteClick(transaction)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : (
                          <Tooltip title="Cannot delete auto-generated transactions">
                            <span>
                              <IconButton size="small" disabled>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TableContainer>
        )}

        {/* Transaction Dialog */}
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
          <DialogTitle>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">
                {transactionType === 'DEPOSIT' ? 'Deposit Cash' : 'Withdraw Cash'}
              </Typography>
              <Chip
                label={portfolioCurrency}
                size="small"
                color="primary"
                variant="outlined"
              />
            </Stack>
          </DialogTitle>
          <DialogContent>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

            <TextField
              autoFocus
              margin="dense"
              label={`Amount (${portfolioCurrency})`}
              type="number"
              fullWidth
              variant="outlined"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Typography color="textSecondary">
                      {portfolioCurrency}
                    </Typography>
                  </InputAdornment>
                )
              }}
              helperText={`Enter amount in ${portfolioCurrency}`}
              sx={{ mb: 2 }}
            />

            <TextField
              margin="dense"
              label="Description (Optional)"
              type="text"
              fullWidth
              variant="outlined"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={`Reason for ${transactionType.toLowerCase()}`}
            />

            <TextField
              margin="dense"
              label="Transaction Date"
              type="date"
              fullWidth
              variant="outlined"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              InputLabelProps={{
                shrink: true,
              }}
              inputProps={{
                max: new Date().toISOString().split('T')[0], // Don't allow future dates
              }}
              sx={{ mt: 2 }}
            />

            {transactionType === 'WITHDRAWAL' && cashBalance < parseFloat(amount || 0) && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Insufficient cash balance. Current balance: {formatCurrency(cashBalance)}
              </Alert>
            )}

            {/* Transaction Summary */}
            {amount && parseFloat(amount) > 0 && (
              <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Transaction Summary
                </Typography>
                <Stack direction="row" justifyContent="space-between" mb={1}>
                  <Typography variant="body2">Amount:</Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {formatCurrency(parseFloat(amount))}
                  </Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2">New Balance:</Typography>
                  <Typography variant="body2" fontWeight="bold" color={transactionType === 'DEPOSIT' ? 'success.main' : 'error.main'}>
                    {formatCurrency(
                      transactionType === 'DEPOSIT'
                        ? cashBalance + parseFloat(amount)
                        : cashBalance - parseFloat(amount)
                    )}
                  </Typography>
                </Stack>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose} disabled={loading}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              variant="contained"
              color={transactionType === 'DEPOSIT' ? 'success' : 'error'}
              disabled={loading || !amount || parseFloat(amount) <= 0}
              startIcon={transactionType === 'DEPOSIT' ? <AddIcon /> : <RemoveIcon />}
            >
              {loading ? <CircularProgress size={24} /> : transactionType}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteConfirmOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Delete Transaction</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete this transaction?
            </Typography>
            {transactionToDelete && (
              <Box mt={2} p={2} bgcolor="grey.100" borderRadius={1}>
                <Typography variant="body2">
                  <strong>Date:</strong> {new Date(transactionToDelete.transaction_date).toLocaleDateString()}
                </Typography>
                <Typography variant="body2">
                  <strong>Type:</strong> {transactionToDelete.transaction_type}
                </Typography>
                <Typography variant="body2">
                  <strong>Amount:</strong> {formatCurrency(Math.abs(transactionToDelete.amount))}
                </Typography>
                <Typography variant="body2">
                  <strong>Description:</strong> {transactionToDelete.description}
                </Typography>
              </Box>
            )}
            <Alert severity="warning" sx={{ mt: 2 }}>
              This action cannot be undone. Deleting this transaction will affect your cash balance.
            </Alert>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel} disabled={deleting}>
              Cancel
            </Button>
            <Button
              onClick={handleDeleteConfirm}
              variant="contained"
              color="error"
              disabled={deleting}
              startIcon={<DeleteIcon />}
            >
              {deleting ? <CircularProgress size={24} /> : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default CashManagement;