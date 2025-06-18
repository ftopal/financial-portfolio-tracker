import React, { useState, useEffect } from 'react';

const Assets = () => {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchAssets = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await fetch('http://127.0.0.1:8000/api/assets/', {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json',
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Assets data:', data); // For debugging
        setAssets(data);
      } catch (err) {
        console.error('Error fetching assets:', err);
        setError(`Failed to load assets: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchAssets();
  }, []);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">My Assets</h1>
        <button className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
          Add Asset
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {assets.length === 0 && !error ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <h3 className="text-lg font-medium text-gray-500 mb-2">
            No assets found
          </h3>
          <p className="text-gray-400">Start building your portfolio by adding your first asset.</p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {assets.map((asset) => (
              <li key={asset.id}>
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center">
                        <div>
                          <p className="text-lg font-medium text-indigo-600 truncate">
                            {asset.symbol ? `${asset.symbol} - ${asset.name}` : asset.name}
                          </p>
                          <div className="mt-1 flex items-center gap-4">
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              {asset.category?.name || 'Uncategorized'}
                            </span>
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                              {asset.asset_type}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-8">
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Quantity</p>
                        <p className="text-lg font-semibold">{parseFloat(asset.quantity).toLocaleString()}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Purchase Price</p>
                        <p className="text-lg font-semibold">{formatCurrency(asset.purchase_price)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Current Price</p>
                        <p className="text-lg font-semibold">{formatCurrency(asset.current_price || asset.current_value)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Total Value</p>
                        <p className="text-lg font-semibold">{formatCurrency(asset.total_value)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Gain/Loss</p>
                        <p className={`text-lg font-semibold ${
                          asset.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {formatCurrency(asset.gain_loss)}
                        </p>
                        <p className={`text-sm ${
                          asset.gain_loss_percentage >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          ({asset.gain_loss_percentage >= 0 ? '+' : ''}{asset.gain_loss_percentage?.toFixed(2)}%)
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-2">
                    <p className="text-sm text-gray-600">
                      Purchased on {formatDate(asset.purchase_date)}
                    </p>
                    {asset.notes && (
                      <p className="text-sm text-gray-500 mt-1">
                        Notes: {asset.notes}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default Assets;