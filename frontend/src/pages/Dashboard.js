import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Paper, Typography, Grid, Card, CardContent } from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import api from '../services/api';
import CurrencySelector from '../components/CurrencySelector';
import CurrencyDisplay from '../components/CurrencyDisplay';
import { useCurrency } from '../contexts/CurrencyContext';

const Dashboard = () => {
  const navigate = useNavigate();
  const { displayCurrency, setDisplayCurrency } = useCurrency();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [convertedValues, setConvertedValues] = useState({});

  useEffect(() => {
    fetchSummary();
  }, []);

  useEffect(() => {
    if (summary && displayCurrency !== 'USD') {
      convertSummaryValues();
    }
  }, [displayCurrency, summary]);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      const response = await api.portfolios.getSummary();
      setSummary(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load portfolio summary');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const convertSummaryValues = async () => {
    if (!summary || !summary.portfolios) return;

    try {
      const converted = {};

      // Convert total values
      for (const portfolio of summary.portfolios) {
        const valueResponse = await api.portfolios.getValueInCurrency(
          portfolio.portfolio.id,
          displayCurrency
        );
        converted[portfolio.portfolio.id] = valueResponse.data.value;
      }

      setConvertedValues(converted);
    } catch (err) {
      console.error('Failed to convert currency values:', err);
    }
  };

  const formatCurrency = (amount) => {
    if (amount === undefined || amount === null) {
      return '$0.00';
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: displayCurrency
    }).format(amount);
  };

  const formatPercentage = (value) => {
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

  const totals = summary?.totals || {};
  const assetBreakdown = summary?.asset_breakdown || [];

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Portfolio Dashboard</h1>
        <div className="w-48">
          <CurrencySelector
            value={displayCurrency}
            onChange={setDisplayCurrency}
            label="Display Currency"
            size="small"
          />
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Value</h3>
          <p className="text-2xl font-bold text-gray-900">
            <CurrencyDisplay
              amount={totals.total_value}
              currency="USD"
              displayCurrency={displayCurrency}
              showOriginal={false}
            />
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Cost</h3>
          <p className="text-2xl font-bold text-gray-900">
            <CurrencyDisplay
              amount={totals.total_cost}
              currency="USD"
              displayCurrency={displayCurrency}
              showOriginal={false}
            />
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Gain/Loss</h3>
          <p className={`text-2xl font-bold ${
            (totals.total_gain_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            <CurrencyDisplay
              amount={totals.total_gain_loss}
              currency="USD"
              displayCurrency={displayCurrency}
              showOriginal={false}
              colorize={true}
            />
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

      {/* Portfolio Cards */}
      {summary?.portfolios && (
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Portfolio Breakdown</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {summary.portfolios.map((item) => (
              <Card
                key={item.portfolio.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => navigate(`/portfolios/${item.portfolio.id}`)}
              >
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {item.portfolio.name}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    Base Currency: {item.portfolio.currency}
                  </Typography>
                  <Box mt={2}>
                    <Typography variant="body2" color="textSecondary">
                      Total Value
                    </Typography>
                    <Typography variant="h5">
                      <CurrencyDisplay
                        amount={item.summary.total_value}
                        currency={item.portfolio.currency}
                        displayCurrency={displayCurrency}
                        showOriginal={item.portfolio.currency !== displayCurrency}
                      />
                    </Typography>
                  </Box>
                  <Box mt={1}>
                    <Typography
                      variant="body1"
                      color={item.summary.total_return >= 0 ? 'success.main' : 'error.main'}
                    >
                      {item.summary.total_return >= 0 ? <TrendingUp /> : <TrendingDown />}
                      {formatPercentage(item.summary.total_return_pct)}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Currency Exposure Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Currency Exposure</h2>
        <CurrencyExposureChart portfolios={summary?.portfolios} />
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

// Currency Exposure Chart Component
const CurrencyExposureChart = ({ portfolios }) => {
  const [exposure, setExposure] = useState({});
  const { displayCurrency } = useCurrency();

  useEffect(() => {
    if (portfolios) {
      calculateTotalExposure();
    }
  }, [portfolios, displayCurrency]);

  const calculateTotalExposure = async () => {
    const totalExposure = {};

    for (const item of portfolios) {
      try {
        const response = await api.portfolios.getCurrencyExposure(
          item.portfolio.id,
          displayCurrency
        );

        const data = response.data.exposure;
        for (const [currency, info] of Object.entries(data)) {
          if (!totalExposure[currency]) {
            totalExposure[currency] = 0;
          }
          totalExposure[currency] += parseFloat(info.converted_amount || info.amount);
        }
      } catch (err) {
        console.error('Failed to get currency exposure:', err);
      }
    }

    setExposure(totalExposure);
  };

  const total = Object.values(exposure).reduce((sum, val) => sum + val, 0);

  return (
    <div className="space-y-4">
      {Object.entries(exposure).map(([currency, amount]) => {
        const percentage = total > 0 ? (amount / total) * 100 : 0;

        return (
          <div key={currency} className="flex items-center justify-between">
            <div className="flex items-center">
              <span className="text-sm font-medium text-gray-900">
                {currency}
              </span>
            </div>
            <div className="flex items-center space-x-4">
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <div className="text-right w-24">
                <p className="text-sm font-medium text-gray-900">
                  {percentage.toFixed(1)}%
                </p>
              </div>
              <div className="text-right w-32">
                <p className="text-sm text-gray-600">
                  <CurrencyDisplay
                    amount={amount}
                    currency={displayCurrency}
                    showCode={true}
                  />
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default Dashboard;