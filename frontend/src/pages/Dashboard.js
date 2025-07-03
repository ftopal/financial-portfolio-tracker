import React, { useState, useEffect, useContext } from 'react';
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
  Chip,
  Divider
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Add as AddIcon,
  Visibility as VisibilityIcon,
  Language as LanguageIcon
} from '@mui/icons-material';
import { api, currencyAPI } from '../services/api';
import { extractDataArray } from '../utils/apiHelpers';
import CurrencyContext from '../contexts/CurrencyContext';
import CurrencySelector from '../components/CurrencySelector';

const Dashboard = () => {
  const navigate = useNavigate();
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const currencyContext = useContext(CurrencyContext);
  const [convertedTotals, setConvertedTotals] = useState({ totalValue: 0, totalGainLoss: 0, totalCash: 0 });
  const [loadingConversion, setLoadingConversion] = useState(false);
  const [localDisplayCurrency, setLocalDisplayCurrency] = useState('USD');
  const [currencyBreakdownConversions, setCurrencyBreakdownConversions] = useState({});

  // Use context values if available, otherwise use local state
  const displayCurrency = currencyContext?.displayCurrency || localDisplayCurrency;
  const setDisplayCurrency = currencyContext?.setDisplayCurrency || setLocalDisplayCurrency;

  useEffect(() => {
    fetchPortfolios();
  }, []);

  useEffect(() => {
    // Calculate converted totals when portfolios or display currency changes
    if (portfolios.length > 0) {
      calculateConvertedTotals();
      updateCurrencyBreakdownConversions();
    }
  }, [portfolios, displayCurrency]);

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

  const calculateConvertedTotals = async () => {
    setLoadingConversion(true);
    console.log('Starting currency conversion, display currency:', displayCurrency);

    try {
      let totalValue = 0;
      let totalGainLoss = 0;
      let totalCash = 0;

      // Convert each portfolio's values to display currency
      for (const portfolio of portfolios) {
        const currency = portfolio.base_currency || 'USD';

        // Use total_value_with_cash if available, otherwise calculate it
        const portfolioTotalValue = portfolio.total_value_with_cash ||
          (parseFloat(portfolio.total_value || 0) + parseFloat(portfolio.cash_balance || 0));

        const gainLoss = parseFloat(portfolio.total_gain_loss || 0);
        const cash = parseFloat(portfolio.cash_balance || 0);

        console.log(`Portfolio ${portfolio.name}: ${currency} -> ${displayCurrency}`, {
          total_value_with_cash: portfolioTotalValue,
          total_value: portfolio.total_value,
          cash_balance: portfolio.cash_balance,
          gainLoss,
          currency
        });

        if (currency === displayCurrency) {
          totalValue += portfolioTotalValue;
          totalGainLoss += gainLoss;
          totalCash += cash;
        } else {
          try {
            // Convert total portfolio value (including cash)
            const response = await currencyAPI.convert({
              amount: portfolioTotalValue,
              from_currency: currency,
              to_currency: displayCurrency
            });

            console.log(`Converting ${portfolioTotalValue} ${currency} to ${displayCurrency}:`, response.data);
            const convertedValue = parseFloat(response.data.converted_amount || portfolioTotalValue);
            totalValue += convertedValue;

            // Convert gain/loss
            if (gainLoss !== 0) {
              const gainLossResponse = await currencyAPI.convert({
                amount: gainLoss,
                from_currency: currency,
                to_currency: displayCurrency
              });
              totalGainLoss += parseFloat(gainLossResponse.data.converted_amount || gainLoss);
            }

            // Convert cash balance separately for the summary
            if (cash !== 0) {
              const cashResponse = await currencyAPI.convert({
                amount: cash,
                from_currency: currency,
                to_currency: displayCurrency
              });
              totalCash += parseFloat(cashResponse.data.converted_amount || cash);
            }
          } catch (err) {
            console.error(`Failed to convert from ${currency} to ${displayCurrency}:`, err);
            // Fallback to original values if conversion fails
            totalValue += portfolioTotalValue;
            totalGainLoss += gainLoss;
            totalCash += cash;
          }
        }
      }

      console.log('Final converted totals:', { totalValue, totalGainLoss, totalCash });
      setConvertedTotals({ totalValue, totalGainLoss, totalCash });
    } catch (err) {
      console.error('Error converting currencies:', err);
      // Fallback to non-converted values
      const totals = portfolios.reduce((acc, portfolio) => {
        const totalVal = portfolio.total_value_with_cash ||
          (parseFloat(portfolio.total_value || 0) + parseFloat(portfolio.cash_balance || 0));
        acc.totalValue += totalVal;
        acc.totalGainLoss += parseFloat(portfolio.total_gain_loss || 0);
        acc.totalCash += parseFloat(portfolio.cash_balance || 0);
        return acc;
      }, { totalValue: 0, totalGainLoss: 0, totalCash: 0 });

      setConvertedTotals(totals);
    } finally {
      setLoadingConversion(false);
    }
  };

  // Calculate totals by currency (original grouped view)
  const calculateTotalsByCurrency = () => {
    if (!Array.isArray(portfolios)) {
      return {};
    }

    return portfolios.reduce((acc, portfolio) => {
      const currency = portfolio.base_currency || 'USD';

      if (!acc[currency]) {
        acc[currency] = {
          totalValue: 0,
          totalGainLoss: 0,
          totalCash: 0,
          count: 0
        };
      }

      acc[currency].totalValue += parseFloat(portfolio.total_value_with_cash || portfolio.total_value || 0);
      acc[currency].totalGainLoss += parseFloat(portfolio.total_gain_loss || 0);
      acc[currency].totalCash += parseFloat(portfolio.cash_balance || 0);
      acc[currency].count += 1;

      return acc;
    }, {});
  };

  // Update conversions for currency breakdown display
  const updateCurrencyBreakdownConversions = async () => {
    const conversions = {};
    const totalsByCurrency = calculateTotalsByCurrency();

    for (const currency of Object.keys(totalsByCurrency)) {
      if (currency !== displayCurrency) {
        try {
          const response = await currencyAPI.convert({
            amount: totalsByCurrency[currency].totalValue,
            from_currency: currency,
            to_currency: displayCurrency
          });
          conversions[currency] = response.data.converted_amount;
        } catch (err) {
          console.error(`Failed to convert ${currency} to ${displayCurrency} for display:`, err);
        }
      }
    }

    setCurrencyBreakdownConversions(conversions);
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

  const totalsByCurrency = calculateTotalsByCurrency();
  const currencyKeys = Object.keys(totalsByCurrency);
  const hasMultipleCurrencies = currencyKeys.length > 1;

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Portfolio Dashboard
      </Typography>

      {/* Unified Summary Section */}
      {portfolios.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="h6" display="flex" alignItems="center">
              <LanguageIcon sx={{ mr: 1 }} />
              Overall Summary
            </Typography>
            <CurrencySelector
              value={displayCurrency}
              onChange={(newCurrency) => setDisplayCurrency(newCurrency)}
              label="Display Currency"
              size="small"
              showHelper={false}
            />
          </Box>

          <Grid container spacing={3}>
            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: 'primary.50' }}>
                <CardContent>
                  <Stack spacing={1}>
                    <Typography color="text.secondary" variant="body2">
                      Total Portfolio Value
                    </Typography>
                    <Typography variant="h5" fontWeight="bold">
                      {loadingConversion ? (
                        <CircularProgress size={24} />
                      ) : (
                        formatCurrency(convertedTotals.totalValue, displayCurrency)
                      )}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Combined across all portfolios
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: convertedTotals.totalGainLoss >= 0 ? 'success.50' : 'error.50' }}>
                <CardContent>
                  <Stack spacing={1}>
                    <Typography color="text.secondary" variant="body2">
                      Total Gain/Loss
                    </Typography>
                    <Typography
                      variant="h5"
                      fontWeight="bold"
                      color={convertedTotals.totalGainLoss >= 0 ? 'success.main' : 'error.main'}
                    >
                      {loadingConversion ? (
                        <CircularProgress size={24} />
                      ) : (
                        formatCurrency(convertedTotals.totalGainLoss, displayCurrency)
                      )}
                    </Typography>
                    {convertedTotals.totalGainLoss >= 0 ? (
                      <Chip
                        icon={<TrendingUpIcon />}
                        label="Overall Profit"
                        color="success"
                        size="small"
                      />
                    ) : (
                      <Chip
                        icon={<TrendingDownIcon />}
                        label="Overall Loss"
                        color="error"
                        size="small"
                      />
                    )}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: 'info.50' }}>
                <CardContent>
                  <Stack spacing={1}>
                    <Typography color="text.secondary" variant="body2">
                      Total Cash Balance
                    </Typography>
                    <Typography variant="h5" fontWeight="bold">
                      {loadingConversion ? (
                        <CircularProgress size={24} />
                      ) : (
                        formatCurrency(convertedTotals.totalCash, displayCurrency)
                      )}
                    </Typography>
                    <Chip
                      icon={<AccountBalanceIcon />}
                      label="Available across all portfolios"
                      color="info"
                      size="small"
                    />
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Currency Breakdown Section - Only show if multiple currencies */}
      {hasMultipleCurrencies && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Breakdown by Currency
          </Typography>
          <Card>
            <CardContent>
              <Grid container spacing={2}>
                {currencyKeys.map((currency) => (
                  <Grid item xs={12} md={4} key={currency}>
                    <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        {currency} ({totalsByCurrency[currency].count} portfolio{totalsByCurrency[currency].count !== 1 ? 's' : ''})
                      </Typography>
                      <Typography variant="body1">
                        Total Value: <strong>{formatCurrency(totalsByCurrency[currency].totalValue, currency)}</strong>
                      </Typography>
                      <Typography
                        variant="body2"
                        color={totalsByCurrency[currency].totalGainLoss >= 0 ? 'success.main' : 'error.main'}
                      >
                        Gain/Loss: {formatCurrency(totalsByCurrency[currency].totalGainLoss, currency)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Cash: {formatCurrency(totalsByCurrency[currency].totalCash, currency)}
                      </Typography>
                      {currency !== displayCurrency && currencyBreakdownConversions[currency] && (
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                          ≈ {formatCurrency(currencyBreakdownConversions[currency], displayCurrency)} in {displayCurrency}
                        </Typography>
                      )}
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Box>
      )}

      <Divider sx={{ my: 4 }} />

      {/* Portfolio Cards */}
      <Box display="flex" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h5">
          Your Portfolios
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/portfolios/new')}
        >
          Create Portfolio
        </Button>
      </Box>

      <Grid container spacing={3}>
        {portfolios.map((portfolio) => (
          <Grid item xs={12} sm={6} md={4} key={portfolio.id}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Stack spacing={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6" component="div">
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