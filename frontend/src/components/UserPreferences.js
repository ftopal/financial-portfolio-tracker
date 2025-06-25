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
  const [hasLoaded, setHasLoaded] = useState(false);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      const response = await api.preferences.get();

      if (response.data.results && response.data.results.length > 0) {
        const savedPreferences = response.data.results[0];
        setPreferences({
          id: savedPreferences.id,
          auto_deposit_enabled: savedPreferences.auto_deposit_enabled,
          auto_deposit_mode: savedPreferences.auto_deposit_mode,
          show_cash_warnings: savedPreferences.show_cash_warnings,
          default_currency: savedPreferences.default_currency
        });
        setHasLoaded(true);
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

      // Include only the fields that should be updated
      const dataToSave = {
        auto_deposit_enabled: preferences.auto_deposit_enabled,
        auto_deposit_mode: preferences.auto_deposit_mode,
        show_cash_warnings: preferences.show_cash_warnings,
        default_currency: preferences.default_currency
      };

      await api.preferences.update(dataToSave);

      // Refresh preferences after save to ensure we have latest data
      await fetchPreferences();

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
            label="Enable Auto-Deposit"
            sx={{ display: 'block', mb: 2 }}
          />

          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Automatically deposit cash when buying securities with insufficient balance
          </Typography>

          <FormControl component="fieldset" disabled={!preferences.auto_deposit_enabled}>
            <FormLabel component="legend">Auto-Deposit Mode</FormLabel>
            <RadioGroup
              value={preferences.auto_deposit_mode}
              onChange={handleChange('auto_deposit_mode')}
            >
              <FormControlLabel
                value="EXACT"
                control={<Radio />}
                label="Deposit exact amount needed for transaction"
              />
              <FormControlLabel
                value="SHORTFALL"
                control={<Radio />}
                label="Deposit only the shortfall amount"
              />
            </RadioGroup>
          </FormControl>
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>Notifications</Typography>

          <FormControlLabel
            control={
              <Switch
                checked={preferences.show_cash_warnings}
                onChange={handleChange('show_cash_warnings')}
                color="primary"
              />
            }
            label="Show Cash Warnings"
            sx={{ display: 'block', mb: 2 }}
          />

          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Display warnings when cash balance is low
          </Typography>
        </Box>

        <Box display="flex" justifyContent="flex-end" gap={2}>
          <Button onClick={fetchPreferences} disabled={loading || saving}>
            Reset
          </Button>
          <Button
            variant="contained"
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