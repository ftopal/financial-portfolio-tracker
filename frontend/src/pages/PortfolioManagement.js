import React, { useState, useEffect } from 'react';
import api from '../services/api';  // Changed import

const PortfolioManagement = () => {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingPortfolio, setEditingPortfolio] = useState(null);
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
      const response = await api.portfolios.getAll();  // Changed from getPortfolios()
      setPortfolios(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load portfolios');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this portfolio?')) {
      try {
        await api.portfolios.delete(id);  // Changed from deletePortfolio(id)
        fetchPortfolios();
      } catch (err) {
        setError('Failed to delete portfolio');
        console.error(err);
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingPortfolio) {
        await api.portfolios.update(editingPortfolio.id, formData);  // Changed from updatePortfolio()
      } else {
        await api.portfolios.create(formData);  // Changed from createPortfolio()
      }
      setShowCreateModal(false);
      setEditingPortfolio(null);
      setFormData({ name: '', description: '' });
      fetchPortfolios();
    } catch (err) {
      setError('Failed to save portfolio');
      console.error(err);
    }
  };

  const handleEdit = (portfolio) => {
    setEditingPortfolio(portfolio);
    setFormData({
      name: portfolio.name,
      description: portfolio.description
    });
    setShowCreateModal(true);
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
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
        <h1 className="text-3xl font-bold text-gray-900">Portfolio Management</h1>
        <button
          onClick={() => {
            setShowCreateModal(true);
            setEditingPortfolio(null);
            setFormData({ name: '', description: '' });
          }}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          Create Portfolio
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {portfolios.map((portfolio) => (
          <div key={portfolio.id} className="bg-white shadow rounded-lg p-6">
            <h3 className="text-xl font-semibold mb-2">{portfolio.name}</h3>
            <p className="text-gray-600 mb-4">{portfolio.description || 'No description'}</p>
            <div className="text-sm text-gray-500 mb-4">
              <p>Assets: {portfolio.asset_count || 0}</p>
              <p>Total Value: ${portfolio.total_value?.toFixed(2) || '0.00'}</p>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => handleEdit(portfolio)}
                className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm"
              >
                Edit
              </button>
              <button
                onClick={() => handleDelete(portfolio.id)}
                className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Create/Edit Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-2xl font-bold mb-4">
              {editingPortfolio ? 'Edit Portfolio' : 'Create Portfolio'}
            </h2>
            <form onSubmit={handleSubmit}>
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
                  onClick={() => setShowCreateModal(false)}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                  {editingPortfolio ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioManagement;