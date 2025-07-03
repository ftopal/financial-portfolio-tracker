import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle } from 'lucide-react';
import api from '../services/api';
import PortfolioDialog from '../components/PortfolioDialog';
import { extractDataArray } from '../utils/apiHelpers';

const Portfolios = () => {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedPortfolio, setSelectedPortfolio] = useState(null);

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getAll();
      const portfoliosData = extractDataArray(response);
      setPortfolios(portfoliosData);
      setError('');
    } catch (err) {
      setError('Failed to load portfolios');
      console.error(err);
      setPortfolios([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePortfolio = () => {
    setSelectedPortfolio(null);
    setDialogOpen(true);
  };

  const handleEditPortfolio = (portfolio) => {
    setSelectedPortfolio(portfolio);
    setDialogOpen(true);
  };

  const handleDeletePortfolio = async (id) => {
    if (window.confirm('Are you sure you want to delete this portfolio?')) {
      try {
        await api.portfolios.delete(id);
        fetchPortfolios();
      } catch (err) {
        console.error(err);
        alert('Failed to delete portfolio');
      }
    }
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedPortfolio(null);
    fetchPortfolios();
  };

  // Updated formatCurrency to accept and use the portfolio's base currency
  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  const formatPercentage = (value) => {
    if (!value) return '0.00%';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
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
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">My Portfolios</h1>
        <button
          onClick={handleCreatePortfolio}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg flex items-center"
        >
          <PlusCircle className="mr-2 h-5 w-5" />
          Create Portfolio
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
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded ml-2">
                  {portfolio.base_currency || 'USD'}
                </span>
              </Link>

              <p className="text-gray-600 mb-4">{portfolio.description || 'No description'}</p>

              <div className="border-t pt-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Assets</span>
                  <span className="font-semibold">{portfolio.asset_count || 0}</span>
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-gray-500">Transactions</span>
                  <span className="font-semibold">{portfolio.transaction_count || 0}</span>
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-gray-500">Total Value</span>
                  {/* Use portfolio's base_currency for formatting */}
                  <span className="font-semibold">{formatCurrency(portfolio.total_value, portfolio.base_currency || 'USD')}</span>
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-gray-500">Total Gain/Loss</span>
                  <span className={`font-semibold ${portfolio.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {/* Use portfolio's base_currency for formatting */}
                    {formatCurrency(portfolio.total_gain_loss, portfolio.base_currency || 'USD')}
                    <span className="text-xs ml-1">
                      ({formatPercentage(portfolio.gain_loss_percentage)})
                    </span>
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t flex justify-between">
                <button
                  onClick={() => handleEditPortfolio(portfolio)}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDeletePortfolio(portfolio.id)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <PortfolioDialog
        open={dialogOpen}
        onClose={handleDialogClose}
        portfolio={selectedPortfolio}
      />
    </div>
  );
};

export default Portfolios;