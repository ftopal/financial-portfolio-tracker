// Update your existing PortfolioList.js to show cash balances

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  Button,
  IconButton,
  Chip,
  LinearProgress,
  Menu,
  MenuItem
} from '@mui/material';
import {
  Add as AddIcon,
  MoreVert as MoreVertIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccountBalance as AccountBalanceIcon
} from '@mui/icons-material';
import { api } from '../services/api';

const PortfolioList = () => {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [anchorEl, setAnchorEl] = useState(null);
  const [selectedPortfolio, setSelectedPortfolio] = useState(null);

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getAll();
      setPortfolios(response.data);
    } catch (err) {
      console.error('Error fetching portfolios:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount || 0);
  };

  const formatPercentage = (value) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const handleMenuOpen = (event, portfolio) => {
    setAnchorEl(event.currentTarget);
    setSelectedPortfolio(portfolio);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedPortfolio(null);
  };

  const handleDelete = async () => {
    if (selectedPortfolio && window.confirm(`Delete portfolio "${selectedPortfolio.name}"?`)) {
      try {
        await api.portfolios.delete(selectedPortfolio.id);
        fetchPortfolios();
      } catch (err) {
        console.error('Error deleting portfolio:', err);
      }
    }
    handleMenuClose();
  };

  if (loading) {
    return <LinearProgress />;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">My Portfolios</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          component={Link}
          to="/portfolios/new"
        >
          Create Portfolio
        </Button>
      </Box>

      {portfolios.length === 0 ? (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <Typography variant="h6" color="textSecondary" gutterBottom>
                No portfolios yet
              </Typography>
              <Typography color="textSecondary">
                Create your first portfolio to start tracking your investments
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {portfolios.map((portfolio) => (
            <Grid item xs={12} md={6} lg={4} key={portfolio.id}>
              <Card
                sx={{
                  height: '100%',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4
                  }
                }}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                    <Box>
                      <Typography variant="h6" component={Link} to={`/portfolios/${portfolio.id}`}
                        sx={{ textDecoration: 'none', color: 'inherit', '&:hover': { color: 'primary.main' } }}>
                        {portfolio.name}
                      </Typography>
                      {portfolio.is_default && (
                        <Chip label="Default" size="small" color="primary" sx={{ mt: 1 }} />
                      )}
                    </Box>
                    <IconButton size="small" onClick={(e) => handleMenuOpen(e, portfolio)}>
                      <MoreVertIcon />
                    </IconButton>
                  </Box>

                  {portfolio.description && (
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      {portfolio.description}
                    </Typography>
                  )}

                  <Box mt={3}>
                    {/* Total Portfolio Value */}
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="textSecondary">Total Value</Typography>
                      <Typography variant="h5" fontWeight="bold">
                        {formatCurrency(portfolio.total_value_with_cash || portfolio.total_value)}
                      </Typography>
                    </Box>

                    {/* Securities & Cash Breakdown */}
                    <Box display="flex" justifyContent="space-between" mb={2}>
                      <Box>
                        <Typography variant="caption" color="textSecondary">Securities</Typography>
                        <Typography variant="body2">
                          {formatCurrency(portfolio.total_value)}
                        </Typography>
                      </Box>
                      <Box textAlign="right">
                        <Typography variant="caption" color="textSecondary">Cash</Typography>
                        <Typography variant="body2">
                          <AccountBalanceIcon sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.5 }} />
                          {formatCurrency(portfolio.cash_balance || 0)}
                        </Typography>
                      </Box>
                    </Box>

                    {/* Gain/Loss */}
                    <Box display="flex" alignItems="center" gap={1}>
                      {portfolio.total_gain_loss >= 0 ? (
                        <TrendingUpIcon color="success" sx={{ fontSize: 20 }} />
                      ) : (
                        <TrendingDownIcon color="error" sx={{ fontSize: 20 }} />
                      )}
                      <Typography
                        variant="body2"
                        color={portfolio.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                        fontWeight="medium"
                      >
                        {formatCurrency(portfolio.total_gain_loss)}
                        {' '}
                        ({formatPercentage(portfolio.gain_loss_percentage)})
                      </Typography>
                    </Box>

                    {/* Stats */}
                    <Box display="flex" justifyContent="space-between" mt={2} pt={2} borderTop={1} borderColor="divider">
                      <Typography variant="caption" color="textSecondary">
                        {portfolio.asset_count || 0} Assets
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {portfolio.transaction_count || 0} Transactions
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {portfolio.currency}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem component={Link} to={`/portfolios/${selectedPortfolio?.id}/edit`}>
          Edit
        </MenuItem>
        <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
          Delete
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default PortfolioList;