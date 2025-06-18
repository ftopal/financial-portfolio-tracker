import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import StockAutocomplete from '../../components/StockAutocomplete';

const PortfolioAssets = () => {
  const { portfolioId } = useParams();
  const navigate = useNavigate();
  const [portfolio, setPortfolio] = useState(null);
  const [assets, setAssets] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingAsset, setEditingAsset] = useState(null);
  const [formData, setFormData] = useState({
    stock_id: null,
    name: '',
    symbol: '',
    asset_type: 'STOCK',
    category: '',
    quantity: '',
    purchase_price: '',
    purchase_date: '',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, [portfolioId]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch portfolio details
      const portfolioResponse = await api.portfolios.get(portfolioId);  // Changed from getPortfolio()
      setPortfolio(portfolioResponse.data);

      // Fetch assets for this portfolio
      const assetsResponse = await api.assets.getAll({ portfolio_id: portfolioId });  // Changed from getAssets()
      setAssets(assetsResponse.data);

      // Fetch categories
      const categoriesResponse = await api.categories.getAll();  // Changed from getCategories()
      setCategories(categoriesResponse.data);

      setError('');
    } catch (err) {
      setError('Failed to load data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const assetData = {
        stock_id: formData.stock_id,  // Add this
        portfolio: portfolioId,
        quantity: parseFloat(formData.quantity),
        purchase_price: parseFloat(formData.purchase_price),
        purchase_date: formData.purchase_date,
        notes: formData.notes || '',
        category: formData.category || null
      };

      if (editingAsset) {
        await api.assets.update(editingAsset.id, assetData);  // Changed from updateAsset()
      } else {
        await api.assets.create(assetData);  // Changed from createAsset()
      }

      setShowAddModal(false);
      setEditingAsset(null);
      resetForm();
      fetchData();
    } catch (err) {
      console.error('Full error details:', err);

      // Log the actual response data
      if (err.response) {
        console.log('Backend error status:', err.response.status);
        console.log('Backend error data:', err.response.data);
      }

      // Better error handling
      let errorMessage = 'Failed to save asset';
      if (err.response && err.response.data) {
        const errorData = err.response.data;

        if (typeof errorData === 'object') {
          errorMessage = Object.entries(errorData)
            .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
            .join('\n');
        } else {
          errorMessage = errorData.toString();
        }
      }

      setError(errorMessage);
    }
  };

  const handleEdit = (asset) => {
    setEditingAsset(asset);
    setFormData({
      name: asset.name,
      symbol: asset.symbol || '',
      asset_type: asset.asset_type,
      category: asset.category || '',
      quantity: asset.quantity.toString(),
      purchase_price: asset.purchase_price.toString(),
      purchase_date: asset.purchase_date,
      notes: asset.notes || ''
    });
    setShowAddModal(true);
  };

  const handleDelete = async (assetId) => {
    if (window.confirm('Are you sure you want to delete this asset?')) {
      try {
        await api.assets.delete(assetId);  // Changed from deleteAsset()
        fetchData();
      } catch (err) {
        setError('Failed to delete asset');
        console.error(err);
      }
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      symbol: '',
      asset_type: 'STOCK',
      category: '',
      quantity: '',
      purchase_price: '',
      purchase_date: '',
      notes: ''
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Portfolio Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          {portfolio?.name} - Assets
        </h1>
        <p className="text-gray-600">{portfolio?.description}</p>
      </div>

      {/* Action Buttons */}
      <div className="flex justify-between mb-6">
        <button
          onClick={() => navigate('/portfolios')}
          className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded"
        >
          Back to Portfolios
        </button>
        <button
          onClick={() => {
            setShowAddModal(true);
            setEditingAsset(null);
            resetForm();
          }}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          Add Asset
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Assets Table */}
      {assets.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <p className="text-gray-500">No assets in this portfolio yet.</p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden rounded-lg">
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
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {asset.name}
                      </div>
                      <div className="text-sm text-gray-500">
                        {asset.symbol} - {asset.asset_type}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                    {parseFloat(asset.quantity).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                    {formatCurrency(asset.purchase_price)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                    {formatCurrency(asset.current_price)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                    {formatCurrency(asset.total_value)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <span className={asset.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                      {formatCurrency(asset.gain_loss)}
                      <br />
                      ({asset.gain_loss_percentage?.toFixed(2)}%)
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleEdit(asset)}
                      className="text-indigo-600 hover:text-indigo-900 mr-3"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(asset.id)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center overflow-y-auto">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl my-8">
            <h2 className="text-2xl font-bold mb-4">
              {editingAsset ? 'Edit Asset' : 'Add Asset'}
            </h2>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <StockAutocomplete
                  onSelectStock={(stock) => {
                    setFormData(prev => ({
                      ...prev,
                      stock_id: stock.id,
                      symbol: stock.symbol,
                      name: stock.name,
                      asset_type: stock.asset_type
                    }));
                  }}
                  assetType={formData.asset_type}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Asset Type
                  </label>
                  <select
                    name="asset_type"
                    value={formData.asset_type}
                    onChange={handleInputChange}
                    disabled={formData.stock_id !== null}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  >
                    <option value="STOCK">Stock</option>
                    <option value="BOND">Bond</option>
                    <option value="CRYPTO">Cryptocurrency</option>
                    <option value="REAL_ESTATE">Real Estate</option>
                    <option value="SAVINGS">Savings Account</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    name="category"
                    value={formData.category}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select Category</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-bold mb-2">
                    Quantity
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    name="quantity"
                    value={formData.quantity}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-bold mb-2">
                    Purchase Price
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    name="purchase_price"
                    value={formData.purchase_price}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-bold mb-2">
                    Purchase Date
                  </label>
                  <input
                    type="date"
                    name="purchase_date"
                    value={formData.purchase_date}
                    onChange={handleInputChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Notes
                </label>
                <textarea
                  name="notes"
                  value={formData.notes}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                  rows="3"
                />
              </div>
              <div className="flex justify-end space-x-2 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    setEditingAsset(null);
                    resetForm();
                  }}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                  {editingAsset ? 'Update' : 'Add'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioAssets;