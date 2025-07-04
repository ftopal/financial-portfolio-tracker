import React, { createContext, useState, useContext, useEffect } from 'react';
import { api, currencyAPI } from '../services/api';

const CurrencyContext = createContext({
  displayCurrency: 'USD',
  setDisplayCurrency: () => {},
  currencies: [],
  exchangeRates: {},
  convertAmount: () => {},
  loading: false,
  error: null
});

export const useCurrency = () => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error('useCurrency must be used within CurrencyProvider');
  }
  return context;
};

export const CurrencyProvider = ({ children }) => {
  const [displayCurrency, setDisplayCurrency] = useState(() => {
    // Load from localStorage or default to USD
    return localStorage.getItem('displayCurrency') || 'USD';
  });
  const [currencies, setCurrencies] = useState([]);
  const [exchangeRates, setExchangeRates] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadCurrencies();
    loadUserPreferences();
  }, []);

  useEffect(() => {
    // Save display currency preference
    localStorage.setItem('displayCurrency', displayCurrency);
  }, [displayCurrency]);

  const loadCurrencies = async () => {
    try {
      // Use currencyAPI.list() instead of api.get()
      const response = await currencyAPI.list();
      setCurrencies(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to load currencies:', err);
      setError('Failed to load currencies');
    } finally {
      setLoading(false);
    }
  };

  const loadUserPreferences = async () => {
    try {
      // Use api.preferences.get() instead of api.userPreferences.get()
      const response = await api.preferences.get();

      // Handle the response structure from your API
      if (response && response.data) {
        // Check if it's a paginated response
        if (response.data.results && response.data.results.length > 0) {
          const preferences = response.data.results[0];
          if (preferences.default_currency) {
            setDisplayCurrency(preferences.default_currency);
          }
        } else if (response.data.default_currency) {
          // Direct response
          setDisplayCurrency(response.data.default_currency);
        }
      }
    } catch (err) {
      console.error('Failed to load user preferences:', err);
      // Don't throw, just log the error
    }
  };

  const convertAmount = async (amount, fromCurrency, toCurrency, date = null) => {
    if (fromCurrency === toCurrency) {
      return amount;
    }

    try {
      // Use currencyAPI.convert() instead of api.post()
      const response = await currencyAPI.convert({
        amount,
        from_currency: fromCurrency,
        to_currency: toCurrency,
        date
      });
      return response.data.converted_amount;
    } catch (err) {
      console.error('Failed to convert currency:', err);
      throw err;
    }
  };

  const updateDisplayCurrency = async (newCurrency) => {
    setDisplayCurrency(newCurrency);
    localStorage.setItem('displayCurrency', newCurrency);

    // Update user preferences on the server
    try {
      // Use api.preferences.update() instead of api.userPreferences.update()
      await api.preferences.update({
        default_currency: newCurrency
      });
    } catch (err) {
      console.error('Failed to update currency preference:', err);
      // Don't throw, just log the error
    }
  };

  const value = {
    displayCurrency,
    setDisplayCurrency: updateDisplayCurrency,
    currencies,
    exchangeRates,
    convertAmount,
    loading,
    error
  };

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
};

export default CurrencyContext;