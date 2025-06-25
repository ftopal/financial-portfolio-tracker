import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  FormControl,
  FormLabel,
  RadioGroup,
  Radio,
  Button,
  Box,
  Alert,
  Divider,
  CircularProgress
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Save as SaveIcon
} from '@mui/icons-material';
import { api } from '../services/api';

const UserPreferences = () => {
  const [preferences, setPreferences] = useState({
    auto_deposit_enabled: true,
    auto_deposit_mode: 'EXACT',
    show_cash_warnings: true,
    default_currency: 'USD'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      const response = await api.preferences.get();
      if (response.data.results && response.data.results.length > 0) {
        setPreferences(response.data.results[0]);
      }
    } catch (err) {
      console.error('Error fetching preferences:', err);
      setMessage({ type: 'error', text: 'Failed to load preferences' });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setPreferences(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      await api.preferences.update(preferences);

      setMessage({ type: 'success', text: 'Preferences saved successfully!' });
    } catch (err) {
      console.error('Error saving preferences:', err);
      setMessage({ type: 'error', text: 'Failed to save preferences' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" p={3}>
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={3}>
          <SettingsIcon color="primary" />
          <Typography variant="h5">Portfolio Preferences</Typography>
        </Box>

        {message.text && (
          <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage({ type: '', text: '' })}>
            {message.text}
          </Alert>
        )}

        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>Cash Management</Typography>

          <FormControlLabel
            control={
              <Switch
                checked={preferences.auto_deposit_enabled}
                onChange={handleChange('auto_deposit_enabled')}
                color="primary"
              />
            }
            label="Enable Auto-Deposits"
          />
          <Typography variant="body2" color="textSecondary" sx={{ ml: 4, mb: 2 }}>
            Automatically create deposits when buying securities with insufficient cash
          </Typography>

          {preferences.auto_deposit_enabled && (
            <FormControl component="fieldset" sx={{ ml: 4, mb: 2 }}>
              <FormLabel component="legend">Auto-Deposit Mode</FormLabel>
              <RadioGroup
                value={preferences.auto_deposit_mode}
                onChange={handleChange('auto_deposit_mode')}
              >
                <FormControlLabel
                  value="EXACT"
                  control={<Radio />}
                  label="Deposit exact amount needed"
                />
                <FormControlLabel
                  value="SHORTFALL"
                  control={<Radio />}
                  label="Deposit only the missing amount"
                />
              </RadioGroup>
            </FormControl>
          )}

          <FormControlLabel
            control={
              <Switch
                checked={preferences.show_cash_warnings}
                onChange={handleChange('show_cash_warnings')}
                color="primary"
              />
            }
            label="Show Cash Warnings"
          />
          <Typography variant="body2" color="textSecondary" sx={{ ml: 4 }}>
            Display warnings when cash balance is low
          </Typography>
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>Display Settings</Typography>

          <FormControl component="fieldset">
            <FormLabel component="legend">Default Currency</FormLabel>
            <RadioGroup
              row
              value={preferences.default_currency}
              onChange={handleChange('default_currency')}
            >
              <FormControlLabel value="USD" control={<Radio />} label="USD ($)" />
              <FormControlLabel value="EUR" control={<Radio />} label="EUR (€)" />
              <FormControlLabel value="GBP" control={<Radio />} label="GBP (£)" />
            </RadioGroup>
          </FormControl>
        </Box>

        <Box display="flex" justifyContent="flex-end">
          <Button
            variant="contained"
            color="primary"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Preferences'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

export default UserPreferences;