// File: frontend/src/components/PortfolioPerformanceChart.js
// Simplified version with user-friendly messages only (no action buttons)

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
  TrendingDown as TrendingDownIcon,
  ShowChart as ShowChartIcon
} from '@mui/icons-material';
import Chart from 'react-apexcharts';
import api from '../services/api';
import TimePeriodSelector from './TimePeriodSelector';
import { formatCurrency } from '../utils/currencyUtils';

const PortfolioPerformanceChart = ({ portfolioId, portfolioName, currency = 'USD' }) => {
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [retentionApplied, setRetentionApplied] = useState(false);

  // Fetch performance data
  const fetchPerformanceData = useCallback(async (period = selectedPeriod) => {
    try {
      setLoading(true);
      setError('');

      console.log('Fetching performance data for portfolio:', portfolioId, 'period:', period);

      const response = await api.portfolios.getPerformance(portfolioId, {
        period: period
      });

      console.log('API Response:', response.data);

      setPerformanceData(response.data);
      setRetentionApplied(response.data.retention_applied || false);

    } catch (err) {
      console.error('Error fetching performance data:', err);

      // More specific error handling
      if (err.response?.status === 404) {
        setError('Portfolio not found');
      } else if (err.response?.status === 403) {
        setError('Access denied');
      } else {
        setError('Failed to load performance data');
      }
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
    if (!performanceData?.chart_data?.series) return {};

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
        }
      },
      yaxis: {
        labels: {
          formatter: function (value) {
            return formatCurrency(value);
          }
        }
      },
      tooltip: {
        x: {
          formatter: function (value) {
            return new Date(value).toLocaleDateString();
          }
        },
        y: {
          formatter: function (value) {
            return formatCurrency(value);
          }
        }
      },
      stroke: {
        curve: 'smooth',
        width: 2
      },
      colors: ['#1976d2'],
      grid: {
        show: true,
        borderColor: '#e0e0e0'
      }
    };
  };

  // Loading state
  if (loading) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center', minHeight: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <CircularProgress sx={{ mb: 2 }} />
        <Typography variant="body1" color="text.secondary">
          Loading portfolio performance...
        </Typography>
      </Paper>
    );
  }

  // Error state
  if (error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="body1">
            {error}
          </Typography>
        </Alert>
        <Box sx={{ textAlign: 'center' }}>
          <IconButton onClick={handleRefresh} color="primary">
            <RefreshIcon />
          </IconButton>
          <Typography variant="body2" color="text.secondary">
            Click to retry
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Empty portfolio state - SIMPLIFIED (no action button)
  if (performanceData?.empty_portfolio) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center', minHeight: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <ShowChartIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" gutterBottom color="text.secondary">
          Portfolio Performance
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2, maxWidth: 400, mx: 'auto' }}>
          {performanceData.message || 'No historical data available. Performance tracking will begin once transactions are added to this portfolio.'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Charts and analytics will appear here as your portfolio grows.
        </Typography>
      </Paper>
    );
  }

  // Insufficient data state - SIMPLIFIED
  if (performanceData?.insufficient_data) {
    return (
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box>
            <Typography variant="h6" gutterBottom>
              Portfolio Performance - {portfolioName}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {selectedPeriod} • Limited historical data
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TimePeriodSelector
              selectedPeriod={selectedPeriod}
              onPeriodChange={handlePeriodChange}
              disabled={loading}
            />
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        </Box>

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            {performanceData.message || 'Insufficient historical data for the selected period. More performance data will become available over time.'}
          </Typography>
        </Alert>

        {/* Show current value if available */}
        {performanceData?.summary && (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={6} md={3}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 2 }}>
                  <Box sx={{ color: 'primary.main', mb: 1 }}>
                    <InfoIcon />
                  </Box>
                  <Typography variant="h6" component="div">
                    {formatCurrency(performanceData.summary.current_value || 0)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Current Value
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}

        {/* Show minimal chart if any data exists */}
        {performanceData?.chart_data?.series?.[0]?.data?.length > 0 && (
          <Box sx={{ mt: 3 }}>
            <Chart
              options={getChartOptions()}
              series={performanceData.chart_data.series}
              type="line"
              height={300}
            />
          </Box>
        )}
      </Paper>
    );
  }

  // Normal state with full data
  return (
    <Paper sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h6" gutterBottom>
            Portfolio Performance - {portfolioName}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="body2" color="text.secondary">
              {selectedPeriod} • {performanceData?.summary?.total_days || 0} days
            </Typography>
            <Chip
              label={`${performanceData?.summary?.data_points || 0} data points`}
              size="small"
              variant="outlined"
            />
            {retentionApplied && (
              <Chip
                label="Limited data (Free plan)"
                size="small"
                color="warning"
                variant="outlined"
              />
            )}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TimePeriodSelector
            selectedPeriod={selectedPeriod}
            onPeriodChange={handlePeriodChange}
            disabled={loading}
          />
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export chart">
            <IconButton>
              <ExportIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Performance Summary Cards */}
      {performanceData?.summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[
            {
              label: 'Total Return',
              value: performanceData.summary.total_return_percentage ? `${performanceData.summary.total_return_percentage.toFixed(2)}%` : 'N/A',
              icon: performanceData.summary.total_return_percentage >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />,
              color: performanceData.summary.total_return_percentage >= 0 ? 'success' : 'error'
            },
            {
              label: 'Current Value',
              value: formatCurrency(performanceData.summary.current_value || 0),
              icon: <InfoIcon />,
              color: 'primary'
            },
            {
              label: 'Volatility',
              value: performanceData.summary.volatility ? `${performanceData.summary.volatility.toFixed(2)}%` : 'N/A',
              icon: <InfoIcon />,
              color: 'info'
            },
            {
              label: 'Data Points',
              value: performanceData.summary.data_points || 0,
              icon: <InfoIcon />,
              color: 'secondary'
            }
          ].map((metric, index) => (
            <Grid item xs={6} md={3} key={index}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent sx={{ textAlign: 'center', py: 2 }}>
                  <Box sx={{ color: `${metric.color}.main`, mb: 1 }}>
                    {metric.icon}
                  </Box>
                  <Typography variant="h6" component="div">
                    {metric.value}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metric.label}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Retention Warning */}
      {retentionApplied && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2">
            You're viewing limited historical data. Upgrade to Premium for unlimited access.
          </Typography>
        </Alert>
      )}

      {/* Chart */}
      {performanceData?.chart_data?.series && (
        <Box sx={{ mt: 3 }}>
          <Chart
            options={getChartOptions()}
            series={performanceData.chart_data.series}
            type="line"
            height={400}
          />
        </Box>
      )}

      {/* Message Display */}
      {performanceData?.message && !performanceData?.empty_portfolio && !performanceData?.insufficient_data && (
        <Alert severity="info" sx={{ mt: 2 }}>
          <Typography variant="body2">
            {performanceData.message}
          </Typography>
        </Alert>
      )}

      {/* Fallback No Data State */}
      {!loading && !performanceData && !error && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <ShowChartIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
          <Typography color="text.secondary" gutterBottom>
            No performance data available
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Performance tracking will begin once transactions are added
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default PortfolioPerformanceChart;