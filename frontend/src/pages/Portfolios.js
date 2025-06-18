import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';  // Add Link import
import api from '../services/api';

const Portfolios = () => {
    const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: ''
  });

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getAll();
      setPortfolios(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load portfolios');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePortfolio = async (e) => {
    e.preventDefault();
    try {
      await api.portfolios.create(formData);
      setShowCreateModal(false);
      setFormData({ name: '', description: '' });
      fetchPortfolios();
    } catch (err) {
      setError('Failed to create portfolio');
      console.error(err);
    }
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount || 0);
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
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">My Portfolios</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          Create New Portfolio
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {portfolios.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <h3 className="text-lg font-medium text-gray-500 mb-2">
            No portfolios yet
          </h3>
          <p className="text-gray-400">Create your first portfolio to start tracking your investments.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {portfolios.map((portfolio) => (
            <div
              key={portfolio.id}
              className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
            >
              {/* Make portfolio name a clickable link */}
              <Link
                to={`/portfolios/${portfolio.id}`}
                className="text-xl font-semibold mb-2 text-blue-600 hover:text-blue-800 block"
              >
                {portfolio.name}
              </Link>

              <p className="text-gray-600 mb-4">{portfolio.description || 'No description'}</p>

              <div className="border-t pt-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Assets</span>
                  <span className="font-semibold">{portfolio.asset_count || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Transaction</span>
                  <span className="font-semibold">{portfolio.transaction_count || 0}</span>
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-gray-500">Total Value</span>
                  <span className="font-semibold">{formatCurrency(portfolio.total_value)}</span>
                </div>
              </div>

              <div className="mt-4 flex space-x-2">
                <Link
                  to={`/portfolios/${portfolio.id}`}
                  className="flex-1 bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm text-center"
                >
                  View Details
                </Link>
                <Link
                  to={`/portfolios/${portfolio.id}/assets`}
                  className="flex-1 bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-sm text-center"
                >
                  Manage Assets
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Portfolio Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-2xl font-bold mb-4">Create New Portfolio</h2>
            <form onSubmit={handleCreatePortfolio}>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Portfolio Name
                </label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Description
                </label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                  rows="3"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setFormData({ name: '', description: '' });
                  }}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Portfolios;