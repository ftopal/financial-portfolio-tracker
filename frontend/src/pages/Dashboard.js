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
import PortfolioDialog from '../components/PortfolioDialog'; // Add this import

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

  // Add state for portfolio dialog
  const [showPortfolioDialog, setShowPortfolioDialog] = useState(false);

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

      // Helper function to round amounts to 8 decimal places
      const roundAmount = (amount) => {
        return Math.round(amount * 100000000) / 100000000;
      };

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
            // Convert total portfolio value (including cash) - with rounding
            const roundedTotalValue = roundAmount(portfolioTotalValue);
            const response = await currencyAPI.convert({
              amount: roundedTotalValue,
              from_currency: currency,
              to_currency: displayCurrency
            });

            console.log(`Converting ${roundedTotalValue} ${currency} to ${displayCurrency}:`, response.data);
            const convertedValue = parseFloat(response.data.converted_amount || portfolioTotalValue);

            // Convert gain/loss separately - with rounding
            const roundedGainLoss = roundAmount(gainLoss);
            const gainLossResponse = await currencyAPI.convert({
              amount: roundedGainLoss,
              from_currency: currency,
              to_currency: displayCurrency
            });
            const convertedGainLoss = parseFloat(gainLossResponse.data.converted_amount || gainLoss);

            // Convert cash separately - with rounding
            const roundedCash = roundAmount(cash);
            const cashResponse = await currencyAPI.convert({
              amount: roundedCash,
              from_currency: currency,
              to_currency: displayCurrency
            });
            const convertedCash = parseFloat(cashResponse.data.converted_amount || cash);

            totalValue += convertedValue;
            totalGainLoss += convertedGainLoss;
            totalCash += convertedCash;

          } catch (conversionError) {
            console.error(`Failed to convert ${currency} to ${displayCurrency}:`, conversionError);
            // Fallback: use original values (not ideal, but prevents complete failure)
            totalValue += portfolioTotalValue;
            totalGainLoss += gainLoss;
            totalCash += cash;
          }
        }
      }

      setConvertedTotals({
        totalValue,
        totalGainLoss,
        totalCash
      });

      console.log('Conversion completed:', { totalValue, totalGainLoss, totalCash });
    } catch (err) {
      console.error('Error in calculateConvertedTotals:', err);
      // Fallback to original calculation without conversion
      const totals = portfolios.reduce((acc, portfolio) => {
        acc.totalValue += parseFloat(portfolio.total_value_with_cash || portfolio.total_value || 0);
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

    // Helper function to round amounts to 8 decimal places
    const roundAmount = (amount) => {
      return Math.round(amount * 100000000) / 100000000;
    };

    for (const currency of Object.keys(totalsByCurrency)) {
      if (currency !== displayCurrency) {
        try {
          const roundedAmount = roundAmount(totalsByCurrency[currency].totalValue);
          const response = await currencyAPI.convert({
            amount: roundedAmount,
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

  // Handler for opening portfolio creation dialog
  const handleCreatePortfolio = () => {
    setShowPortfolioDialog(true);
  };

  // Handler for closing portfolio dialog and refreshing data
  const handlePortfolioDialogClose = () => {
    setShowPortfolioDialog(false);
    fetchPortfolios(); // Refresh portfolios list after creation
  };

  const totalsByCurrency = calculateTotalsByCurrency();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box display="flex" justifyContent="between" alignItems="center" mb={4}>
        <Typography variant="h4" component="h1" fontWeight="bold">
          Portfolio Dashboard
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Currency Selector */}
      <Box mb={4}>
        <Typography variant="h6" gutterBottom>
          Display Currency
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <LanguageIcon color="primary" />
          <CurrencySelector
            value={displayCurrency}
            onChange={setDisplayCurrency}
            variant="outlined"
          />
        </Box>
      </Box>

      {/* Portfolio Totals */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Total Portfolio Value
              </Typography>
              {loadingConversion ? (
                <CircularProgress size={24} />
              ) : (
                <Typography variant="h4" fontWeight="bold" color="primary">
                  {formatCurrency(convertedTotals.totalValue, displayCurrency)}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                Across all portfolios
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Total Gain/Loss
              </Typography>
              {loadingConversion ? (
                <CircularProgress size={24} />
              ) : (
                <Typography
                  variant="h4"
                  fontWeight="bold"
                  color={convertedTotals.totalGainLoss >= 0 ? 'success.main' : 'error.main'}
                >
                  {formatCurrency(convertedTotals.totalGainLoss, displayCurrency)}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                Unrealized gains/losses
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Total Cash
              </Typography>
              {loadingConversion ? (
                <CircularProgress size={24} />
              ) : (
                <Typography variant="h4" fontWeight="bold">
                  {formatCurrency(convertedTotals.totalCash, displayCurrency)}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                Available for investment
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Currency Breakdown */}
      {Object.keys(totalsByCurrency).length > 1 && (
        <Box mb={4}>
          <Typography variant="h6" gutterBottom>
            By Currency
          </Typography>
          <Grid container spacing={2}>
            {Object.entries(totalsByCurrency).map(([currency, data]) => (
              <Grid item xs={12} sm={6} md={4} key={currency}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                      {currency}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {data.count} portfolio{data.count !== 1 ? 's' : ''}
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(data.totalValue, currency)}
                    </Typography>
                    {currency !== displayCurrency && currencyBreakdownConversions[currency] && (
                      <Typography variant="caption" color="text.secondary">
                        ≈ {formatCurrency(currencyBreakdownConversions[currency], displayCurrency)}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      <Divider sx={{ my: 4 }} />

      {/* Individual Portfolios */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight="bold">
          Your Portfolios
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreatePortfolio} // Updated to use dialog instead of navigation
        >
          Create Portfolio
        </Button>
      </Box>

      <Grid container spacing={3}>
        {portfolios.map((portfolio) => (
          <Grid item xs={12} md={6} lg={4} key={portfolio.id}>
            <Card>
              <CardContent>
                <Stack spacing={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box>
                      <Typography variant="h6" fontWeight="bold">
                        {portfolio.name}
                      </Typography>
                      <Chip
                        label={portfolio.base_currency || 'USD'}
                        size="small"
                        variant="outlined"
                        icon={<AccountBalanceIcon />}
                      />
                    </Box>
                    <Typography variant="h5" fontWeight="bold">
                      {formatCurrency(portfolio.total_value_with_cash || portfolio.total_value || 0, portfolio.base_currency || 'USD')}
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
                  onClick={handleCreatePortfolio} // Updated to use dialog instead of navigation
                >
                  Create Portfolio
                </Button>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Portfolio Creation Dialog */}
      <PortfolioDialog
        open={showPortfolioDialog}
        onClose={handlePortfolioDialogClose}
        portfolio={null} // null for creating new portfolio
      />
    </Container>
  );
};

export default Dashboard;