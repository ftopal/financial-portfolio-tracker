// src/components/PortfolioDialog.js - Updated with currency selection
import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert
} from '@mui/material';
import api from '../services/api';

const PortfolioDialog = ({ open, onClose, portfolio }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    base_currency: 'USD'  // Add base_currency
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currencies, setCurrencies] = useState([]);
  const [loadingCurrencies, setLoadingCurrencies] = useState(false);

  useEffect(() => {
    if (open) {
      fetchSupportedCurrencies();
    }

    if (portfolio) {
      setFormData({
        name: portfolio.name || '',
        description: portfolio.description || '',
        base_currency: portfolio.base_currency || 'USD'  // Include base_currency
      });
    } else {
      setFormData({
        name: '',
        description: '',
        base_currency: 'USD'  // Default to USD for new portfolios
      });
    }
    setError('');
  }, [portfolio, open]);

  const fetchSupportedCurrencies = async () => {
    setLoadingCurrencies(true);
    try {
      const response = await api.portfolios.supported_currencies();
      setCurrencies(response.data.currencies || []);
    } catch (err) {
      console.error('Error fetching currencies:', err);
      // Fallback to common currencies
      setCurrencies(['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY']);
    } finally {
      setLoadingCurrencies(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (portfolio) {
        // Update existing portfolio (exclude base_currency as it can't be changed)
        const { base_currency, ...updateData } = formData;
        await api.portfolios.update(portfolio.id, updateData);
      } else {
        // Create new portfolio with base_currency
        await api.portfolios.create(formData);
      }
      onClose();
    } catch (err) {
      setError(err.response?.data?.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          {portfolio ? 'Edit Portfolio' : 'Create New Portfolio'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <TextField
              fullWidth
              label="Portfolio Name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={loading}
              margin="normal"
            />
            <TextField
              fullWidth
              label="Description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              multiline
              rows={3}
              disabled={loading}
              margin="normal"
            />

            {/* Currency selector - only for new portfolios */}
            {!portfolio && (
              <FormControl fullWidth margin="normal" disabled={loading || loadingCurrencies}>
                <InputLabel>Base Currency</InputLabel>
                <Select
                  name="base_currency"
                  value={formData.base_currency}
                  onChange={handleChange}
                  label="Base Currency"
                >
                  {currencies.map((currency) => (
                    <MenuItem key={currency} value={currency}>
                      {currency}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {/* Info message for existing portfolios */}
            {portfolio && (
              <Alert severity="info" sx={{ mt: 2 }}>
                Base currency ({portfolio.base_currency || 'USD'}) cannot be changed after portfolio creation
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !formData.name.trim()}
          >
            {loading ? 'Saving...' : (portfolio ? 'Update' : 'Create')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default PortfolioDialog;