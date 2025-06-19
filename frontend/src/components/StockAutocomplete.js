import React, { useState, useEffect, useCallback } from 'react';
import { Search, TrendingUp, AlertCircle } from 'lucide-react';
import api from '../services/api';
import debounce from 'lodash.debounce';

const StockAutocomplete = ({ onSelectStock, assetType = 'STOCK' }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [error, setError] = useState('');

  // Debounced search function
  const searchStocks = useCallback(
    debounce(async (query) => {
      if (!query || query.length < 1) {
        setSearchResults([]);
        return;
      }

      setIsLoading(true);
      setError('');

      try {
        const response = await api.securities.search(query);
        setSearchResults(response.data.results);

        // If no results in database, offer to search Yahoo Finance
        if (response.data.results.length === 0) {
          setError(`No results found. Try importing "${query.toUpperCase()}" from Yahoo Finance.`);
        }
      } catch (err) {
        setError('Error searching stocks');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    searchStocks(searchTerm);
  }, [searchTerm, searchStocks]);

  const handleImportStock = async () => {
    if (!searchTerm) return;

    setIsLoading(true);
    setError('');

    try {
      const response = await api.securities.import(searchTerm);

      if (response.data.stock) {
        setSelectedStock(response.data.stock);
        setSearchResults([response.data.stock]);
        onSelectStock(response.data.stock);
        setError('');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to import stock');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectStock = (stock) => {
    setSelectedStock(stock);
    setSearchTerm(stock.symbol);
    setShowDropdown(false);
    onSelectStock(stock);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount || 0);
  };

  return (
    <div className="relative">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Stock Symbol *
        </label>
        <div className="relative">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value.toUpperCase());
              setShowDropdown(true);
              setSelectedStock(null);
            }}
            onFocus={() => setShowDropdown(true)}
            placeholder="Search by symbol or name..."
            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <Search className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
          {isLoading && (
            <div className="absolute right-3 top-2.5">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
            </div>
          )}
        </div>
      </div>

      {/* Selected stock info */}
      {selectedStock && (
        <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-medium text-gray-900">{selectedStock.name}</p>
              <p className="text-sm text-gray-600">
                {selectedStock.exchange} • {selectedStock.sector}
              </p>
            </div>
            <div className="text-right">
              <p className="font-medium">{formatCurrency(selectedStock.current_price)}</p>
              <p className="text-xs text-gray-500">Current Price</p>
            </div>
          </div>
        </div>
      )}

      {/* Dropdown */}
      {showDropdown && searchTerm && !selectedStock && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
          {searchResults.length > 0 ? (
            searchResults.map((stock) => (
              <div
                key={stock.id}
                onClick={() => handleSelectStock(stock)}
                className="px-4 py-3 hover:bg-gray-100 cursor-pointer border-b border-gray-100"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-gray-900">
                      {stock.symbol} - {stock.name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {stock.exchange} • {stock.asset_type}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{formatCurrency(stock.current_price)}</p>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="p-4">
              {error && (
                <div className="mb-3">
                  <p className="text-sm text-gray-600 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                  </p>
                </div>
              )}
              <button
                type="button"
                onClick={handleImportStock}
                disabled={isLoading}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium disabled:opacity-50"
              >
                {isLoading ? 'Importing...' : `Import ${searchTerm} from Yahoo Finance`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StockAutocomplete;