// frontend/src/components/StockAutocomplete.js - Fixed version
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
        setError('');
        return;
      }

      setIsLoading(true);
      setError('');

      try {
        console.log('Searching for:', query); // Debug log
        const response = await api.securities.search(query);
        console.log('Search response:', response); // Debug log

        // The API returns an array directly
        const results = Array.isArray(response.data) ? response.data : [];
        setSearchResults(results);

        // If no results in database, show import option
        if (results.length === 0) {
          setError(`No results found. Click below to import "${query.toUpperCase()}" from Yahoo Finance.`);
        }
      } catch (err) {
        setError('Error searching stocks');
        console.error('Search error:', err);
        setSearchResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    if (searchTerm) {
      searchStocks(searchTerm);
    } else {
      setSearchResults([]);
      setError('');
    }
  }, [searchTerm, searchStocks]);

  const handleImportStock = async () => {
    if (!searchTerm) return;

    setIsLoading(true);
    setError('');

    try {
      console.log('Importing:', searchTerm); // Debug log
      const response = await api.securities.import(searchTerm);
      console.log('Import response:', response); // Debug log

      if (response.data.security) {
        setSelectedStock(response.data.security);
        setSearchResults([response.data.security]);
        onSelectStock(response.data.security);
        setError('');
        setShowDropdown(false);
      }
    } catch (err) {
      console.error('Import error:', err);
      setError(err.response?.data?.error || 'Failed to import stock. Please check the symbol and try again.');
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

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.stock-autocomplete-container')) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="relative stock-autocomplete-container">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Security Symbol *
        </label>
        <div className="relative">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              const value = e.target.value.toUpperCase();
              setSearchTerm(value);
              setShowDropdown(true);
              setSelectedStock(null);
              console.log('Search term changed:', value); // Debug log
            }}
            onFocus={() => {
              setShowDropdown(true);
              console.log('Input focused, showing dropdown'); // Debug log
            }}
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
                {selectedStock.exchange || 'N/A'} • {selectedStock.sector || selectedStock.security_type}
              </p>
            </div>
            <div className="text-right">
              <p className="font-medium">{formatCurrency(selectedStock.current_price)}</p>
              <p className="text-xs text-gray-500">Current Price</p>
            </div>
          </div>
        </div>
      )}

      {/* Dropdown - Fixed visibility */}
      {showDropdown && searchTerm && !selectedStock && (
        <div
          className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
          style={{
            zIndex: 9999,  // Ensure it's on top
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0
          }}
        >
          {searchResults.length > 0 ? (
            // Show search results
            searchResults.map((stock) => (
              <div
                key={stock.id}
                onClick={() => handleSelectStock(stock)}
                className="px-4 py-3 hover:bg-gray-100 cursor-pointer border-b border-gray-100 last:border-b-0"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-gray-900">
                      {stock.symbol} - {stock.name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {stock.exchange || 'N/A'} • {stock.security_type || stock.asset_type || 'STOCK'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{formatCurrency(stock.current_price)}</p>
                  </div>
                </div>
              </div>
            ))
          ) : (
            // Show import option when no results
            <div className="p-4">
              {/* Always show the search status */}
              <div className="mb-3">
                <p className="text-sm text-gray-600 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                  {isLoading ? 'Searching...' : `No results found for "${searchTerm}"`}
                </p>
              </div>

              {/* Show import button when not loading and search term exists */}
              {!isLoading && searchTerm.length >= 1 && (
                <button
                  type="button"
                  onClick={handleImportStock}
                  className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors duration-200 flex items-center justify-center gap-2"
                >
                  <TrendingUp className="w-4 h-4" />
                  Import {searchTerm} from Yahoo Finance
                </button>
              )}

              {/* Show error if import failed */}
              {error && !isLoading && (
                <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded">
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Debug info - remove in production */}
      {process.env.NODE_ENV === 'development' && (
        <div className="mt-2 text-xs text-gray-500">
          Debug: showDropdown={showDropdown.toString()}, searchTerm="{searchTerm}", resultsCount={searchResults.length}
        </div>
      )}
    </div>
  );
};

export default StockAutocomplete;