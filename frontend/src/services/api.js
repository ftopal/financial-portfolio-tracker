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
  }
};

// Asset services
export const assetAPI = {
  getAll: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.portfolio_id) params.append('portfolio_id', filters.portfolio_id);
    if (filters.asset_type) params.append('asset_type', filters.asset_type);

    return API.get(`assets/?${params.toString()}`);
  },
  get: (id) => API.get(`assets/${id}/`),
  create: (data) => API.post('assets/', data),
  update: (id, data) => API.put(`assets/${id}/`, data),
  delete: (id) => API.delete(`assets/${id}/`),
  updatePrice: (id, price) => API.post(`assets/${id}/update_price/`, { price }),
  getGrouped: () => API.get('assets/grouped/')
};

// Transaction services
export const transactionAPI = {
  getAll: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.asset_id) params.append('asset', filters.asset_id);
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

// Stock services
export const stockAPI = {
  search: (query) => API.get(`stocks/search/?q=${query}`),
  import: (symbol) => API.post('stocks/import_stock/', { symbol }),
  get: (id) => API.get(`stocks/${id}/`),
  getAll: () => API.get('stocks/'),
};

// Helper function to handle errors
export const handleAPIError = (error) => {
  if (error.response) {
    // Server responded with error
    const message = error.response.data.detail ||
                   error.response.data.message ||
                   'An error occurred';
    return {
      message,
      status: error.response.status,
      data: error.response.data
    };
  } else if (error.request) {
    // Request made but no response
    return {
      message: 'No response from server. Please check your connection.',
      status: 0
    };
  } else {
    // Something else happened
    return {
      message: error.message || 'An unexpected error occurred',
      status: 0
    };
  }
};

// Export everything as default
const api = {
    auth: authAPI,
    portfolios: portfolioAPI,
    assets: assetAPI,
    transactions: transactionAPI,
    categories: categoryAPI,
    stocks: stockAPI,
    handleError: handleAPIError
};

export default api;