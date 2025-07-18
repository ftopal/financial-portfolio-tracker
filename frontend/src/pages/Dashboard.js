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
  Divider,
  IconButton,
  Collapse,
  Paper,
  Tooltip
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Add as AddIcon,
  Visibility as VisibilityIcon,
  Language as LanguageIcon,
  ShowChart as ShowChartIcon,
  Timeline as TimelineIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip as RechartsTooltip } from 'recharts';
import { api, currencyAPI } from '../services/api';
import { extractDataArray } from '../utils/apiHelpers';
import CurrencyContext from '../contexts/CurrencyContext';
import CurrencySelector from '../components/CurrencySelector';
import PortfolioDialog from '../components/PortfolioDialog';
import PortfolioPerformanceSummary from '../components/PortfolioPerformanceSummary';

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
  const [showPortfolioDialog, setShowPortfolioDialog] = useState(false);

  // New Phase 5 features
  const [showPerformanceOverview, setShowPerformanceOverview] = useState(true);
  const [showAssetAllocation, setShowAssetAllocation] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Chart colors for consistency
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D', '#ffc658', '#8dd1e1'];

  // Use context values if available, otherwise use local state
  const displayCurrency = currencyContext?.displayCurrency || localDisplayCurrency;
  const setDisplayCurrency = currencyContext?.setDisplayCurrency || setLocalDisplayCurrency;

  useEffect(() => {
    fetchPortfolios();
  }, []);

  useEffect(() => {
    if (portfolios.length > 0) {
      calculateConvertedTotals();
      updateCurrencyBreakdownConversions();
    }
  }, [portfolios, displayCurrency]);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getAll();
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

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchPortfolios();
    setRefreshing(false);
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
    try {
      let totalValue = 0;
      let totalGainLoss = 0;
      let totalCash = 0;

      const roundAmount = (amount) => Math.round(amount * 100000000) / 100000000;

      for (const portfolio of portfolios) {
        const currency = portfolio.base_currency || 'USD';
        const portfolioTotalValue = portfolio.total_value_with_cash ||
          (parseFloat(portfolio.total_value || 0) + parseFloat(portfolio.cash_balance || 0));
        const gainLoss = parseFloat(portfolio.total_gain_loss || 0);
        const cash = parseFloat(portfolio.cash_balance || 0);

        if (currency === displayCurrency) {
          totalValue += portfolioTotalValue;
          totalGainLoss += gainLoss;
          totalCash += cash;
        } else {
          try {
            const roundedTotalValue = roundAmount(portfolioTotalValue);
            const response = await currencyAPI.convert({
              amount: roundedTotalValue,
              from_currency: currency,
              to_currency: displayCurrency
            });
            totalValue += response.data.converted_amount;

            if (gainLoss !== 0) {
              const gainLossResponse = await currencyAPI.convert({
                amount: roundAmount(Math.abs(gainLoss)),
                from_currency: currency,
                to_currency: displayCurrency
              });
              totalGainLoss += gainLoss >= 0 ? gainLossResponse.data.converted_amount : -gainLossResponse.data.converted_amount;
            }

            if (cash !== 0) {
              const cashResponse = await currencyAPI.convert({
                amount: roundAmount(cash),
                from_currency: currency,
                to_currency: displayCurrency
              });
              totalCash += cashResponse.data.converted_amount;
            }
          } catch (err) {
            console.error(`Failed to convert ${currency} to ${displayCurrency}:`, err);
            totalValue += portfolioTotalValue;
            totalGainLoss += gainLoss;
            totalCash += cash;
          }
        }
      }

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

  const calculateTotalsByCurrency = () => {
    if (!Array.isArray(portfolios)) return {};

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

  const updateCurrencyBreakdownConversions = async () => {
    const conversions = {};
    const totalsByCurrency = calculateTotalsByCurrency();
    const roundAmount = (amount) => Math.round(amount * 100000000) / 100000000;

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

  // Prepare data for asset allocation pie chart
  const prepareAssetAllocationData = () => {
    const assetTypes = {};

    portfolios.forEach(portfolio => {
      // This is a simplified version - you might want to get detailed asset data from API
      const value = parseFloat(portfolio.total_value || 0);
      const type = portfolio.name || 'Portfolio'; // Fallback to portfolio name

      if (assetTypes[type]) {
        assetTypes[type] += value;
      } else {
        assetTypes[type] = value;
      }
    });

    return Object.entries(assetTypes).map(([name, value]) => ({
      name,
      value,
      formattedValue: formatCurrency(value, displayCurrency)
    }));
  };

  // Prepare data for portfolio distribution pie chart
  const preparePortfolioDistributionData = () => {
    return portfolios.map(portfolio => ({
      name: portfolio.name,
      value: parseFloat(portfolio.total_value || 0),
      formattedValue: formatCurrency(portfolio.total_value || 0, portfolio.base_currency || 'USD'),
      gainLoss: parseFloat(portfolio.total_gain_loss || 0),
      gainLossPercent: portfolio.gain_loss_percentage || 0
    }));
  };

  const handleCreatePortfolio = () => {
    setShowPortfolioDialog(true);
  };

  const handlePortfolioDialogClose = () => {
    setShowPortfolioDialog(false);
    fetchPortfolios();
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
      {/* Header with Refresh */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Typography variant="h4" component="h1" fontWeight="bold">
          Portfolio Dashboard
        </Typography>
        <Tooltip title="Refresh Data">
          <IconButton onClick={handleRefresh} disabled={refreshing}>
            <RefreshIcon sx={{
              animation: refreshing ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' }
              }
            }} />
          </IconButton>
        </Tooltip>
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
                Total return
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
                Available cash
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Performance Overview Section */}
      {portfolios.length > 0 && (
        <>
          <Card sx={{ mb: 4 }}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TimelineIcon color="primary" />
                  Portfolio Performance Overview
                </Typography>
                <IconButton onClick={() => setShowPerformanceOverview(!showPerformanceOverview)}>
                  {showPerformanceOverview ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>

              <Collapse in={showPerformanceOverview}>
                <Grid container spacing={3}>
                  {portfolios.slice(0, 4).map(portfolio => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={portfolio.id}>
                      <Card variant="outlined">
                        <CardContent sx={{ p: 2 }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="subtitle2" noWrap>
                              {portfolio.name}
                            </Typography>
                            <IconButton
                              size="small"
                              onClick={() => navigate(`/portfolios/${portfolio.id}`)}
                            >
                              <ShowChartIcon fontSize="small" />
                            </IconButton>
                          </Box>

                          <PortfolioPerformanceSummary
                            portfolioId={portfolio.id}
                            period="3M"
                            currency={portfolio.base_currency || 'USD'}
                            showTitle={false}
                            compact={true}
                          />
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}

                  {portfolios.length > 4 && (
                    <Grid item xs={12}>
                      <Box sx={{ textAlign: 'center', py: 2 }}>
                        <Typography variant="body2" color="text.secondary">
                          Showing 4 of {portfolios.length} portfolios
                        </Typography>
                      </Box>
                    </Grid>
                  )}
                </Grid>
              </Collapse>
            </CardContent>
          </Card>

          {/* Asset Allocation Charts */}
          <Card sx={{ mb: 4 }}>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <AccountBalanceIcon color="primary" />
                  Asset Allocation
                </Typography>
                <IconButton onClick={() => setShowAssetAllocation(!showAssetAllocation)}>
                  {showAssetAllocation ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>

              <Collapse in={showAssetAllocation}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2, height: 300 }}>
                      <Typography variant="subtitle1" gutterBottom textAlign="center">
                        Portfolio Distribution
                      </Typography>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={preparePortfolioDistributionData()}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          >
                            {preparePortfolioDistributionData().map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <RechartsTooltip
                            formatter={(value, name) => [
                              formatCurrency(value, displayCurrency),
                              name
                            ]}
                          />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </Paper>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2, height: 300 }}>
                      <Typography variant="subtitle1" gutterBottom textAlign="center">
                        Currency Breakdown
                      </Typography>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={Object.entries(totalsByCurrency).map(([currency, data]) => ({
                              name: currency,
                              value: data.totalValue,
                              count: data.count
                            }))}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          >
                            {Object.keys(totalsByCurrency).map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <RechartsTooltip
                            formatter={(value, name) => [
                              formatCurrency(value, name),
                              `${name} (${totalsByCurrency[name]?.count || 0} portfolios)`
                            ]}
                          />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </Paper>
                  </Grid>
                </Grid>
              </Collapse>
            </CardContent>
          </Card>
        </>
      )}

      {/* Currency Breakdown */}
      {Object.keys(totalsByCurrency).length > 1 && (
        <Card sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Currency Breakdown
            </Typography>
            <Grid container spacing={2}>
              {Object.entries(totalsByCurrency).map(([currency, data]) => (
                <Grid item xs={12} sm={6} md={4} key={currency}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      {currency} ({data.count} portfolio{data.count !== 1 ? 's' : ''})
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(data.totalValue, currency)}
                    </Typography>
                    {currency !== displayCurrency && currencyBreakdownConversions[currency] && (
                      <Typography variant="caption" color="text.secondary">
                        ≈ {formatCurrency(currencyBreakdownConversions[currency], displayCurrency)}
                      </Typography>
                    )}
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Individual Portfolios */}
      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 3 }}>
        Your Portfolios
      </Typography>

      <Grid container spacing={3}>
        {portfolios.map(portfolio => (
          <Grid item xs={12} sm={6} md={4} key={portfolio.id}>
            <Card>
              <CardContent>
                <Stack spacing={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6" noWrap>
                      {portfolio.name}
                    </Typography>
                    <Chip
                      label={portfolio.base_currency || 'USD'}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  <Divider />

                  <Box display="flex" justifyContent="space-between">
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Total Value
                      </Typography>
                      <Typography variant="h6">
                        {formatCurrency(portfolio.total_value || 0, portfolio.base_currency || 'USD')}
                      </Typography>
                    </Box>
                    <Box textAlign="right">
                      <Typography variant="caption" color="text.secondary">
                        Assets
                      </Typography>
                      <Typography variant="h6">
                        {portfolio.asset_count || 0}
                      </Typography>
                    </Box>
                  </Box>

                  <Box display="flex" justifyContent="space-between" alignItems="center">
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
                  onClick={handleCreatePortfolio}
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
        portfolio={null}
      />
    </Container>
  );
};

export default Dashboard;