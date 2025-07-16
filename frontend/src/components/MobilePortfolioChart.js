import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  Chip,
  useTheme,
  useMediaQuery,
  Collapse,
  Button
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Fullscreen as FullscreenIcon
} from '@mui/icons-material';
import Chart from 'react-apexcharts';
import api from '../services/api';
import TimePeriodSelector from './TimePeriodSelector';
import { formatCurrency } from '../utils/currencyUtils';

const MobilePortfolioChart = ({ portfolioId, portfolioName, currency = 'USD' }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isSmallMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [retentionApplied, setRetentionApplied] = useState(false);
  const [expanded, setExpanded] = useState(!isMobile);
  const [fullscreen, setFullscreen] = useState(false);

  // Fetch performance data
  const fetchPerformanceData = useCallback(async (period = selectedPeriod) => {
    try {
      setLoading(true);
      setError('');

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

  // Responsive chart configuration
  const getChartOptions = () => {
    if (!performanceData?.chart_data) return {};

    const chartHeight = fullscreen ? 500 : (isMobile ? 300 : 400);
    const showToolbar = !isSmallMobile;

    return {
      chart: {
        type: 'line',
        height: chartHeight,
        fontFamily: 'inherit',
        toolbar: {
          show: showToolbar,
          tools: {
            download: showToolbar,
            selection: showToolbar,
            zoom: showToolbar,
            zoomin: showToolbar,
            zoomout: showToolbar,
            pan: showToolbar,
            reset: showToolbar
          }
        },
        zoom: {
          enabled: !isSmallMobile,
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
          style: {
            fontSize: isMobile ? '10px' : '12px'
          },
          formatter: function (value) {
            return new Date(value).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric'
            });
          }
        },
        tooltip: {
          enabled: true
        }
      },
      yaxis: {
        labels: {
          style: {
            fontSize: isMobile ? '10px' : '12px'
          },
          formatter: function (value) {
            return formatCurrency(value, currency, true); // true for compact format
          }
        },
        title: {
          text: `Value (${currency})`,
          style: {
            fontSize: isMobile ? '10px' : '12px'
          }
        }
      },
      stroke: {
        curve: 'smooth',
        width: isMobile ? 2 : 3
      },
      colors: ['#1976d2'],
      grid: {
        borderColor: theme.palette.divider,
        strokeDashArray: 5,
        padding: {
          left: isMobile ? 5 : 10,
          right: isMobile ? 5 : 10
        }
      },
      tooltip: {
        theme: theme.palette.mode,
        style: {
          fontSize: isMobile ? '11px' : '12px'
        },
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
      legend: {
        show: !isSmallMobile,
        fontSize: isMobile ? '11px' : '12px'
      },
      responsive: [{
        breakpoint: 600,
        options: {
          yaxis: {
            labels: {
              style: {
                fontSize: '9px'
              }
            }
          },
          xaxis: {
            labels: {
              style: {
                fontSize: '9px'
              }
            }
          }
        }
      }]
    };
  };

  // Compact performance summary for mobile
  const renderMobileSummary = () => {
    if (!performanceData?.summary) return null;

    const { summary } = performanceData;

    return (
      <Box sx={{ mb: 2 }}>
        <Card variant="outlined">
          <CardContent sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Return ({selectedPeriod})
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
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
              </Box>

              <Box sx={{ textAlign: 'right' }}>
                <Typography variant="body2" color="text.secondary">
                  Current Value
                </Typography>
                <Typography variant="h6">
                  {formatCurrency(summary.current_value || 0, currency, true)}
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>
    );
  };

  return (
    <Paper sx={{ mb: 3 }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant={isMobile ? "subtitle1" : "h6"}>
              Portfolio Performance
            </Typography>
            {!isMobile && (
              <Typography variant="body2" color="text.secondary">
                {portfolioName}
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={handleRefresh} disabled={loading}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            {isMobile && (
              <Tooltip title={fullscreen ? "Exit fullscreen" : "Fullscreen"}>
                <IconButton size="small" onClick={() => setFullscreen(!fullscreen)}>
                  <FullscreenIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            {isMobile && (
              <IconButton size="small" onClick={() => setExpanded(!expanded)}>
                {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            )}
          </Box>
        </Box>
      </Box>

      {/* Content */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {/* Time Period Selector */}
          <Box sx={{ mb: 2 }}>
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
              <Typography variant="body2">
                Limited historical data (free account). Upgrade for full history.
              </Typography>
            </Alert>
          )}

          {/* Loading State */}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {/* Chart and Summary */}
          {!loading && performanceData && (
            <>
              {/* Mobile Summary */}
              {isMobile && renderMobileSummary()}

              {/* Chart */}
              <Box sx={{ mt: 2 }}>
                <Chart
                  options={getChartOptions()}
                  series={performanceData.chart_data.series}
                  type="line"
                  height={fullscreen ? 500 : (isMobile ? 300 : 400)}
                />
              </Box>

              {/* Chart Info */}
              <Box sx={{
                mt: 2,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexDirection: isMobile ? 'column' : 'row',
                gap: 1
              }}>
                <Typography variant="body2" color="text.secondary">
                  {performanceData.start_date} to {performanceData.end_date}
                </Typography>

                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip
                    label={`${performanceData.chart_data.series?.[0]?.data?.length || 0} points`}
                    size="small"
                    variant="outlined"
                  />
                  {retentionApplied && (
                    <Chip
                      label="Limited"
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
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography color="text.secondary" gutterBottom>
                No performance data available
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Add transactions to see portfolio performance
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default MobilePortfolioChart;