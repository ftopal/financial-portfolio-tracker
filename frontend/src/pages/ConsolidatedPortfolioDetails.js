
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, TrendingUp, TrendingDown, Trash2 } from 'lucide-react';
import api from '../services/api';
import StockAutocomplete from '../components/StockAutocomplete';

const ConsolidatedPortfolioDetails = () => {
  const { portfolioId } = useParams();
  const [portfolio, setPortfolio] = useState(null);
  const [consolidatedAssets, setConsolidatedAssets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedRows, setExpandedRows] = useState({});
  const [selectedSecurity, setSelectedSecurity] = useState(null);

  // Add new state for transaction modal
  const [showAddNewTransactionModal, setShowAddNewTransactionModal] = useState(false);
  const [newTransactionForm, setNewTransactionForm] = useState({
    security_id: null,
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    transaction_date: new Date().toISOString().split('T')[0], // Default to today
    fees: '0',
    notes: '',
    dividend_per_share: '' // Add this field for dividends
  });

  const fetchConsolidatedData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getConsolidatedView(portfolioId);

      setPortfolio(response.data.portfolio || {});
      setConsolidatedAssets(response.data.consolidated_assets || []);
      setSummary(response.data.summary || {});
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

  // New function to handle Add Transaction from expanded row
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
      total_quantity: asset.total_quantity // Add total quantity to selected security
    });

    // Pre-fill the form with security information
    setNewTransactionForm({
      security_id: firstTransaction ? firstTransaction.stock_id : null,
      transaction_type: 'BUY',
      quantity: '',
      price: asset.current_price ? asset.current_price.toString() : '',
      transaction_date: new Date().toISOString().split('T')[0],
      fees: '0',
      notes: '',
      dividend_per_share: ''
    });

    setShowAddNewTransactionModal(true);
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

  // Updated function to handle opening modal for new transaction
  const handleOpenNewTransactionModal = () => {
    // Reset selected security when opening from main button
    setSelectedSecurity(null);
    setNewTransactionForm({
      security_id: null,
      transaction_type: 'BUY',
      quantity: '',
      price: '',
      transaction_date: new Date().toISOString().split('T')[0],
      fees: '0',
      notes: '',
      dividend_per_share: ''
    });
    setShowAddNewTransactionModal(true);
  };

  const handleNewTransactionSubmit = async (e) => {
    e.preventDefault();

    try {
      let transactionData = {
        portfolio: portfolioId,
        security: newTransactionForm.security_id,
        transaction_type: newTransactionForm.transaction_type,
        transaction_date: newTransactionForm.transaction_date,
        quantity: parseFloat(newTransactionForm.quantity),
        fees: parseFloat(newTransactionForm.fees) || 0,
        notes: newTransactionForm.notes || ''
      };

      // Handle dividend transactions differently
      if (newTransactionForm.transaction_type === 'DIVIDEND') {
        const totalDividend = parseFloat(newTransactionForm.price);
        const quantity = parseFloat(newTransactionForm.quantity);

        // Calculate dividend per share from total amount
        let dividendPerShare = quantity > 0 ? totalDividend / quantity : 0;

        // Round to 4 decimal places to match backend field constraints
        dividendPerShare = Math.round(dividendPerShare * 10000) / 10000;

        // Ensure it doesn't exceed max digits (10 total, 4 decimal = max 999999.9999)
        if (dividendPerShare > 999999.9999) {
          alert('Dividend per share exceeds maximum allowed value. Please check your input.');
          return;
        }

        transactionData.dividend_per_share = dividendPerShare;
        // For dividends, the 'price' field should be the dividend per share
        transactionData.price = dividendPerShare;
      } else {
        // For BUY/SELL transactions, price is price per share
        transactionData.price = parseFloat(newTransactionForm.price);
      }

      console.log('Sending transaction data:', transactionData); // Debug log

      await api.transactions.create(transactionData);

      // Close modal and refresh data
      setShowAddNewTransactionModal(false);
      setSelectedSecurity(null);
      setNewTransactionForm({
        security_id: null,
        transaction_type: 'BUY',
        quantity: '',
        price: '',
        transaction_date: new Date().toISOString().split('T')[0],
        fees: '0',
        notes: '',
        dividend_per_share: ''
      });
      fetchConsolidatedData(); // Refresh the data

    } catch (err) {
      console.error('Error adding transaction:', err);
      console.error('Response data:', err.response?.data);

      // Extract error message
      let errorMessage = 'Failed to add transaction';
      if (err.response?.data) {
        if (err.response.data.dividend_per_share) {
          errorMessage = err.response.data.dividend_per_share[0];
        } else if (err.response.data.detail) {
          errorMessage = err.response.data.detail;
        } else if (err.response.data.error) {
          errorMessage = err.response.data.error;
        } else if (typeof err.response.data === 'string') {
          errorMessage = err.response.data;
        }
      }

      alert(errorMessage);
    }
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
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
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

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Value</h3>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(summary.total_value)}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Cost</h3>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(summary.total_cost)}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Gain/Loss</h3>
            <p className={`text-2xl font-bold ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(summary.total_gain_loss)}
            </p>
            <p className={`text-sm ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercentage((summary.total_gain_loss / summary.total_cost) * 100)}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Unique Assets</h3>
            <p className="text-2xl font-bold text-gray-900">
              {summary.unique_assets}
            </p>
          </div>
        </div>
      )}

      {/* Consolidated Assets Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            Consolidated Holdings
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Click on any row to see individual transactions
          </p>
        </div>

        {consolidatedAssets.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-gray-500">No assets in this portfolio yet.</p>
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
                            {asset.total_gain_loss >= 0 ?
                              <TrendingUp className="w-4 h-4 mr-1" /> :
                              <TrendingDown className="w-4 h-4 mr-1" />
                            }
                            {formatCurrency(asset.total_gain_loss)}
                          </div>
                          <div className="text-xs">
                            {formatPercentage(asset.gain_loss_percentage)}
                          </div>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded transactions */}
                    {expandedRows[asset.key] && (
                      <tr>
                        <td colSpan="6" className="px-6 py-4 bg-gray-50">
                          <div className="ml-8">
                            <div className="flex justify-between items-center mb-3">
                              <h4 className="text-sm font-medium text-gray-700">Individual Transactions</h4>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleAddTransactionForSecurity(asset);
                                }}
                                className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm font-medium"
                              >
                                Add Transaction
                              </button>
                            </div>
                            <table className="min-w-full">
                              <thead>
                                <tr className="text-xs text-gray-500">
                                  <th className="text-left pb-2">Date</th>
                                  <th className="text-left pb-2">Type</th>
                                  <th className="text-right pb-2">Quantity</th>
                                  <th className="text-right pb-2">Price</th>
                                  <th className="text-right pb-2">Value</th>
                                  <th className="text-right pb-2">Gain/Loss</th>
                                  <th className="text-right pb-2">Actions</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-200">
                                {asset.transactions.map((transaction, idx) => (
                                  <tr key={idx} className="text-sm">
                                    <td className="py-2">{formatDate(transaction.transaction_date || transaction.purchase_date)}</td>
                                    <td className="py-2">
                                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                                        ${transaction.transaction_type === 'BUY' ? 'bg-green-100 text-green-800' :
                                          transaction.transaction_type === 'SELL' ? 'bg-red-100 text-red-800' :
                                          transaction.transaction_type === 'DIVIDEND' ? 'bg-blue-100 text-blue-800' :
                                          'bg-gray-100 text-gray-800'}`}>
                                        {transaction.transaction_type}
                                      </span>
                                    </td>
                                    <td className="text-right py-2">{transaction.quantity.toLocaleString()}</td>
                                    <td className="text-right py-2">
                                      {transaction.transaction_type === 'DIVIDEND'
                                        ? transaction.dividend_per_share
                                          ? formatCurrency(transaction.dividend_per_share) + '/share'
                                          : '-'
                                        : formatCurrency(transaction.price || transaction.purchase_price)
                                      }
                                    </td>
                                    <td className="text-right py-2">{formatCurrency(transaction.value)}</td>
                                    <td className={`text-right py-2 ${
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
                                          {transaction.gain_loss_percentage !== undefined && (
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

      {/* Add New Transaction Modal */}
      {showAddNewTransactionModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white rounded-lg p-6 w-full max-w-md my-8">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Add New Transaction
            </h3>

            <form onSubmit={handleNewTransactionSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Security *
                  </label>
                  {selectedSecurity ? (
                    // Show pre-selected security info
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-medium text-gray-900">{selectedSecurity.symbol} - {selectedSecurity.name}</p>
                          <p className="text-sm text-gray-600">{selectedSecurity.security_type}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedSecurity(null);
                            setNewTransactionForm({
                              ...newTransactionForm,
                              security_id: null,
                              price: '',
                              dividend_per_share: ''
                            });
                          }}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          Change
                        </button>
                      </div>
                    </div>
                  ) : (
                    // Show autocomplete for selecting security
                    <StockAutocomplete
                      onSelectStock={(security) => {
                        // Try to find if we already have this security in our portfolio
                        const existingAsset = consolidatedAssets.find(
                          asset => asset.symbol === security.symbol
                        );

                        const securityWithQuantity = {
                          ...security,
                          total_quantity: existingAsset ? existingAsset.total_quantity : 0
                        };

                        setSelectedSecurity(securityWithQuantity);
                        setNewTransactionForm({
                          ...newTransactionForm,
                          security_id: security.id,
                          price: security.current_price ? security.current_price.toString() : '',
                          dividend_per_share: '',
                          // Auto-fill quantity if it's a dividend transaction
                          quantity: newTransactionForm.transaction_type === 'DIVIDEND' && existingAsset
                            ? existingAsset.total_quantity.toString()
                            : newTransactionForm.quantity
                        });
                      }}
                    />
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transaction Type *
                  </label>
                  <select
                    value={newTransactionForm.transaction_type}
                    onChange={(e) => {
                      const newType = e.target.value;
                      setNewTransactionForm({
                        ...newTransactionForm,
                        transaction_type: newType,
                        // Auto-fill quantity for dividends if we have a selected security
                        quantity: newType === 'DIVIDEND' && selectedSecurity?.total_quantity
                          ? selectedSecurity.total_quantity.toString()
                          : newTransactionForm.quantity
                      });
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                    <option value="DIVIDEND">Dividend</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quantity *
                  </label>
                  <input
                    type="number"
                    step="0.00000001"
                    required
                    value={newTransactionForm.quantity}
                    onChange={(e) => setNewTransactionForm({
                      ...newTransactionForm,
                      quantity: e.target.value
                    })}
                    placeholder={newTransactionForm.transaction_type === 'DIVIDEND' ? "Number of shares owned" : "Number of shares"}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {newTransactionForm.transaction_type === 'DIVIDEND' && (
                    <p className="text-xs text-gray-500 mt-1">
                      {selectedSecurity?.total_quantity > 0
                        ? `Auto-filled with your current holding of ${selectedSecurity.total_quantity} shares`
                        : "Enter the number of shares you own"}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {newTransactionForm.transaction_type === 'DIVIDEND' ? 'Total Dividend Amount *' : 'Price per Share/Unit *'}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={newTransactionForm.price}
                    onChange={(e) => setNewTransactionForm({
                      ...newTransactionForm,
                      price: e.target.value
                    })}
                    placeholder={newTransactionForm.transaction_type === 'DIVIDEND' ? "Total dividend received" : "Price per share"}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {newTransactionForm.transaction_type === 'DIVIDEND' && (
                    <p className="text-xs text-gray-500 mt-1">
                      Enter the total dividend amount you received
                      {newTransactionForm.quantity && newTransactionForm.price && (
                        (() => {
                          const perShare = parseFloat(newTransactionForm.price) / parseFloat(newTransactionForm.quantity);
                          const roundedPerShare = Math.round(perShare * 10000) / 10000;

                          if (roundedPerShare > 999999.9999) {
                            return (
                              <span className="block text-red-600 mt-1">
                                ⚠️ Dividend per share too large. Please check your values.
                              </span>
                            );
                          }

                          return (
                            <span className="block text-blue-600 mt-1">
                              = ${roundedPerShare.toFixed(4)} per share
                            </span>
                          );
                        })()
                      )}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transaction Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={newTransactionForm.transaction_date}
                    onChange={(e) => setNewTransactionForm({
                      ...newTransactionForm,
                      transaction_date: e.target.value
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Fees
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={newTransactionForm.fees}
                    onChange={(e) => setNewTransactionForm({
                      ...newTransactionForm,
                      fees: e.target.value
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notes
                  </label>
                  <textarea
                    rows="3"
                    value={newTransactionForm.notes}
                    onChange={(e) => setNewTransactionForm({
                      ...newTransactionForm,
                      notes: e.target.value
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddNewTransactionModal(false);
                    setSelectedSecurity(null);
                    setNewTransactionForm({
                      security_id: null,
                      transaction_type: 'BUY',
                      quantity: '',
                      price: '',
                      transaction_date: new Date().toISOString().split('T')[0],
                      fees: '0',
                      notes: '',
                      dividend_per_share: ''
                    });
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newTransactionForm.security_id || !newTransactionForm.quantity || !newTransactionForm.price}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  Add Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConsolidatedPortfolioDetails;