import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Chip
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  ShowChart as ShowChartIcon,
  Timeline as TimelineIcon
} from '@mui/icons-material';
import api from '../services/api';
import { formatCurrency } from '../utils/currencyUtils';

const PortfolioPerformanceSummary = ({
  portfolioId,
  period = '1Y',
  currency = 'USD',
  showTitle = true,
  compact = false
}) => {
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Fetch summary data
  const fetchSummaryData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const response = await api.portfolios.getPerformanceSummary(portfolioId, {
        period: period
      });

      setSummaryData(response.data);
    } catch (err) {
      console.error('Error fetching performance summary:', err);
      setError('Failed to load performance summary');
      setSummaryData(null);
    } finally {
      setLoading(false);
    }
  }, [portfolioId, period]);

  // Initial data fetch
  useEffect(() => {
    fetchSummaryData();
  }, [fetchSummaryData]);

  // Loading state
  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error" sx={{ mb: 0 }}>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // No data state
  if (!summaryData?.summary) {
    return (
      <Card>
        <CardContent>
          <Typography color="text.secondary" align="center">
            No performance data available
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const { summary } = summaryData;

  // Compact layout for dashboard widgets
  if (compact) {
    return (
      <Card>
        <CardContent sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Performance ({period})
            </Typography>
            <ShowChartIcon fontSize="small" color="action" />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
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
            {formatCurrency(summary.unrealized_gains || 0, currency)}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Full layout
  return (
    <Card>
      <CardContent>
        {showTitle && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
            <TimelineIcon color="primary" />
            <Typography variant="h6">
              Performance Summary ({period})
            </Typography>
          </Box>
        )}

        <Grid container spacing={2}>
          {/* Total Return */}
          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Return
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 1 }}>
                {summary.total_return_pct >= 0 ? (
                  <TrendingUpIcon color="success" fontSize="small" />
                ) : (
                  <TrendingDownIcon color="error" fontSize="small" />
                )}
                <Typography
                  variant="h5"
                  color={summary.total_return_pct >= 0 ? 'success.main' : 'error.main'}
                >
                  {summary.total_return_pct?.toFixed(2)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                {formatCurrency(summary.unrealized_gains || 0, currency)}
              </Typography>
            </Box>
          </Grid>

          {/* Current Value */}
          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Value
              </Typography>
              <Typography variant="h5" gutterBottom>
                {formatCurrency(summary.end_value || 0, currency)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Initial: {formatCurrency(summary.start_value || 0, currency)}
              </Typography>
            </Box>
          </Grid>

          {/* Volatility */}
          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Volatility
              </Typography>
              <Typography variant="h5" gutterBottom>
                {summary.volatility?.toFixed(2)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Risk measure
              </Typography>
            </Box>
          </Grid>

          {/* Best/Worst Day */}
          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Best Day
              </Typography>
              <Typography variant="h5" color="success.main" gutterBottom>
                +{summary.best_day?.toFixed(2)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Worst: {summary.worst_day?.toFixed(2)}%
              </Typography>
            </Box>
          </Grid>

          {/* Additional Stats */}
          <Grid item xs={12}>
            <Box sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 1,
              pt: 2,
              borderTop: 1,
              borderColor: 'divider'
            }}>
              <Typography variant="body2" color="text.secondary">
                Period: {summaryData.start_date} to {summaryData.end_date}
              </Typography>

              <Box sx={{ display: 'flex', gap: 1 }}>
                <Chip
                  label={`${summary.days_positive || 0} positive days`}
                  size="small"
                  color="success"
                  variant="outlined"
                />
                <Chip
                  label={`${summary.days_negative || 0} negative days`}
                  size="small"
                  color="error"
                  variant="outlined"
                />
                {summaryData.retention_applied && (
                  <Chip
                    label="Limited data"
                    size="small"
                    color="warning"
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default PortfolioPerformanceSummary;