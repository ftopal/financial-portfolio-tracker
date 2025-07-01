import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Button,
  Stack,
  Chip
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Add as AddIcon,
  Visibility as VisibilityIcon
} from '@mui/icons-material';
import { api } from '../services/api';
import { extractDataArray } from '../utils/apiHelpers';

const Dashboard = () => {
  const navigate = useNavigate();
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
  try {
    setLoading(true);
    const response = await api.portfolios.getAll();

    // Use the helper to extract data array
    const portfoliosData = extractDataArray(response);
    setPortfolios(portfoliosData);

    setError('');
  } catch (err) {
    console.error('Error fetching portfolios:', err);
    setError('Failed to load portfolios');
    setPortfolios([]);
  } finally {
    setLoading(false);
  }
};

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  const formatPercentage = (value) => {
    return `${value >= 0 ? '+' : ''}${value?.toFixed(2) || 0}%`;
  };

  // Calculate totals across all portfolios
  const calculateTotals = () => {
    // Check if portfolios is an array before using reduce
    if (!Array.isArray(portfolios)) {
      return { totalValue: 0, totalGainLoss: 0, totalCash: 0 };
    }

    return portfolios.reduce((acc, portfolio) => {
      acc.totalValue += parseFloat(portfolio.total_value_with_cash || portfolio.total_value || 0);
      acc.totalGainLoss += parseFloat(portfolio.total_gain_loss || 0);
      acc.totalCash += parseFloat(portfolio.cash_balance || 0);
      return acc;
    }, { totalValue: 0, totalGainLoss: 0, totalCash: 0 });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  const totals = calculateTotals();

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Portfolio Dashboard
      </Typography>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography color="text.secondary" variant="body2">
                  Total Value
                </Typography>
                <Typography variant="h5" fontWeight="bold">
                  {formatCurrency(totals.totalValue)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Across {portfolios.length} portfolio{portfolios.length !== 1 ? 's' : ''}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography color="text.secondary" variant="body2">
                  Total Gain/Loss
                </Typography>
                <Typography
                  variant="h5"
                  fontWeight="bold"
                  color={totals.totalGainLoss >= 0 ? 'success.main' : 'error.main'}
                >
                  {formatCurrency(totals.totalGainLoss)}
                </Typography>
                {totals.totalGainLoss >= 0 ? (
                  <TrendingUpIcon color="success" />
                ) : (
                  <TrendingDownIcon color="error" />
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography color="text.secondary" variant="body2">
                  Total Cash
                </Typography>
                <Typography variant="h5" fontWeight="bold">
                  {formatCurrency(totals.totalCash)}
                </Typography>
                <AccountBalanceIcon color="primary" />
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography color="text.secondary" variant="body2">
                  Portfolios
                </Typography>
                <Typography variant="h5" fontWeight="bold">
                  {portfolios.length}
                </Typography>
                <Button
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => navigate('/portfolios/new')}
                >
                  Create New
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Portfolio List */}
      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
        Your Portfolios
      </Typography>

      <Grid container spacing={3}>
        {portfolios.map((portfolio) => (
          <Grid item xs={12} md={6} lg={4} key={portfolio.id}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Stack spacing={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">
                      {portfolio.name}
                    </Typography>
                    <Chip
                      label={portfolio.base_currency || 'USD'}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </Box>

                  {portfolio.description && (
                    <Typography variant="body2" color="text.secondary">
                      {portfolio.description}
                    </Typography>
                  )}

                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Total Value
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(
                        portfolio.total_value_with_cash || portfolio.total_value,
                        portfolio.base_currency || 'USD'
                      )}
                    </Typography>
                  </Box>

                  <Box display="flex" justifyContent="space-between">
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Gain/Loss
                      </Typography>
                      <Typography
                        variant="body2"
                        color={portfolio.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                        fontWeight="medium"
                      >
                        {formatCurrency(portfolio.total_gain_loss, portfolio.base_currency || 'USD')}
                        {' '}
                        ({formatPercentage(portfolio.gain_loss_percentage)})
                      </Typography>
                    </Box>
                    <Box textAlign="right">
                      <Typography variant="caption" color="text.secondary">
                        Cash
                      </Typography>
                      <Typography variant="body2">
                        {formatCurrency(portfolio.cash_balance || 0, portfolio.base_currency || 'USD')}
                      </Typography>
                    </Box>
                  </Box>

                  <Button
                    fullWidth
                    variant="contained"
                    startIcon={<VisibilityIcon />}
                    onClick={() => navigate(`/portfolios/${portfolio.id}`)}
                  >
                    View Details
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}

        {portfolios.length === 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 4 }}>
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No portfolios yet
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Create your first portfolio to start tracking your investments
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => navigate('/portfolios/new')}
                >
                  Create Portfolio
                </Button>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Container>
  );
};

export default Dashboard;