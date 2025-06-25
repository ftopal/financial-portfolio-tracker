// frontend/src/components/CashManagement.js

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
  InputAdornment
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  History as HistoryIcon,
  TrendingUp,
  TrendingDown,
  AttachMoney
} from '@mui/icons-material';
import { api } from '../services/api';

const CashManagement = ({ portfolioId, cashBalance = 0, currency = 'USD', onBalanceUpdate }) => {
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

  useEffect(() => {
    if (tabValue === 1) {
      fetchCashHistory();
    }
  }, [tabValue, portfolioId]);

  const fetchCashHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await api.portfolios.getCashHistory(portfolioId);
      setCashHistory(response.data);
    } catch (err) {
      console.error('Error fetching cash history:', err);
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
  };

  const handleClose = () => {
    setOpen(false);
    setError('');
    setSuccess('');
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
        description: description || `Cash ${transactionType.toLowerCase()}`
      });

      setSuccess(`Successfully ${transactionType === 'DEPOSIT' ? 'deposited' : 'withdrew'} ${formatCurrency(numAmount)}`);

      // Refresh cash history if on history tab
      if (tabValue === 1) {
        fetchCashHistory();
      }

      // Notify parent component to refresh
      if (onBalanceUpdate) {
        onBalanceUpdate();
      }

      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.error || 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getTransactionIcon = (type) => {
    switch (type) {
      case 'DEPOSIT':
      case 'SELL':
      case 'DIVIDEND':
      case 'INTEREST':
        return <TrendingUp color="success" />;
      case 'WITHDRAWAL':
      case 'BUY':
      case 'FEE':
        return <TrendingDown color="error" />;
      default:
        return <AttachMoney />;
    }
  };

  const getTransactionColor = (type) => {
    switch (type) {
      case 'DEPOSIT':
      case 'SELL':
      case 'DIVIDEND':
      case 'INTEREST':
        return 'success';
      case 'WITHDRAWAL':
      case 'BUY':
      case 'FEE':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <AccountBalanceIcon color="primary" />
            <Typography variant="h6">Cash Account</Typography>
          </Box>
          <Typography variant="h4" color="primary">
            {formatCurrency(cashBalance)}
          </Typography>
        </Box>

        <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)} sx={{ mb: 2 }}>
          <Tab label="Actions" />
          <Tab label="History" icon={<HistoryIcon />} iconPosition="end" />
        </Tabs>

        {tabValue === 0 && (
          <Box display="flex" gap={2}>
            <Button
              variant="contained"
              color="success"
              startIcon={<AddIcon />}
              onClick={() => handleOpen('DEPOSIT')}
              fullWidth
            >
              Deposit
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<RemoveIcon />}
              onClick={() => handleOpen('WITHDRAWAL')}
              fullWidth
              disabled={cashBalance <= 0}
            >
              Withdraw
            </Button>
          </Box>
        )}

        {tabValue === 1 && (
          <TableContainer component={Paper} variant="outlined">
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
                    <TableCell align="right">Amount</TableCell>
                    <TableCell align="right">Balance</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {cashHistory.map((transaction) => (
                    <TableRow key={transaction.id}>
                      <TableCell>{formatDate(transaction.transaction_date)}</TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          {getTransactionIcon(transaction.transaction_type)}
                          <Chip
                            label={transaction.transaction_type}
                            size="small"
                            color={getTransactionColor(transaction.transaction_type)}
                            variant="outlined"
                          />
                        </Box>
                      </TableCell>
                      <TableCell>
                        {transaction.description}
                        {transaction.is_auto_deposit && (
                          <Chip label="Auto" size="small" sx={{ ml: 1 }} />
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          color={transaction.amount > 0 ? 'success.main' : 'error.main'}
                          fontWeight="medium"
                        >
                          {transaction.amount > 0 ? '+' : ''}{formatCurrency(transaction.amount)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{formatCurrency(transaction.balance_after)}</TableCell>
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
            {transactionType === 'DEPOSIT' ? 'Deposit Cash' : 'Withdraw Cash'}
          </DialogTitle>
          <DialogContent>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

            <TextField
              autoFocus
              margin="dense"
              label="Amount"
              type="number"
              fullWidth
              variant="outlined"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              InputProps={{
                startAdornment: (
                  <Typography color="textSecondary" sx={{ mr: 1 }}>
                    {currency}
                  </Typography>
                )
              }}
              sx={{ mb: 2 }}
            />="number"
              fullWidth
              variant="outlined"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              InputProps={{
                startAdornment: currency + ' '
              }}
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

            {transactionType === 'WITHDRAWAL' && cashBalance < parseFloat(amount || 0) && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Insufficient cash balance. Current balance: {formatCurrency(cashBalance)}
              </Alert>
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
              disabled={loading || !amount}
            >
              {loading ? <CircularProgress size={24} /> : transactionType}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default CashManagement;