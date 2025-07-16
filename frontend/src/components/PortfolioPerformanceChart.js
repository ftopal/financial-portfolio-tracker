import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Grid,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  Chip
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  GetApp as ExportIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon
} from '@mui/icons-material';
import Chart from 'react-apexcharts';
import api from '../services/api'; // Your existing API import
import TimePeriodSelector from './TimePeriodSelector';
import { formatCurrency } from '../utils/currencyUtils';

const PortfolioPerformanceChart = ({ portfolioId, portfolioName, currency = 'USD' }) => {
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [retentionApplied, setRetentionApplied] = useState(false);

  // Fetch performance data using your existing API structure
  const fetchPerformanceData = useCallback(async (period = selectedPeriod) => {
    try {
      setLoading(true);
      setError('');

      // Use your existing API structure: api.portfolios.getPerformance
      const response = await api.portfolios.getPerformance(portfolioId, {
        period: period
      });

      setPerformanceData(response.data);
      setRetentionApplied(response.data.retention_applied || false);
    } catch (err) {
      console.error('Error fetching performance data:', err);
      setError('Failed to load performance data');
      setPerformanceData(null);
    } finally {
      setLoading(false);
    }
  }, [portfolioId, selectedPeriod]);

  // Handle period change
  const handlePeriodChange = (newPeriod) => {
    setSelectedPeriod(newPeriod);
    fetchPerformanceData(newPeriod);
  };

  // Handle refresh
  const handleRefresh = () => {
    fetchPerformanceData();
  };

  // Initial data fetch
  useEffect(() => {
    fetchPerformanceData();
  }, [fetchPerformanceData]);

  // Chart configuration
  const getChartOptions = () => {
    if (!performanceData?.chart_data) return {};

    return {
      chart: {
        type: 'line',
        height: 400,
        fontFamily: 'inherit',
        toolbar: {
          show: true,
          tools: {
            download: true,
            selection: true,
            zoom: true,
            zoomin: true,
            zoomout: true,
            pan: true,
            reset: true
          }
        },
        zoom: {
          enabled: true,
          type: 'x'
        },
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 800
        }
      },
      series: performanceData.chart_data.series,
      xaxis: {
        type: 'datetime',
        labels: {
          datetimeUTC: false,
          formatter: function (value) {
            return new Date(value).toLocaleDateString();
          }
        },
        tooltip: {
          enabled: true
        }
      },
      yaxis: {
        labels: {
          formatter: function (value) {
            return formatCurrency(value, currency);
          }
        },
        title: {
          text: `Portfolio Value (${currency})`
        }
      },
      stroke: {
        curve: 'smooth',
        width: 2
      },
      colors: ['#1976d2'],
      grid: {
        borderColor: '#e0e0e0',
        strokeDashArray: 5
      },
      tooltip: {
        theme: 'light',
        x: {
          formatter: function (value) {
            return new Date(value).toLocaleDateString();
          }
        },
        y: {
          formatter: function (value) {
            return formatCurrency(value, currency);
          }
        }
      },
      theme: {
        mode: 'light'
      }
    };
  };

  // Performance summary cards
  const renderSummaryCards = () => {
    if (!performanceData?.summary) return null;

    const { summary } = performanceData;

    return (
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Return
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {summary.total_return_pct >= 0 ? (
                  <TrendingUpIcon color="success" fontSize="small" />
                ) : (
                  <TrendingDownIcon color="error" fontSize="small" />
                )}
                <Typography
                  variant="h6"
                  color={summary.total_return_pct >= 0 ? 'success.main' : 'error.main'}
                >
                  {summary.total_return_pct?.toFixed(2)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                {formatCurrency(summary.total_return || 0, currency)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Value
              </Typography>
              <Typography variant="h6">
                {formatCurrency(summary.current_value || 0, currency)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Initial: {formatCurrency(summary.initial_value || 0, currency)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Volatility
              </Typography>
              <Typography variant="h6">
                {summary.volatility?.toFixed(2)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Risk measure
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Best Day
              </Typography>
              <Typography variant="h6" color="success.main">
                +{summary.best_day?.toFixed(2)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Worst: {summary.worst_day?.toFixed(2)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  return (
    <Paper sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h6" gutterBottom>
            Portfolio Performance
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {portfolioName} • {performanceData?.period || selectedPeriod}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Export chart">
            <IconButton disabled={!performanceData}>
              <ExportIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Time Period Selector */}
      <Box sx={{ mb: 3 }}>
        <TimePeriodSelector
          selectedPeriod={selectedPeriod}
          onPeriodChange={handlePeriodChange}
          showRetentionWarning={retentionApplied}
          disabled={loading}
        />
      </Box>

      {/* Error State */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Retention Warning */}
      {retentionApplied && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <InfoIcon fontSize="small" />
            <Typography variant="body2">
              Showing limited historical data (free account).
              <strong> Upgrade for full history.</strong>
            </Typography>
          </Box>
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Chart and Summary */}
      {!loading && performanceData && (
        <>
          {/* Summary Cards */}
          {renderSummaryCards()}

          {/* Chart */}
          <Box sx={{ mt: 2 }}>
            <Chart
              options={getChartOptions()}
              series={performanceData.chart_data.series}
              type="line"
              height={400}
            />
          </Box>

          {/* Chart Info */}
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Period: {performanceData.start_date} to {performanceData.end_date}
            </Typography>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip
                label={`${performanceData.chart_data.series?.[0]?.data?.length || 0} data points`}
                size="small"
                variant="outlined"
              />
              {retentionApplied && (
                <Chip
                  label="Limited data"
                  size="small"
                  color="warning"
                  variant="outlined"
                />
              )}
            </Box>
          </Box>
        </>
      )}

      {/* No Data State */}
      {!loading && !performanceData && !error && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography color="text.secondary" gutterBottom>
            No performance data available
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Add transactions to see portfolio performance
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default PortfolioPerformanceChart;