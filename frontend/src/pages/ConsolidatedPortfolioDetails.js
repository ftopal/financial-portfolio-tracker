import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, TrendingUp, TrendingDown } from 'lucide-react';
import api from '../services/api';

const ConsolidatedPortfolioDetails = () => {
  const { portfolioId } = useParams();
  const [portfolio, setPortfolio] = useState(null);
  const [consolidatedAssets, setConsolidatedAssets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedRows, setExpandedRows] = useState({});

  // Add new state for transaction modal
  const [showAddTransactionModal, setShowAddTransactionModal] = useState(false);
  const [selectedAssetForTransaction, setSelectedAssetForTransaction] = useState(null);
  const [transactionForm, setTransactionForm] = useState({
    quantity: '',
    purchase_price: '',
    purchase_date: '',
    notes: ''
  });

  useEffect(() => {
    fetchConsolidatedData();
  }, [portfolioId]);

  const fetchConsolidatedData = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getConsolidatedView(portfolioId);
      setPortfolio(response.data.portfolio);
      setConsolidatedAssets(response.data.consolidated_assets);
      setSummary(response.data.summary);
      setError('');
    } catch (err) {
      console.error('Error fetching consolidated data:', err);
      setError('Failed to load portfolio data');
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (key) => {
    setExpandedRows(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleAddTransaction = (asset) => {
    setSelectedAssetForTransaction(asset);
    setTransactionForm({
      quantity: '',
      purchase_price: '',
      purchase_date: '',
      notes: ''
    });
    setShowAddTransactionModal(true);
  };

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();

    try {
      const assetData = {
        stock_id: selectedAssetForTransaction.transactions[0]?.stock_id || null,
        portfolio: portfolioId,
        symbol: selectedAssetForTransaction.symbol,
        name: selectedAssetForTransaction.name,
        asset_type: selectedAssetForTransaction.asset_type,
        quantity: parseFloat(transactionForm.quantity),
        purchase_price: parseFloat(transactionForm.purchase_price),
        purchase_date: transactionForm.purchase_date,
        notes: transactionForm.notes || '',
      };

      await api.assets.create(assetData);

      // Close modal and refresh data
      setShowAddTransactionModal(false);
      setTransactionForm({
        quantity: '',
        purchase_price: '',
        purchase_date: '',
        notes: ''
      });
      fetchConsolidatedData(); // Refresh the data

    } catch (err) {
      console.error('Error adding transaction:', err);
      setError('Failed to add transaction');
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

  if (error) {
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
          {portfolio?.name}
        </h1>
        {portfolio?.description && (
          <p className="text-gray-600 mt-2">{portfolio.description}</p>
        )}
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
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
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Transactions</h3>
            <p className="text-2xl font-bold text-gray-900">
              {summary.total_transactions}
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
          <div className="p-12 text-center">
            <p className="text-gray-500">No assets in this portfolio yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Asset
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Quantity
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Avg Cost Price
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Current Price
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Value
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Gain/Loss
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {consolidatedAssets.map((asset) => (
                  <React.Fragment key={asset.key}>
                    {/* Main row */}
                    <tr
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => toggleRow(asset.key)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="mr-2">
                            {expandedRows[asset.key] ?
                              <ChevronDown className="w-4 h-4 text-gray-400" /> :
                              <ChevronRight className="w-4 h-4 text-gray-400" />
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
                                  handleAddTransaction(asset);
                                }}
                                className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm font-medium"
                              >
                                Add Transaction
                              </button>
                            </div>
                            <table className="min-w-full">
                              <thead>
                                <tr className="text-xs text-gray-500">
                                  <th className="text-left pb-2">Purchase Date</th>
                                  <th className="text-right pb-2">Quantity</th>
                                  <th className="text-right pb-2">Purchase Price</th>
                                  <th className="text-right pb-2">Current Price</th>
                                  <th className="text-right pb-2">Value</th>
                                  <th className="text-right pb-2">Gain/Loss</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-200">
                                {asset.transactions.map((transaction, idx) => (
                                  <tr key={idx} className="text-sm">
                                    <td className="py-2">{formatDate(transaction.purchase_date)}</td>
                                    <td className="text-right py-2">{transaction.quantity.toLocaleString()}</td>
                                    <td className="text-right py-2">{formatCurrency(transaction.purchase_price)}</td>
                                    <td className="text-right py-2">{formatCurrency(transaction.current_price)}</td>
                                    <td className="text-right py-2">{formatCurrency(transaction.value)}</td>
                                    <td className={`text-right py-2 ${transaction.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                      {formatCurrency(transaction.gain_loss)}
                                      <div className="text-xs">
                                        {formatPercentage(transaction.gain_loss_percentage)}
                                      </div>
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
        <Link
          to={`/portfolios/${portfolioId}/assets`}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md"
        >
          Add Asset
        </Link>
      </div>

      {/* Add Transaction Modal */}
      {showAddTransactionModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Add Transaction for {selectedAssetForTransaction?.name}
            </h3>

            <form onSubmit={handleTransactionSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quantity *
                  </label>
                  <input
                    type="number"
                    step="0.00000001"
                    required
                    value={transactionForm.quantity}
                    onChange={(e) => setTransactionForm({...transactionForm, quantity: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Purchase Price *
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    required
                    value={transactionForm.purchase_price}
                    onChange={(e) => setTransactionForm({...transactionForm, purchase_price: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Purchase Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={transactionForm.purchase_date}
                    onChange={(e) => setTransactionForm({...transactionForm, purchase_date: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notes
                  </label>
                  <textarea
                    rows="3"
                    value={transactionForm.notes}
                    onChange={(e) => setTransactionForm({...transactionForm, notes: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowAddTransactionModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md"
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