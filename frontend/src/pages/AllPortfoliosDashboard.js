import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Grid,
  Paper,
  Box,
  CircularProgress,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  ShowChart as ShowChartIcon,
  Timeline as TimelineIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import api from '../services/api';
import PortfolioPerformanceSummary from '../components/PortfolioPerformanceSummary';

const AllPortfoliosDashboard = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const [showPerformanceWidgets, setShowPerformanceWidgets] = useState(true);

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await api.portfolios.getAllSummary();
        setSummary(response.data);
      } catch (err) {
        setError('Failed to load portfolio data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, []);

  // Convert asset type data to format for PieChart
  const prepareAssetTypeData = () => {
    if (!summary || !summary.by_asset_type) return [];

    return Object.entries(summary.by_asset_type).map(([name, data]) => ({
      name,
      value: parseFloat(data.total_value)
    }));
  };

  // Convert portfolio data to format for PieChart
  const preparePortfolioData = () => {
    if (!summary || !summary.portfolios) return [];

    return summary.portfolios.map(portfolio => ({
      name: portfolio.name,
      value: parseFloat(portfolio.total_value)
    }));
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        All Portfolios Dashboard
      </Typography>

      {error && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography color="error">{error}</Typography>
        </Paper>
      )}

      {summary && (
        <>
          <Grid container spacing={3}>
            {/* Summary Statistics */}
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="h6" gutterBottom>Total Portfolio Value</Typography>
                <Typography variant="h4">${Number(summary.total_value).toLocaleString()}</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="h6" gutterBottom>Total Invested</Typography>
                <Typography variant="h4">${Number(summary.total_invested).toLocaleString()}</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="h6" gutterBottom>Total Gain/Loss</Typography>
                <Typography
                  variant="h4"
                  color={summary.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                >
                  ${Number(summary.total_gain_loss).toLocaleString()}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="h6" gutterBottom>Portfolio Count</Typography>
                <Typography variant="h4">{summary.portfolio_count}</Typography>
              </Paper>
            </Grid>

            {/* Asset Type Distribution */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 300 }}>
                <Typography variant="h6" gutterBottom>Asset Types</Typography>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={prepareAssetTypeData()}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {prepareAssetTypeData().map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `$${Number(value).toLocaleString()}`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>

            {/* Portfolio Distribution */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 300 }}>
                <Typography variant="h6" gutterBottom>Portfolio Allocation</Typography>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={preparePortfolioData()}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {preparePortfolioData().map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `$${Number(value).toLocaleString()}`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>

            {/* Portfolio Performance Widgets */}
            {showPerformanceWidgets && summary && summary.portfolios && (
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12}>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TimelineIcon color="primary" />
                    Portfolio Performance Overview
                    <IconButton
                      size="small"
                      onClick={() => setShowPerformanceWidgets(false)}
                      sx={{ ml: 'auto' }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Typography>
                </Grid>

                {/* Show performance summaries for each portfolio */}
                {summary.portfolios.slice(0, 4).map(portfolio => (
                  <Grid item xs={12} sm={6} md={4} lg={3} key={portfolio.id}>
                    <Card>
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

                {/* Show all portfolios link if more than 4 */}
                {summary.portfolios.length > 4 && (
                  <Grid item xs={12}>
                    <Box sx={{ textAlign: 'center', py: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Showing {Math.min(4, summary.portfolios.length)} of {summary.portfolios.length} portfolios
                      </Typography>
                    </Box>
                  </Grid>
                )}
              </Grid>
            )}


            {!showPerformanceWidgets && (
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12}>
                  <Card>
                    <CardContent sx={{ p: 2, textAlign: 'center' }}>
                      <Button
                        startIcon={<ShowChartIcon />}
                        onClick={() => setShowPerformanceWidgets(true)}
                        variant="outlined"
                      >
                        Show Portfolio Performance
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            )}

            {/* Portfolio List */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>My Portfolios</Typography>
                <TableContainer>
                  <Table aria-label="portfolio table">
                    <TableHead>
                      <TableRow>
                        <TableCell>Name</TableCell>
                        <TableCell align="right">Assets</TableCell>
                        <TableCell align="right">Value</TableCell>
                        <TableCell align="right">Invested</TableCell>
                        <TableCell align="right">Gain/Loss</TableCell>
                        <TableCell align="right">Return %</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {summary.portfolios.map((portfolio) => (
                        <TableRow key={portfolio.id}>
                          <TableCell component="th" scope="row">
                            {portfolio.name}
                          </TableCell>
                          <TableCell align="right">{portfolio.asset_count}</TableCell>
                          <TableCell align="right">${Number(portfolio.total_value).toLocaleString()}</TableCell>
                          <TableCell align="right">${Number(portfolio.total_invested).toLocaleString()}</TableCell>
                          <TableCell
                            align="right"
                            sx={{ color: portfolio.gain_loss >= 0 ? 'success.main' : 'error.main' }}
                          >
                            ${Number(portfolio.gain_loss).toLocaleString()}
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{ color: portfolio.gain_loss_percentage >= 0 ? 'success.main' : 'error.main' }}
                          >
                            {portfolio.gain_loss_percentage.toFixed(2)}%
                          </TableCell>
                          <TableCell align="right">
                            <Button size="small" onClick={() => navigate(`/dashboard/${portfolio.id}`)}>
                              View
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Container>
  );
};

export default AllPortfoliosDashboard;