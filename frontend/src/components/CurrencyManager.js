import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Typography,
  CircularProgress,
  Alert,
  Box
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { currencyAPI } from '../services/api';
import { extractDataArray } from '../utils/apiHelpers';

const CurrencyManager = ({ open, onClose }) => {
  const [exchangeRates, setExchangeRates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      fetchExchangeRates();
    }
  }, [open]);

  const fetchExchangeRates = async () => {
    setLoading(true);
    setError('');
    try {
      console.log('Fetching exchange rates...');

      // Use currencyAPI.exchangeRates.list()
      const response = await currencyAPI.exchangeRates.list({ limit: 100 });

      console.log('Exchange rates response:', response);

      // Use the helper to extract data array
      const rates = extractDataArray(response);
      setExchangeRates(rates);
    } catch (err) {
      console.error('Failed to fetch exchange rates:', err);
      setError('Failed to fetch exchange rates');
      setExchangeRates([]);
    } finally {
      setLoading(false);
    }
  };

  const updateRates = async () => {
    setUpdating(true);
    setError('');
    try {
      // Use currencyAPI.updateRates()
      await currencyAPI.updateRates();

      // Wait a moment for the update to complete
      setTimeout(async () => {
        await fetchExchangeRates();
        setUpdating(false);
      }, 1000);
    } catch (err) {
      console.error('Failed to update exchange rates:', err);
      setError('Failed to update exchange rates');
      setUpdating(false);
    }
  };

  const formatRate = (rate) => {
    return parseFloat(rate).toFixed(4);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Exchange Rates
        <IconButton
          onClick={updateRates}
          disabled={updating}
          sx={{
            float: 'right',
            animation: updating ? 'rotate 1s linear infinite' : 'none',
            '@keyframes rotate': {
              '0%': { transform: 'rotate(0deg)' },
              '100%': { transform: 'rotate(360deg)' }
            }
          }}
          title="Update exchange rates"
        >
          <RefreshIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : exchangeRates.length === 0 ? (
          <Typography align="center" color="text.secondary" sx={{ p: 3 }}>
            No exchange rates found. Click the refresh button to update rates.
          </Typography>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>From</TableCell>
                  <TableCell>To</TableCell>
                  <TableCell align="right">Rate</TableCell>
                  <TableCell align="right">Date</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {exchangeRates.map((rate, index) => (
                  <TableRow key={index} hover>
                    <TableCell>{rate.from_currency}</TableCell>
                    <TableCell>{rate.to_currency}</TableCell>
                    <TableCell align="right">{formatRate(rate.rate)}</TableCell>
                    <TableCell align="right">{formatDate(rate.date)}</TableCell>
                    <TableCell>{rate.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {updating && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mt: 2 }}>
            <CircularProgress size={20} sx={{ mr: 1 }} />
            <Typography variant="body2" color="text.secondary">
              Updating exchange rates...
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CurrencyManager;