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
  Alert
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import api from '../services/api';

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
    try {
      const response = await api.exchangeRates.list({
        from_currency: 'USD',
        limit: 20
      });
      setExchangeRates(response.data);
    } catch (err) {
      setError('Failed to fetch exchange rates');
    } finally {
      setLoading(false);
    }
  };

  const updateRates = async () => {
    setUpdating(true);
    setError('');
    try {
      await api.currencies.updateRates();
      await fetchExchangeRates();
    } catch (err) {
      setError('Failed to update exchange rates');
    } finally {
      setUpdating(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Exchange Rates
        <IconButton
          onClick={updateRates}
          disabled={updating}
          sx={{ float: 'right' }}
        >
          <RefreshIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {loading ? (
          <CircularProgress />
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>From</TableCell>
                  <TableCell>To</TableCell>
                  <TableCell>Rate</TableCell>
                  <TableCell>Date</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {exchangeRates.map((rate, index) => (
                  <TableRow key={index}>
                    <TableCell>{rate.from_currency}</TableCell>
                    <TableCell>{rate.to_currency}</TableCell>
                    <TableCell>{parseFloat(rate.rate).toFixed(4)}</TableCell>
                    <TableCell>{new Date(rate.date).toLocaleDateString()}</TableCell>
                    <TableCell>{rate.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CurrencyManager;