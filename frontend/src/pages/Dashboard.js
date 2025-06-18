import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';  // Changed import

const Dashboard = () => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSummary();
  }, []);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getSummary();  // Changed from getPortfolioSummary()
      setSummary(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load portfolio summary');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    // Add safety check for undefined/null values
    if (amount === undefined || amount === null) {
      return '$0.00';
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatPercentage = (value) => {
    // Add safety check
    if (value === undefined || value === null) {
      return '0.00%';
    }
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
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
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    );
  }

  // Use optional chaining and default values
  const totals = summary?.totals || {};
  const assetBreakdown = summary?.asset_breakdown || [];

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Portfolio Dashboard</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Value</h3>
          <p className="text-2xl font-bold text-gray-900">
            {formatCurrency(totals.total_value)}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Cost</h3>
          <p className="text-2xl font-bold text-gray-900">
            {formatCurrency(totals.total_cost)}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Gain/Loss</h3>
          <p className={`text-2xl font-bold ${
            (totals.total_gain_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatCurrency(totals.total_gain_loss)}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Return %</h3>
          <p className={`text-2xl font-bold ${
            (totals.gain_loss_percentage || 0) >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatPercentage(totals.gain_loss_percentage)}
          </p>
        </div>
      </div>

      {/* Asset Breakdown */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Asset Breakdown by Type</h2>

        {assetBreakdown.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No assets to display</p>
        ) : (
          <div className="space-y-4">
            {assetBreakdown.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center">
                  <span className="text-sm font-medium text-gray-900">
                    {item.asset_type}
                  </span>
                  <span className="ml-2 text-sm text-gray-500">
                    ({item.count} {item.count === 1 ? 'asset' : 'assets'})
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">
                    {formatCurrency(item.value)}
                  </p>
                  <p className="text-xs text-gray-500">
                    {((item.value / (totals.total_value || 1)) * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="mt-8 flex space-x-4">
        <button
          onClick={() => navigate('/assets')}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          View All Assets
        </button>
        <button
          onClick={() => navigate('/portfolios')}
          className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
        >
          Manage Portfolios
        </button>
      </div>
    </div>
  );
};

export default Dashboard;