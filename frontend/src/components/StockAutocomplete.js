import React, { useState, useEffect, useCallback } from 'react';
import { Search, AlertCircle } from 'lucide-react';
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
        console.log('Searching for:', query);
        const response = await api.securities.search(query);
        console.log('Search response:', response);

        const results = Array.isArray(response.data) ? response.data : [];
        setSearchResults(results);

        // If no results in database, show message instead of import option
        if (results.length === 0) {
          setError(`No results found for "${query.toUpperCase()}". Please contact your administrator to add new securities.`);
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

  const handleSelectStock = (stock) => {
    setSelectedStock(stock);
    onSelectStock(stock);
    setShowDropdown(false);
    setSearchTerm(stock.symbol);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount || 0);
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    setSearchTerm(value);
    setShowDropdown(true);

    if (!value) {
      setSelectedStock(null);
      onSelectStock(null);
    }
  };

  const handleInputFocus = () => {
    if (searchTerm && !selectedStock) {
      setShowDropdown(true);
    }
  };

  const handleInputBlur = () => {
    // Delay hiding dropdown to allow for selection
    setTimeout(() => setShowDropdown(false), 200);
  };

  return (
    <div className="relative w-full">
      {/* Search Input */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-gray-400" />
        </div>
        <input
          type="text"
          value={searchTerm}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
          placeholder="Search for stocks, ETFs, crypto..."
          className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* Selected Stock Display */}
      {selectedStock && !showDropdown && (
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

      {/* Dropdown */}
      {showDropdown && searchTerm && !selectedStock && (
        <div
          className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
          style={{
            zIndex: 9999,
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
            // Show no results message (without import option)
            <div className="p-4">
              <div className="mb-3">
                <p className="text-sm text-gray-600 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                  {isLoading ? 'Searching...' : error || `No results found for "${searchTerm}"`}
                </p>
              </div>
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