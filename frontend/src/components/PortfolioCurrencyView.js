import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Divider,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper
} from '@mui/material';
import { portfolioAPI, currencyAPI } from '../services/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const PortfolioCurrencyView = ({ portfolio }) => {
  const [displayCurrency, setDisplayCurrency] = useState(portfolio?.base_currency || 'USD');
  const [convertedValue, setConvertedValue] = useState(null);
  const [exchangeRate, setExchangeRate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [availableCurrencies, setAvailableCurrencies] = useState([]);
  const [loadingCurrencies, setLoadingCurrencies] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');

  // Fetch available currencies from the backend
  useEffect(() => {
    const fetchCurrencies = async () => {
      try {
        setLoadingCurrencies(true);
        const response = await currencyAPI.list();

        // Extract currency codes from the response
        const currencies = response.data.results || response.data || [];
        const currencyCodes = currencies.map(currency => currency.code);

        // Filter out currencies that shouldn't appear in display dropdown
        const displayCurrencies = currencyCodes.filter(currency => {
          // Remove GBp (British Pence) as it's not a meaningful display currency
          // GBp is a trading unit that converts to GBP, not a display currency
          return currency !== 'GBp';
        });

        setAvailableCurrencies(displayCurrencies);

        console.log('Fetched currencies from API:', currencyCodes);
        console.log('Filtered display currencies:', displayCurrencies);
      } catch (err) {
        console.error('Failed to fetch currencies:', err);
        // Fallback to the most common currencies if API fails (excluding GBp)
        setAvailableCurrencies(['USD', 'EUR', 'GBP']);
      } finally {
        setLoadingCurrencies(false);
      }
    };

    fetchCurrencies();
  }, []);

  // Fetch chart data when portfolio or display currency changes
  useEffect(() => {
    if (portfolio?.id) {
      fetchChartData();
    }
  }, [portfolio?.id, displayCurrency]);

  const fetchChartData = async () => {
    try {
      setChartLoading(true);
      setChartError('');

      const response = await portfolioAPI.getCurrencyExposureChart(
        portfolio.id,
        displayCurrency !== portfolio.base_currency ? displayCurrency : null
      );

      if (response.data.chart_data && response.data.chart_data.length > 0) {
        const dataToUse = response.data.converted_chart_data || response.data.chart_data;
        setChartData(dataToUse);
      } else {
        setChartData([]);
        setChartError('No currency exposure data available');
      }
    } catch (err) {
      console.error('Failed to fetch currency chart data:', err);
      setChartError('Failed to load currency chart data');
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  };

  const formatCurrency = (amount, currency) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;

      return (
        <Paper sx={{ p: 1, bgcolor: 'background.paper', border: 1, borderColor: 'divider' }}>
          <Typography variant="body2" fontWeight="bold">
            {data.currency}
          </Typography>
          <Typography variant="body2">
            Original: {formatCurrency(data.original_amount, data.currency)}
          </Typography>
          <Typography variant="body2">
            Converted: {formatCurrency(data.amount, displayCurrency)}
          </Typography>
          <Typography variant="body2">
            Percentage: {data.percentage}%
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  const renderLabel = (entry) => {
    if (entry.percentage < 3) return '';
    return `${entry.currency}\n${entry.percentage}%`;
  };

  const formatExchangeRate = (rate, fromCurrency, toCurrency) => {
    if (!rate) return '';

    // Format the rate to 4 decimal places for display
    const formattedRate = parseFloat(rate).toFixed(4);
    return `1 ${fromCurrency} = ${formattedRate} ${toCurrency}`;
  };

  // Convert currency when display currency changes
  useEffect(() => {
    if (!portfolio) return;

    const portfolioValue = portfolio.total_value_with_cash || portfolio.total_value || 0;

    // If display currency is same as base currency, no conversion needed
    if (displayCurrency === portfolio.base_currency) {
      setConvertedValue(portfolioValue);
      setExchangeRate(null);
      setError(null);
      return;
    }

    // Perform currency conversion
    const convertCurrency = async () => {
      setLoading(true);
      setError(null);

      try {
        // Round the amount to 8 decimal places to prevent serializer errors
        const roundedAmount = Math.round(portfolioValue * 100000000) / 100000000;

        console.log('Converting currency:', {
          original_amount: portfolioValue,
          rounded_amount: roundedAmount,
          from_currency: portfolio.base_currency,
          to_currency: displayCurrency
        });

        const response = await currencyAPI.convert({
          amount: roundedAmount,
          from_currency: portfolio.base_currency,
          to_currency: displayCurrency
        });

        console.log('Conversion response:', response.data);
        setConvertedValue(response.data.converted_amount);

        // Calculate and store the exchange rate for display
        if (roundedAmount > 0) {
          const calculatedRate = response.data.converted_amount / roundedAmount;
          setExchangeRate(calculatedRate);
        }
      } catch (err) {
        console.error('Currency conversion failed:', err);

        // More detailed error handling
        if (err.response?.data?.error) {
          setError(`Failed to convert currency: ${err.response.data.error}`);
        } else if (err.response?.status === 400) {
          setError('Failed to convert currency - invalid request');
        } else {
          setError('Failed to convert currency - exchange rate not available');
        }

        // Fallback to showing original value
        setConvertedValue(portfolioValue);
        setExchangeRate(null);
      } finally {
        setLoading(false);
      }
    };

    convertCurrency();
  }, [displayCurrency, portfolio]);

  if (!portfolio) return null;

  const portfolioValue = portfolio.total_value_with_cash || portfolio.total_value || 0;
  const displayValue = convertedValue !== null ? convertedValue : portfolioValue;

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6">Portfolio Value & Currency Exposure</Typography>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Display Currency</InputLabel>
            <Select
              value={displayCurrency}
              onChange={(e) => setDisplayCurrency(e.target.value)}
              label="Display Currency"
              disabled={loadingCurrencies}
            >
              {loadingCurrencies ? (
                <MenuItem disabled>
                  <CircularProgress size={20} />
                </MenuItem>
              ) : (
                availableCurrencies.map((currency) => (
                  <MenuItem key={currency} value={currency}>
                    {currency} {currency === portfolio.base_currency ? '(Base)' : ''}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Box>

        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)} sx={{ mb: 2 }}>
          <Tab label="Overview" />
          <Tab label="Chart View" />
        </Tabs>

        {/* Tab 0: Your existing overview content */}
        {activeTab === 0 && (
          <>
            {loading ? (
              <Box display="flex" justifyContent="center" py={2}>
                <CircularProgress size={30} />
              </Box>
            ) : (
              <>
                <Typography variant="h4" fontWeight="bold" gutterBottom>
                  {formatCurrency(displayValue, displayCurrency)}
                </Typography>

                {displayCurrency !== portfolio.base_currency && !error && (
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {formatCurrency(portfolioValue, portfolio.base_currency)} (base currency)
                  </Typography>
                )}

                {displayCurrency !== portfolio.base_currency && exchangeRate && !error && (
                  <Typography variant="caption" color="text.secondary" display="block" mb={2}>
                    Exchange Rate: {formatExchangeRate(exchangeRate, portfolio.base_currency, displayCurrency)}
                  </Typography>
                )}

                {error && (
                  <Typography variant="caption" color="error" display="block" mb={2}>
                    {error}
                  </Typography>
                )}

                <Divider sx={{ my: 2 }} />

                <Box mt={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Currency Exposure
                  </Typography>
                  <Box display="flex" justifyContent="space-between" my={1}>
                    <Typography variant="body2">{portfolio.base_currency}:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      {formatCurrency(portfolioValue, portfolio.base_currency)}
                    </Typography>
                  </Box>

                  {displayCurrency !== portfolio.base_currency && convertedValue && !error && (
                    <>
                      <Box display="flex" justifyContent="space-between" my={1}>
                        <Typography variant="body2">{displayCurrency} (converted):</Typography>
                        <Typography variant="body2" fontWeight="medium">
                          {formatCurrency(convertedValue, displayCurrency)}
                        </Typography>
                      </Box>
                      {exchangeRate && (
                        <Box display="flex" justifyContent="space-between" my={1}>
                          <Typography variant="caption" color="text.secondary">Rate:</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {formatExchangeRate(exchangeRate, portfolio.base_currency, displayCurrency)}
                          </Typography>
                        </Box>
                      )}
                    </>
                  )}
                </Box>
              </>
            )}
          </>
        )}

        {/* Tab 1: New chart view */}
        {activeTab === 1 && (
          <>
            {chartLoading ? (
              <Box display="flex" justifyContent="center" py={4}>
                <CircularProgress />
              </Box>
            ) : chartError ? (
              <Alert severity="info">{chartError}</Alert>
            ) : chartData.length > 0 ? (
              <>
                <Box height={300} mb={3}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={renderLabel}
                        outerRadius={100}
                        fill="#8884d8"
                        dataKey={chartData[0]?.converted_amount !== undefined ? "converted_amount" : "amount"}
                      >
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        payload={chartData.map((item, index) => ({
                          value: `${item.currency} (${item.percentage}%)`,
                          type: 'square',
                          color: item.color,
                          id: index
                        }))}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </Box>

                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Currency</TableCell>
                        <TableCell align="right">Amount</TableCell>
                        <TableCell align="right">Percentage</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {chartData.map((row) => (
                        <TableRow key={row.currency}>
                          <TableCell>
                            <Box display="flex" alignItems="center" gap={1}>
                              <Box
                                width={12}
                                height={12}
                                bgcolor={row.color}
                                borderRadius="2px"
                              />
                              <Typography variant="body2" fontWeight="medium">
                                {row.currency}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="right">
                            <Box>
                              <Typography variant="body2">
                                {formatCurrency(row.original_amount, row.currency)}
                              </Typography>
                              {row.currency !== displayCurrency && (
                                <Typography variant="caption" color="text.secondary">
                                  → {formatCurrency(row.amount, displayCurrency)}
                                </Typography>
                              )}
                            </Box>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2">
                              {row.percentage}%
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            ) : (
              <Typography variant="body1" color="text.secondary" align="center">
                No currency exposure data available
              </Typography>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default PortfolioCurrencyView;