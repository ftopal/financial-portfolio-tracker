import axios from 'axios';

// Base URL for the API
const BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/';

// Create an axios instance with default config
const API = axios.create({
  baseURL: BASE_URL + 'api/',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Create another axios instance for auth endpoints
const AUTH_API = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

// Request interceptor for adding token
API.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling errors
API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Currency-related endpoints grouped together
export const currencyAPI = {
  // Basic currency operations
  list: () => API.get('currencies/'),
  get: (code) => API.get(`currencies/${code}/`),
  convert: (data) => API.post('currencies/convert/', data),
  updateRates: () => API.post('currencies/update_rates/'),

  // Exchange rate operations
  exchangeRates: {
    list: (params) => API.get('exchange-rates/', { params }),
    get: (id) => API.get(`exchange-rates/${id}/`),
    latest: (fromCurrency, toCurrency) =>
      API.get('exchange-rates/', {
        params: {
          from_currency: fromCurrency,
          to_currency: toCurrency,
          limit: 1
        }
      }),
  }
};

// Also add to API object for backward compatibility
API.currencies = currencyAPI;
API.exchangeRates = currencyAPI.exchangeRates;

API.userPreferences = {
  get: () => API.get('/api/user-preferences/'),
  update: (data) => API.patch('/api/user-preferences/', data),
};

// Authentication services
export const authAPI = {
  login: (username, password) => {
    return AUTH_API.post('api-token-auth/', { username, password })
      .then(response => {
        if (response.data.token) {
          localStorage.setItem('token', response.data.token);
          localStorage.setItem('user', JSON.stringify({ username }));
        }
        return response.data;
      });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  },

  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  },

  getCurrentUser: () => {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }
};

// Portfolio services
export const portfolioAPI = {
  getAll: () => API.get('portfolios/'),
  get: (id) => API.get(`portfolios/${id}/`),
  getConsolidatedView: (portfolioId) => API.get(`portfolios/${portfolioId}/consolidated/`),
  create: (data) => API.post('portfolios/', data),
  update: (id, data) => API.put(`portfolios/${id}/`, data),
  delete: (id) => API.delete(`portfolios/${id}/`),
  getSummary: (portfolioId = null) => {
    const url = portfolioId ? `summary/?portfolio_id=${portfolioId}` : 'summary/';
    return API.get(url);
  },
  recalculateBalance: (portfolioId) => API.post(`portfolios/${portfolioId}/recalculate_cash_balance/`),
  verifyBalance: (portfolioId) => API.get(`portfolios/${portfolioId}/verify_cash_balance/`),

  getHoldings: (id) => API.get(`portfolios/${id}/holdings/`),

  // New cash-related endpoints
  depositCash: (portfolioId, data) => API.post(`portfolios/${portfolioId}/deposit_cash/`, data),
  withdrawCash: (portfolioId, data) => API.post(`portfolios/${portfolioId}/withdraw_cash/`, data),
  getCashHistory: (portfolioId, options = {}) => {
    const params = new URLSearchParams();

    // Add pagination parameters
    if (options.page) params.append('page', options.page);
    if (options.page_size) params.append('page_size', options.page_size);

    // Add optional filters
    if (options.transaction_type) params.append('transaction_type', options.transaction_type);
    if (options.start_date) params.append('start_date', options.start_date);
    if (options.end_date) params.append('end_date', options.end_date);

    const queryString = params.toString();
    const url = `portfolios/${portfolioId}/cash_history/${queryString ? `?${queryString}` : ''}`;

    return API.get(url);
  },
  checkAutoDeposit: (portfolioId, data) => API.post(`portfolios/${portfolioId}/check_auto_deposit/`, data),

  // Currency-related portfolio operations
  supported_currencies: () => API.get('portfolios/supported_currencies/'),
  getValueInCurrency: (id, currency, date = null) => {
    const params = { currency };
    if (date) params.date = date;
    return API.get(`portfolios/${id}/value/`, { params });
  },

  getCurrencyExposure: (id, targetCurrency = null) => {
    const params = targetCurrency ? { currency: targetCurrency } : {};
    return API.get(`portfolios/${id}/currency_exposure/`, { params });
  },
  getCurrencyExposureChart: (id, targetCurrency = null) => {
    const params = targetCurrency ? { currency: targetCurrency } : {};
    return API.get(`portfolios/${id}/currency_exposure_chart/`, { params });
  },
  getXIRR: (portfolioId, forceRecalculate = false) => {
    const params = forceRecalculate ? { force: 'true' } : {};
    return API.get(`portfolios/${portfolioId}/xirr/`, { params });
  },
};

// Cash Transaction services (NEW)
export const cashAPI = {
  getAll: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.portfolio_id) params.append('portfolio_id', filters.portfolio_id);
    if (filters.type) params.append('type', filters.type);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    return API.get(`cash-transactions/?${params.toString()}`);
  },
  get: (id) => API.get(`cash-transactions/${id}/`),
  create: (data) => API.post('cash-transactions/', data),
  update: (id, data) => API.put(`cash-transactions/${id}/`, data),
  delete: (id) => API.delete(`cash-transactions/${id}/`)
};

// User Preferences services (NEW)
export const preferencesAPI = {
  get: () => API.get('preferences/'),
  update: async (data) => {
    try {
      // First try to get existing preferences
      const response = await API.get('preferences/');

      if (response.data.results && response.data.results.length > 0) {
        // Update existing preferences
        const id = response.data.results[0].id;
        return API.patch(`preferences/${id}/`, data);
      } else {
        // Create new preferences - the backend will handle user assignment
        return API.post('preferences/', data);
      }
    } catch (error) {
      // If GET fails, try to create new preferences
      if (error.response && error.response.status === 404) {
        return API.post('preferences/', data);
      }
      throw error;
    }
  }
};

// Security services
export const securityAPI = {
  search: (query) => API.get(`securities/search/?q=${query}`),
  import: (symbol) => API.post('securities/import_security/', { symbol }),
  get: (id) => API.get(`securities/${id}/`),
  getAll: () => API.get('securities/'),
  updatePrice: (id, price) => API.post(`securities/${id}/update_price/`, { price })
};

// Transaction services
export const transactionAPI = {
  getAll: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.portfolio_id) params.append('portfolio_id', filters.portfolio_id);
    if (filters.security_id) params.append('security_id', filters.security_id);
    if (filters.type) params.append('type', filters.type);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    return API.get(`transactions/?${params.toString()}`);
  },
  get: (id) => API.get(`transactions/${id}/`),
  create: (data) => API.post('transactions/', data),
  update: (id, data) => API.put(`transactions/${id}/`, data),
  delete: (id) => API.delete(`transactions/${id}/`)
};

// Category services
export const categoryAPI = {
  getAll: () => API.get('categories/'),
  get: (id) => API.get(`categories/${id}/`),
  create: (data) => API.post('categories/', data),
  update: (id, data) => API.put(`categories/${id}/`, data),
  delete: (id) => API.delete(`categories/${id}/`)
};

// Consolidated API export
export const api = {
  auth: authAPI,
  portfolios: portfolioAPI,
  securities: securityAPI,
  transactions: transactionAPI,
  categories: categoryAPI,
  cash: cashAPI,
  preferences: preferencesAPI,
  currencies: currencyAPI
};

export default api;