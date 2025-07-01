import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../services/api';
import StockAutocomplete from '../components/StockAutocomplete';
import {extractDataArray} from "../utils/apiHelpers";


const PortfolioDetails = () => {
  const { portfolioId } = useParams();
  const [portfolio, setPortfolio] = useState(null);
  const [assets, setAssets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddAssetModal, setShowAddAssetModal] = useState(false);
  const [categories, setCategories] = useState([]);
  const [newAsset, setNewAsset] = useState({
    stock_id: null,
    name: '',
    symbol: '',
    asset_type: 'STOCK',
    category: '',
    purchase_price: '',
    quantity: '',
    purchase_date: '',
    notes: ''
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
  const fetchPortfolioDetails = async () => {
    try {
      // Fetch portfolio info
      const portfolioResponse = await api.portfolios.get(portfolioId);
      setPortfolio(portfolioResponse.data);

      // Fetch assets for this portfolio
      const assetsResponse = await api.assets.getAll({ portfolio_id: portfolioId });
      setAssets(assetsResponse.data);

      // Fetch portfolio summary
      const summaryResponse = await api.portfolios.getSummary(portfolioId);
      setSummary(summaryResponse.data.totals);

    } catch (err) {
      console.error('Error fetching portfolio details:', err);
      setError(err.message || 'Failed to fetch portfolio details');
    } finally {
      setLoading(false);
    }
  };

  fetchPortfolioDetails();
  fetchCategories();
}, [portfolioId]);

  const fetchCategories = async () => {
    try {
      const response = await api.categories.getAll();
      const categoriesData = extractDataArray(response);
      setCategories(categoriesData);
    } catch (err) {
      console.error('Error fetching categories:', err);
      setCategories([]);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewAsset(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleCreateAsset = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');

    try {
      // Prepare data with proper types
      const assetData = {
        stock_id: newAsset.stock_id,
        category: newAsset.category ? parseInt(newAsset.category) : null,
        purchase_price: parseFloat(newAsset.purchase_price),
        quantity: parseFloat(newAsset.quantity),
        purchase_date: newAsset.purchase_date,
        notes: newAsset.notes || '',
        portfolio: parseInt(portfolioId)
      };

      console.log('Sending asset data:', assetData);

      const response = await api.assets.create(assetData);  // Use new API
      const createdAsset = response.data;

      console.log('Created asset:', createdAsset);

      // Add the new asset to the list
      setAssets([...assets, createdAsset]);

      // Reset form and close modal
      setNewAsset({
        name: '',
        symbol: '',
        asset_type: 'STOCK',
        category: '',
        purchase_price: '',
        quantity: '',
        purchase_date: '',
        notes: ''
      });
      setShowAddAssetModal(false);

      // Refresh portfolio details to update summary
      fetchPortfolioDetails();

    } catch (err) {
      console.error('Full error details:', err);

      // Better error handling
      let errorMessage = 'Failed to create asset';
      if (err.response && err.response.data) {
        const errorData = err.response.data;
        console.log('Backend error response:', errorData); // Add this to see exact error

        if (typeof errorData === 'object') {
          errorMessage = Object.entries(errorData)
            .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
            .join('; ');
        } else {
          errorMessage = errorData.toString();
        }
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(`Error: ${errorMessage}`);
    } finally {
      setCreating(false);
    }
  };

  const fetchPortfolioDetails = async () => {
    try {
      // Fetch portfolio info
      const portfolioResponse = await api.portfolios.get(portfolioId);  // Use new API
      setPortfolio(portfolioResponse.data);

      // Fetch assets for this portfolio
      const assetsResponse = await api.assets.getAll({ portfolio_id: portfolioId });  // Use new API
      setAssets(assetsResponse.data);

      // Fetch portfolio summary
      const summaryResponse = await api.portfolios.getSummary(portfolioId);  // Use new API
      setSummary(summaryResponse.data.totals);  // Note: summary structure might be different

    } catch (err) {
      console.error('Error fetching portfolio details:', err);
      setError(err.message || 'Failed to fetch portfolio details');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount || 0);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatPercentage = (percentage) => {
    return `${percentage >= 0 ? '+' : ''}${(percentage || 0).toFixed(2)}%`;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error || 'Portfolio not found'}
        </div>
        <Link to="/portfolios" className="text-blue-600 hover:text-blue-800">
          ← Back to Portfolios
        </Link>
      </div>
    );
  }

  // Rest of your component remains the same, but I'll convert the inline styles to Tailwind classes
  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <Link to="/portfolios" className="text-blue-600 hover:text-blue-800 text-sm">
          ← Back to Portfolios
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">
          {portfolio.name}
        </h1>
        {portfolio.description && (
          <p className="text-gray-600 mt-2">
            {portfolio.description}
          </p>
        )}
        <p className="text-gray-500 text-sm mt-1">
          Created: {formatDate(portfolio.created_at)}
        </p>
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
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Invested</h3>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(summary.total_cost)}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Gain/Loss</h3>
            <p className={`text-2xl font-bold ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(summary.total_gain_loss)}
            </p>
            <p className={`text-sm ${summary.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercentage(summary.gain_loss_percentage)}
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Assets</h3>
            <p className="text-2xl font-bold text-gray-900">
              {summary.total_assets}
            </p>
          </div>
        </div>
      )}

      {/* Assets Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-bold text-gray-900">
            Assets ({assets.length})
          </h2>
          <button
            onClick={() => {
              setShowAddAssetModal(true);
              fetchCategories(); // Refresh categories when opening modal
            }}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-medium"
          >
            + Add Asset
          </button>
        </div>

        {assets.length === 0 ? (
          <div className="p-12 text-center">
            <h3 className="text-lg font-medium text-gray-500 mb-2">No assets found</h3>
            <p className="text-gray-400">This portfolio doesn't have any assets yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Asset
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quantity
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Purchase Price
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
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Purchase Date
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {assets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {asset.symbol ? `${asset.symbol} - ${asset.name}` : asset.name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {asset.asset_type}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.category_name || 'Uncategorized'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {parseFloat(asset.quantity).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(asset.purchase_price)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(asset.current_price)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 text-right">
                      {formatCurrency(asset.total_value)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className={`text-sm font-medium ${asset.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(asset.gain_loss)}
                      </div>
                      <div className={`text-xs ${asset.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatPercentage(asset.gain_loss_percentage)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(asset.purchase_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Asset Modal - keeping your existing modal code but with Tailwind classes */}
      {showAddAssetModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Add New Asset
            </h3>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleCreateAsset}>
              <div className="space-y-4">
                <StockAutocomplete
                  onSelectStock={(stock) => {
                    setNewAsset(prev => ({
                      ...prev,
                      stock_id: stock.id,
                      symbol: stock.symbol,
                      name: stock.name,
                      asset_type: stock.asset_type
                    }));
                  }}
                  assetType={newAsset.asset_type}
                />

                {/* Asset Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Asset Type *
                  </label>
                  <select
                    name="asset_type"
                    value={newAsset.asset_type}
                    onChange={handleInputChange}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="STOCK">Stock</option>
                    <option value="BOND">Bond</option>
                    <option value="SAVINGS">Savings Account</option>
                    <option value="CRYPTO">Cryptocurrency</option>
                    <option value="REAL_ESTATE">Real Estate</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                {/* Category */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    name="category"
                    value={newAsset.category}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select Category</option>
                    {categories.map(category => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Purchase Price and Current Price */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Purchase Price *
                    </label>
                    <input
                      type="number"
                      name="purchase_price"
                      step="0.01"
                      required
                      value={newAsset.purchase_price}
                      onChange={handleInputChange}
                      placeholder="0.00"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                {/* Quantity and Purchase Date */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Quantity *
                    </label>
                    <input
                      type="number"
                      name="quantity"
                      step="0.00000001"
                      required
                      value={newAsset.quantity}
                      onChange={handleInputChange}
                      placeholder="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Purchase Date *
                    </label>
                    <input
                      type="date"
                      name="purchase_date"
                      required
                      value={newAsset.purchase_date}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notes
                  </label>
                  <textarea
                    name="notes"
                    rows="3"
                    value={newAsset.notes}
                    onChange={handleInputChange}
                    placeholder="Optional notes about this asset"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Modal Buttons */}
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddAssetModal(false);
                    setNewAsset({
                      name: '',
                      symbol: '',
                      asset_type: 'STOCK',
                      category: '',
                      current_price: '',
                      purchase_price: '',
                      quantity: '',
                      purchase_date: '',
                      notes: ''
                    });
                    setError('');
                  }}
                  disabled={creating}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newAsset.name || !newAsset.purchase_price || !newAsset.quantity || !newAsset.purchase_date}
                  className={`px-4 py-2 rounded-md text-white ${
                    creating || !newAsset.name || !newAsset.purchase_price || !newAsset.quantity || !newAsset.purchase_date
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-green-600 hover:bg-green-700'
                  }`}
                >
                  {creating ? 'Creating...' : 'Create Asset'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioDetails;