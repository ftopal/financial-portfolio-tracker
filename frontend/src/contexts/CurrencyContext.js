import React, { createContext, useState, useContext, useEffect } from 'react';
import api from '../services/api';

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
      const response = await api.get('/api/currencies/');
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
      const response = await api.get('/api/user-preferences/');
      if (response.data && response.data.default_currency) {
        setDisplayCurrency(response.data.default_currency);
      }
    } catch (err) {
      console.error('Failed to load user preferences:', err);
    }
  };

  const convertAmount = async (amount, fromCurrency, toCurrency, date = null) => {
    if (fromCurrency === toCurrency) {
      return amount;
    }

    try {
      const response = await api.post('/api/currencies/convert/', {
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

    // Update user preferences on the server
    try {
      await api.patch('/api/user-preferences/', {
        default_currency: newCurrency
      });
    } catch (err) {
      console.error('Failed to update currency preference:', err);
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