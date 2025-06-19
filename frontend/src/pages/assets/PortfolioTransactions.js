import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import StockAutocomplete from '../../components/StockAutocomplete';

const PortfolioTransactions = () => {
  const { portfolioId } = useParams();
  const navigate = useNavigate();
  const [portfolio, setPortfolio] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({
    security_id: null,
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    transaction_date: '',
    fees: '0',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, [portfolioId]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch portfolio details
      const portfolioResponse = await api.portfolios.get(portfolioId);
      setPortfolio(portfolioResponse.data);

      // Fetch transactions for this portfolio
      const transactionsResponse = await api.transactions.getAll({ portfolio_id: portfolioId });
      setTransactions(transactionsResponse.data);

      // Fetch categories
      const categoriesResponse = await api.categories.getAll();
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
      const transactionData = {
        portfolio: portfolioId,
        security: formData.security_id,
        transaction_type: formData.transaction_type,
        transaction_date: formData.transaction_date,
        quantity: parseFloat(formData.quantity),
        price: parseFloat(formData.price),
        fees: parseFloat(formData.fees) || 0,
        notes: formData.notes || ''
      };

      await api.transactions.create(transactionData);

      setShowAddModal(false);
      resetForm();

      // Navigate back to portfolio details
      navigate(`/portfolios/${portfolioId}`);
    } catch (err) {
      console.error('Full error details:', err);

      let errorMessage = 'Failed to save transaction';
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

  const resetForm = () => {
    setFormData({
      security_id: null,
      transaction_type: 'BUY',
      quantity: '',
      price: '',
      transaction_date: '',
      fees: '0',
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

  // For now, just show the add transaction form
  // Since we're coming here to add a new transaction
  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Portfolio Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          Add Transaction - {portfolio?.name}
        </h1>
        <p className="text-gray-600">{portfolio?.description}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Transaction Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">New Transaction</h2>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Security
              </label>
              <StockAutocomplete
                onSelectStock={(security) => {
                  setFormData(prev => ({
                    ...prev,
                    security_id: security.id
                  }));
                }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Transaction Type
              </label>
              <select
                name="transaction_type"
                value={formData.transaction_type}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="BUY">Buy</option>
                <option value="SELL">Sell</option>
                <option value="DIVIDEND">Dividend</option>
              </select>
            </div>

            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2">
                Quantity
              </label>
              <input
                type="number"
                step="0.00000001"
                name="quantity"
                value={formData.quantity}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2">
                Price per Share
              </label>
              <input
                type="number"
                step="0.0001"
                name="price"
                value={formData.price}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2">
                Transaction Date
              </label>
              <input
                type="date"
                name="transaction_date"
                value={formData.transaction_date}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2">
                Fees
              </label>
              <input
                type="number"
                step="0.01"
                name="fees"
                value={formData.fees}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
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
          </div>

          <div className="flex justify-end space-x-2 mt-6">
            <button
              type="button"
              onClick={() => navigate(`/portfolios/${portfolioId}`)}
              className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
            >
              Add Transaction
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PortfolioTransactions;