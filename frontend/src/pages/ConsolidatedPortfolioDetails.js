import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, TrendingUp, TrendingDown, Trash2 } from 'lucide-react';
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

  // Function to handle Add Transaction from expanded row
  const handleAddTransactionForSecurity = (asset) => {
    // Get the first transaction to extract security ID
    const firstTransaction = asset.transactions && asset.transactions.length > 0
      ? asset.transactions[0]
      : null;

    // Set selected security with all necessary information
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

  // Function to handle transaction deletion
  const handleDeleteTransaction = async (transactionId, securityName) => {
    if (window.confirm(`Are you sure you want to delete this transaction for ${securityName}?`)) {
      try {
        await api.transactions.delete(transactionId);
        // Refresh the data after successful deletion
        fetchConsolidatedData();
      } catch (err) {
        console.error('Error deleting transaction:', err);
        alert('Failed to delete transaction. Please try again.');
      }
    }
  };

  // Function to handle opening modal for new transaction
  const handleOpenNewTransactionModal = () => {
    setSelectedSecurity(null);
    setShowTransactionForm(true);
  };

  // Function to handle transaction success
  const handleTransactionSuccess = () => {
    setShowTransactionForm(false);
    setSelectedSecurity(null);
    fetchConsolidatedData(); // Refresh the data
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
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
      // Handle different date formats
      let date;
      if (dateString.includes('T')) {
        // ISO format with time
        date = new Date(dateString);
      } else {
        // Just date, assume UTC to avoid timezone issues
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

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error && !portfolio) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
        <Link to="/portfolios" className="text-blue-600 hover:text-blue-800">
          ← Back to Portfolios
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <Link to="/portfolios" className="text-blue-600 hover:text-blue-800 text-sm">
          ← Back to Portfolios
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">
          {portfolio?.name || 'Portfolio Details'}
        </h1>
        {portfolio?.description && (
          <p className="text-gray-600 mt-2">{portfolio.description}</p>
        )}
      </div>

      {/* Two-column layout for summary and currency view */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Summary Cards Section */}
        <div>
          {summary && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Total Value</h3>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.total_value)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Securities + Cash
                </p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Securities Value</h3>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.securities_value || summary.total_value)}
                </p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Cash Balance</h3>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.cash_balance || 0)}
                </p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Total Gain/Loss</h3>
                <p className={`text-2xl font-bold ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(summary.total_gain_loss)}
                </p>
                <p className={`text-sm ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {summary.total_cost > 0 ? formatPercentage((summary.total_gain_loss / summary.total_cost) * 100) : '0.00%'}
                </p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow col-span-2">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Total Dividends</h3>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.total_dividends || 0)}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Currency View Section */}
        <div>
          {portfolio && (
            <PortfolioCurrencyView portfolio={portfolio} />
          )}
        </div>
      </div>

      {/* Cash Management Section */}
      {cashAccount && (
        <div className="mb-8">
          <CashManagement
            portfolioId={portfolioId}
            cashBalance={cashAccount.balance}
            currency={cashAccount.currency}
            onBalanceUpdate={fetchConsolidatedData}
          />
        </div>
      )}

      {/* Consolidated Assets Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            Securities Holdings
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Click on any row to see individual transactions
          </p>
        </div>

        {consolidatedAssets.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-gray-500">No securities in this portfolio yet.</p>
            <p className="text-gray-500 mt-2">Add securities to start tracking your investments.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Asset
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quantity
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Avg Cost
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Current Price
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Value
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Gain/Loss
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {consolidatedAssets.map((asset) => (
                  <React.Fragment key={asset.key}>
                    <tr
                      onClick={() => toggleRow(asset.key)}
                      className="hover:bg-gray-50 cursor-pointer"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="mr-3">
                            {expandedRows[asset.key] ?
                              <ChevronDown className="w-5 h-5 text-gray-400" /> :
                              <ChevronRight className="w-5 h-5 text-gray-400" />
                            }
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {asset.symbol ? `${asset.symbol} - ${asset.name}` : asset.name}
                            </div>
                            <div className="text-sm text-gray-500">
                              {asset.asset_type} • {asset.transactions.length} transaction{asset.transactions.length > 1 ? 's' : ''}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {asset.total_quantity.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {formatCurrency(asset.avg_cost_price)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {formatCurrency(asset.current_price)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                        {formatCurrency(asset.total_current_value)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <div className={`text-sm font-medium ${asset.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          <div className="flex items-center justify-end">
                            {asset.total_gain_loss >= 0 ? (
                              <TrendingUp className="w-4 h-4 mr-1" />
                            ) : (
                              <TrendingDown className="w-4 h-4 mr-1" />
                            )}
                            {formatCurrency(Math.abs(asset.total_gain_loss))}
                          </div>
                          <div className="text-xs">
                            {(() => {
                              // Calculate percentage from gain/loss and total cost
                              const totalCost = asset.avg_cost_price * asset.total_quantity;
                              const percentage = totalCost > 0 ? (asset.total_gain_loss / totalCost) * 100 : 0;
                              return formatPercentage(percentage);
                            })()}
                          </div>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded Row - Transactions */}
                    {expandedRows[asset.key] && (
                      <tr>
                        <td colSpan="6" className="px-6 py-4 bg-gray-50">
                          <div className="mb-3 flex justify-between items-center">
                            <h4 className="text-sm font-medium text-gray-700">Transaction History</h4>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAddTransactionForSecurity(asset);
                              }}
                              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                            >
                              + Add Transaction
                            </button>
                          </div>
                          <div className="overflow-hidden">
                            <table className="min-w-full">
                              <thead>
                                <tr className="text-xs text-gray-500 uppercase">
                                  <th className="text-left py-2">Date</th>
                                  <th className="text-left py-2">Type</th>
                                  <th className="text-right py-2">Quantity</th>
                                  <th className="text-right py-2">Price</th>
                                  <th className="text-right py-2">Total</th>
                                  <th className="text-right py-2">Gain/Loss</th>
                                  <th className="text-right py-2">Action</th>
                                </tr>
                              </thead>
                              <tbody className="text-sm">
                                {asset.transactions.map((transaction) => (
                                  <tr key={transaction.id} className="border-t border-gray-200">
                                    <td className="py-2">{formatDate(transaction.date || transaction.transaction_date)}</td>
                                    <td className="py-2">
                                      <span className={`px-2 py-1 rounded text-xs ${
                                        transaction.transaction_type === 'BUY' ? 'bg-green-100 text-green-800' :
                                        transaction.transaction_type === 'SELL' ? 'bg-red-100 text-red-800' :
                                        transaction.transaction_type === 'DIVIDEND' ? 'bg-blue-100 text-blue-800' :
                                        transaction.transaction_type === 'SPLIT' ? 'bg-purple-100 text-purple-800' :
                                        'bg-gray-100 text-gray-800'
                                      }`}>
                                        {transaction.transaction_type}
                                      </span>
                                    </td>
                                    <td className="text-right py-2">{transaction.quantity}</td>
                                    <td className="text-right py-2">{formatCurrency(transaction.price)}</td>
                                    <td className="text-right py-2">{formatCurrency(transaction.value)}</td>
                                    <td className={`text-right py-2 font-medium ${
                                      transaction.transaction_type === 'DIVIDEND' ? 'text-blue-600' :
                                      transaction.transaction_type === 'SELL' ? 'text-gray-600' :
                                      transaction.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'
                                    }`}>
                                      {transaction.transaction_type === 'DIVIDEND' ? (
                                        <span className="text-blue-600">+{formatCurrency(transaction.value)}</span>
                                      ) : transaction.transaction_type === 'SELL' ? (
                                        <span className="text-gray-600">Sold</span>
                                      ) : (
                                        <>
                                          {formatCurrency(transaction.gain_loss || 0)}
                                          {transaction.gain_loss_percentage !== undefined && transaction.gain_loss_percentage !== null && (
                                            <div className="text-xs">
                                              {formatPercentage(transaction.gain_loss_percentage)}
                                            </div>
                                          )}
                                        </>
                                      )}
                                    </td>
                                    <td className="text-right py-2">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeleteTransaction(transaction.id, asset.name);
                                        }}
                                        className="text-red-600 hover:text-red-800 transition-colors"
                                        title="Delete transaction"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Action Buttons - Updated */}
      <div className="mt-6 flex space-x-4">
        <button
          onClick={handleOpenNewTransactionModal}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md"
        >
          Add New Transaction
        </button>
      </div>

      {/* Use TransactionForm instead of inline modal */}
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
      />
    </div>
  );
};

export default ConsolidatedPortfolioDetails;