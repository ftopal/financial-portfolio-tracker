import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  IconButton,
  Collapse,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Breadcrumbs,
  Link,
  Tooltip,
  Badge
} from '@mui/material';
import {
  ChevronRight as ChevronRightIcon,
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  AccountBalance as AccountBalanceIcon,
  ShowChart as ShowChartIcon,
  AttachMoney as AttachMoneyIcon,
  AccountBalanceWallet as WalletIcon
} from '@mui/icons-material';
import api from '../services/api';
import StockAutocomplete from '../components/StockAutocomplete';
import CashManagement from '../components/CashManagement';
import TransactionForm from '../components/TransactionForm';
import PortfolioCurrencyView from '../components/PortfolioCurrencyView';

const ConsolidatedPortfolioDetails = () => {
  const { portfolioId } = useParams();
  const [portfolio, setPortfolio] = useState(null);
  const [consolidatedAssets, setConsolidatedAssets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [cashAccount, setCashAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedRows, setExpandedRows] = useState({});
  const [selectedSecurity, setSelectedSecurity] = useState(null);
  const [showTransactionForm, setShowTransactionForm] = useState(false);

  const fetchConsolidatedData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getConsolidatedView(portfolioId);

      setPortfolio(response.data.portfolio || {});
      setConsolidatedAssets(response.data.consolidated_assets || []);
      setSummary(response.data.summary || {});
      setCashAccount(response.data.cash_account || null);
      setError('');
    } catch (err) {
      console.error('Error fetching consolidated data:', err);
      setError('Failed to load portfolio data');
      setConsolidatedAssets([]);
    } finally {
      setLoading(false);
    }
  }, [portfolioId]);

  useEffect(() => {
    fetchConsolidatedData();
  }, [portfolioId, fetchConsolidatedData]);

  const toggleRow = (key) => {
    setExpandedRows(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleAddTransactionForSecurity = (asset) => {
    const firstTransaction = asset.transactions && asset.transactions.length > 0
      ? asset.transactions[0]
      : null;

    setSelectedSecurity({
      id: firstTransaction ? firstTransaction.stock_id : null,
      symbol: asset.symbol,
      name: asset.name,
      current_price: asset.current_price,
      security_type: asset.asset_type,
      total_quantity: asset.total_quantity
    });

    setShowTransactionForm(true);
  };

  const handleDeleteTransaction = async (transactionId, securityName) => {
    if (window.confirm(`Are you sure you want to delete this transaction for ${securityName}?`)) {
      try {
        await api.transactions.delete(transactionId);
        fetchConsolidatedData();
      } catch (err) {
        console.error('Error deleting transaction:', err);
        alert('Failed to delete transaction. Please try again.');
      }
    }
  };

  const handleOpenNewTransactionModal = () => {
    setSelectedSecurity(null);
    setShowTransactionForm(true);
  };

  const handleTransactionSuccess = () => {
    setShowTransactionForm(false);
    setSelectedSecurity(null);
    fetchConsolidatedData();
  };

  const formatCurrency = (amount, currencyCode = null) => {
    const code = currencyCode || portfolio?.base_currency || 'USD';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: code
    }).format(amount || 0);
  };

  const formatPercentage = (value) => {
    if (value === undefined || value === null || isNaN(value)) {
      return '0.00%';
    }
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';

    try {
      let date;
      if (dateString.includes('T')) {
        date = new Date(dateString);
      } else {
        date = new Date(dateString + 'T00:00:00Z');
      }

      if (isNaN(date.getTime())) {
        return 'Invalid Date';
      }

      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (error) {
      console.error('Date formatting error:', error);
      return 'Invalid Date';
    }
  };

  const getHoldingsMap = () => {
    const holdings = {};
    consolidatedAssets.forEach(asset => {
      holdings[asset.symbol] = asset.total_quantity;
    });
    return holdings;
  };

  const getTransactionTypeColor = (type) => {
    const colors = {
      'BUY': 'success',
      'SELL': 'error',
      'DIVIDEND': 'info',
      'SPLIT': 'secondary'
    };
    return colors[type] || 'default';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error && !portfolio) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button component={RouterLink} to="/portfolios" variant="text" startIcon={<ChevronRightIcon sx={{ transform: 'rotate(180deg)' }} />}>
          Back to Portfolios
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
        <Link component={RouterLink} to="/portfolios" underline="hover" color="inherit">
          Portfolios
        </Link>
        <Typography color="text.primary">{portfolio?.name || 'Portfolio Details'}</Typography>
      </Breadcrumbs>

      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box display="flex" alignItems="center" gap={2} mb={1}>
          <Typography variant="h4" component="h1">
            {portfolio?.name || 'Portfolio Details'}
          </Typography>
          <Chip
            label={portfolio?.base_currency || 'USD'}
            color="primary"
            variant="outlined"
            size="medium"
            icon={<AttachMoneyIcon />}
          />
        </Box>
        {portfolio?.description && (
          <Typography variant="body1" color="text.secondary">
            {portfolio.description}
          </Typography>
        )}
      </Box>

      {/* Summary Cards and Currency View Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Summary Cards */}
        <Grid item xs={12} lg={6}>
          {summary && (
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom variant="body2">
                          Total Value
                        </Typography>
                        <Typography variant="h5" component="div" fontWeight="bold">
                          {formatCurrency(summary.total_value)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Securities + Cash
                        </Typography>
                      </Box>
                      <WalletIcon color="primary" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom variant="body2">
                          Securities Value
                        </Typography>
                        <Typography variant="h5" component="div" fontWeight="bold">
                          {formatCurrency(summary.securities_value || summary.total_value)}
                        </Typography>
                      </Box>
                      <ShowChartIcon color="primary" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom variant="body2">
                          Cash Balance
                        </Typography>
                        <Typography variant="h5" component="div" fontWeight="bold">
                          {formatCurrency(summary.cash_balance || 0)}
                        </Typography>
                      </Box>
                      <AccountBalanceIcon color="primary" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom variant="body2">
                          Total Gain/Loss
                        </Typography>
                        <Typography
                          variant="h5"
                          component="div"
                          fontWeight="bold"
                          color={summary.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                        >
                          {formatCurrency(summary.total_gain_loss)}
                        </Typography>
                        <Typography
                          variant="caption"
                          color={summary.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                        >
                          {summary.total_cost > 0 ? formatPercentage((summary.total_gain_loss / summary.total_cost) * 100) : '0.00%'}
                        </Typography>
                      </Box>
                      {summary.total_gain_loss >= 0 ? (
                        <TrendingUpIcon color="success" />
                      ) : (
                        <TrendingDownIcon color="error" />
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom variant="body2">
                          Total Dividends
                        </Typography>
                        <Typography variant="h5" component="div" fontWeight="bold" color="info.main">
                          {formatCurrency(summary.total_dividends || 0)}
                        </Typography>
                      </Box>
                      <AttachMoneyIcon color="info" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}
        </Grid>

        {/* Currency View */}
        <Grid item xs={12} lg={6}>
          {portfolio && (
            <PortfolioCurrencyView portfolio={portfolio} />
          )}
        </Grid>
      </Grid>

      {/* Cash Management */}
      {cashAccount && (
        <Box sx={{ mb: 4 }}>
          <CashManagement
            portfolioId={portfolioId}
            cashBalance={cashAccount.balance}
            currency={portfolio?.base_currency || cashAccount.currency}
            onBalanceUpdate={fetchConsolidatedData}
            portfolio={portfolio}
          />
        </Box>
      )}

      {/* Securities Holdings Table */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6" component="h2" gutterBottom>
            Securities Holdings
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Click on any row to see individual transactions
          </Typography>
        </Box>

        {consolidatedAssets.length === 0 ? (
          <Box sx={{ p: 6, textAlign: 'center' }}>
            <Typography color="text.secondary" gutterBottom>
              No securities in this portfolio yet.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Add securities to start tracking your investments.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Asset</TableCell>
                  <TableCell align="right">Quantity</TableCell>
                  <TableCell align="right">Avg Cost ({portfolio?.base_currency || 'USD'})</TableCell>
                  <TableCell align="right">Current Price ({portfolio?.base_currency || 'USD'})</TableCell>
                  <TableCell align="right">Total Value ({portfolio?.base_currency || 'USD'})</TableCell>
                  <TableCell align="right">Gain/Loss ({portfolio?.base_currency || 'USD'})</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {consolidatedAssets.map((asset) => (
                  <React.Fragment key={asset.key}>
                    <TableRow
                      hover
                      onClick={() => toggleRow(asset.key)}
                      sx={{ cursor: 'pointer', '& > *': { borderBottom: 'unset' } }}
                    >
                      <TableCell>
                        <Box display="flex" alignItems="center">
                          <IconButton size="small" sx={{ mr: 1 }}>
                            {expandedRows[asset.key] ? <ExpandMoreIcon /> : <ChevronRightIcon />}
                          </IconButton>
                          <Box>
                            <Typography variant="body2" fontWeight="medium">
                              {asset.symbol ? `${asset.symbol} - ${asset.name}` : asset.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {asset.asset_type} • {asset.transactions.length} transaction{asset.transactions.length > 1 ? 's' : ''}
                            </Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell align="right">{asset.total_quantity.toLocaleString()}</TableCell>
                      <TableCell align="right">{formatCurrency(asset.avg_cost_price)}</TableCell>
                      <TableCell align="right">{formatCurrency(asset.current_price)}</TableCell>
                      <TableCell align="right">
                        <Typography fontWeight="medium">
                          {formatCurrency(asset.total_current_value)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Box display="flex" alignItems="center" justifyContent="flex-end">
                          {asset.total_gain_loss >= 0 ? (
                            <TrendingUpIcon sx={{ fontSize: 20, mr: 0.5 }} color="success" />
                          ) : (
                            <TrendingDownIcon sx={{ fontSize: 20, mr: 0.5 }} color="error" />
                          )}
                          <Box>
                            <Typography
                              variant="body2"
                              fontWeight="medium"
                              color={asset.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                            >
                              {formatCurrency(Math.abs(asset.total_gain_loss))}
                            </Typography>
                            <Typography
                              variant="caption"
                              color={asset.total_gain_loss >= 0 ? 'success.main' : 'error.main'}
                            >
                              {(() => {
                                const totalCost = asset.avg_cost_price * asset.total_quantity;
                                const percentage = totalCost > 0 ? (asset.total_gain_loss / totalCost) * 100 : 0;
                                return formatPercentage(percentage);
                              })()}
                            </Typography>
                          </Box>
                        </Box>
                      </TableCell>
                    </TableRow>

                    {/* Expanded Row - Transactions */}
                    <TableRow>
                      <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
                        <Collapse in={expandedRows[asset.key]} timeout="auto" unmountOnExit>
                          <Box sx={{ margin: 2 }}>
                            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                              <Typography variant="subtitle2" gutterBottom component="div">
                                Transaction History
                              </Typography>
                              <Button
                                size="small"
                                startIcon={<AddIcon />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleAddTransactionForSecurity(asset);
                                }}
                              >
                                Add Transaction
                              </Button>
                            </Box>
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  <TableCell>Date</TableCell>
                                  <TableCell>Type</TableCell>
                                  <TableCell align="right">Quantity</TableCell>
                                  <TableCell align="right">Price</TableCell>
                                  <TableCell align="right">Total</TableCell>
                                  <TableCell align="right">Gain/Loss</TableCell>
                                  <TableCell align="center">Action</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {asset.transactions.map((transaction) => (
                                  <TableRow key={transaction.id}>
                                    <TableCell>{formatDate(transaction.date || transaction.transaction_date)}</TableCell>
                                    <TableCell>
                                      <Chip
                                        label={transaction.transaction_type}
                                        size="small"
                                        color={getTransactionTypeColor(transaction.transaction_type)}
                                      />
                                    </TableCell>
                                    <TableCell align="right">{transaction.quantity}</TableCell>
                                    <TableCell align="right">
                                      {/* Show price in original transaction currency */}
                                      {formatCurrency(transaction.price, transaction.currency || portfolio?.base_currency)}
                                    </TableCell>
                                    <TableCell align="right">
                                      {/* Show total in original transaction currency */}
                                      {formatCurrency(
                                        transaction.transaction_type === 'BUY'
                                          ? (transaction.quantity * transaction.price) + (transaction.fees || 0)
                                          : transaction.transaction_type === 'SELL'
                                          ? (transaction.quantity * transaction.price) - (transaction.fees || 0)
                                          : transaction.value,
                                        transaction.currency || portfolio?.base_currency
                                      )}
                                      {/* Show converted value if different currency */}
                                      {transaction.currency && transaction.currency !== portfolio?.base_currency && (
                                        <Typography variant="caption" display="block" color="text.secondary">
                                          ({formatCurrency(transaction.value, portfolio?.base_currency)})
                                        </Typography>
                                      )}
                                    </TableCell>
                                    <TableCell align="right">
                                      {transaction.transaction_type === 'BUY' && (
                                        <Box>
                                          {/* Show gain/loss in transaction currency */}
                                          <Typography
                                            variant="body2"
                                            color={transaction.gain_loss >= 0 ? 'success.main' : 'error.main'}
                                          >
                                            {transaction.gain_loss >= 0 ? '+' : ''}{formatCurrency(Math.abs(transaction.gain_loss), transaction.currency || portfolio?.base_currency)}
                                          </Typography>
                                          <Typography
                                            variant="caption"
                                            color={transaction.gain_loss >= 0 ? 'success.main' : 'error.main'}
                                          >
                                            {transaction.gain_loss >= 0 ? '+' : ''}{transaction.gain_loss_percentage.toFixed(2)}%
                                          </Typography>
                                          {/* Show converted gain/loss if different currency */}
                                          {transaction.currency && transaction.currency !== portfolio?.base_currency && (
                                            <Typography variant="caption" display="block" color="text.secondary">
                                              ({transaction.gain_loss >= 0 ? '+' : ''}{formatCurrency(Math.abs(transaction.gain_loss_base_currency || (transaction.gain_loss * (transaction.exchange_rate || 1))), portfolio?.base_currency)})
                                            </Typography>
                                          )}
                                        </Box>
                                      )}
                                      {transaction.transaction_type === 'DIVIDEND' && (
                                        <Typography variant="body2" color="info.main">
                                          +{formatCurrency(transaction.value, portfolio?.base_currency)}
                                        </Typography>
                                      )}
                                      {transaction.transaction_type === 'SELL' && (
                                        <Typography variant="body2" color="text.secondary">
                                          Sold
                                        </Typography>
                                      )}
                                      {transaction.transaction_type === 'SPLIT' && (
                                        <Typography variant="body2" color="text.secondary">
                                          -
                                        </Typography>
                                      )}
                                    </TableCell>
                                    <TableCell align="center">
                                      <Tooltip title="Delete Transaction">
                                        <IconButton
                                          size="small"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteTransaction(transaction.id, asset.name);
                                          }}
                                          color="error"
                                        >
                                          <DeleteIcon fontSize="small" />
                                        </IconButton>
                                      </Tooltip>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Action Buttons */}
      <Box sx={{ mt: 3 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleOpenNewTransactionModal}
        >
          Add New Transaction
        </Button>
      </Box>

      {/* Transaction Form Modal */}
      <TransactionForm
        open={showTransactionForm}
        onClose={() => {
          setShowTransactionForm(false);
          setSelectedSecurity(null);
        }}
        portfolioId={portfolioId}
        security={selectedSecurity}
        onSuccess={handleTransactionSuccess}
        existingHoldings={getHoldingsMap()}
        portfolio={portfolio}
      />
    </Container>
  );
};

export default ConsolidatedPortfolioDetails;