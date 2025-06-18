import React, { useState, useEffect } from 'react';

const GroupedAssets = () => {
  const [groupedAssets, setGroupedAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedAssets, setExpandedAssets] = useState(new Set());

  useEffect(() => {
    const fetchGroupedAssets = async () => {
      try {
        // Fetch grouped assets from Django API
        const token = localStorage.getItem('token');
        const response = await fetch('http://127.0.0.1:8000/api/assets/grouped/', {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json',
          }
        });

        if (!response.ok) {
          throw new Error('Failed to fetch grouped assets');
        }

        const data = await response.json();
        setGroupedAssets(data);
      } catch (err) {
        setError('Failed to load grouped assets');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchGroupedAssets();
  }, []);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatPercentage = (percentage) => {
    return `${percentage >= 0 ? '+' : ''}${percentage.toFixed(2)}%`;
  };

  const toggleExpand = (index) => {
    const newExpanded = new Set(expandedAssets);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedAssets(newExpanded);
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
      <h1 className="text-3xl font-bold text-gray-900 mb-6">
        Portfolio Assets (Grouped)
      </h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {groupedAssets.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <h3 className="text-lg font-medium text-gray-500">
            No assets found in your portfolio
          </h3>
        </div>
      ) : (
        <div className="space-y-4">
          {groupedAssets.map((asset, index) => (
            <div key={index} className="bg-white shadow rounded-lg overflow-hidden">
              <div
                className="p-6 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => toggleExpand(index)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {asset.symbol ? `${asset.symbol} - ${asset.name}` : asset.name}
                    </h3>
                    <div className="flex gap-2 mt-2">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {asset.category}
                      </span>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                        {asset.asset_type}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold text-gray-900">
                      {formatCurrency(asset.total_value)}
                    </div>
                    <div className={`text-sm font-medium ${
                      asset.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {formatCurrency(asset.gain_loss)} ({formatPercentage(asset.gain_loss_percentage)})
                    </div>
                  </div>
                  <div className="ml-4">
                    <svg
                      className={`h-5 w-5 transform transition-transform ${
                        expandedAssets.has(index) ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>

              {expandedAssets.has(index) && (
                <div className="border-t border-gray-200 p-6">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Total Quantity</dt>
                      <dd className="text-lg font-semibold text-gray-900">
                        {asset.total_quantity.toLocaleString()}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Avg Purchase Price</dt>
                      <dd className="text-lg font-semibold text-gray-900">
                        {formatCurrency(asset.average_purchase_price || 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Current Price</dt>
                      <dd className="text-lg font-semibold text-gray-900">
                        {formatCurrency(asset.current_price)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Total Invested</dt>
                      <dd className="text-lg font-semibold text-gray-900">
                        {formatCurrency(asset.total_invested)}
                      </dd>
                    </div>
                  </div>

                  <h4 className="text-lg font-medium text-gray-900 mb-4">
                    Individual Purchases ({asset.individual_purchases.length})
                  </h4>

                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Quantity
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Purchase Price
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Purchase Date
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Total Cost
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Current Value
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Gain/Loss
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {asset.individual_purchases.map((purchase) => {
                          const purchaseGainLoss = purchase.current_value - purchase.total_cost;
                          const purchaseGainLossPercentage = purchase.total_cost > 0
                            ? (purchaseGainLoss / purchase.total_cost) * 100
                            : 0;

                          return (
                            <tr key={purchase.id}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {purchase.quantity.toLocaleString()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {formatCurrency(purchase.purchase_price)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {purchase.purchase_date
                                  ? new Date(purchase.purchase_date).toLocaleDateString()
                                  : 'N/A'
                                }
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {formatCurrency(purchase.total_cost)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {formatCurrency(purchase.current_value)}
                              </td>
                              <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${
                                purchaseGainLoss >= 0 ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {formatCurrency(purchaseGainLoss)} ({formatPercentage(purchaseGainLossPercentage)})
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GroupedAssets;