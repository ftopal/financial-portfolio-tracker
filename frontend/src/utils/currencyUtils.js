// Currency symbols mapping
const CURRENCY_SYMBOLS = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  CAD: 'C$',
  AUD: 'A$',
  CHF: 'Fr',
  CNY: '¥',
  SEK: 'kr',
  NOK: 'kr',
  DKK: 'kr',
  PLN: 'zł',
  CZK: 'Kč',
  HUF: 'Ft',
  RUB: '₽',
  BRL: 'R$',
  INR: '₹',
  KRW: '₩',
  SGD: 'S$',
  HKD: 'HK$',
  MXN: '$',
  ZAR: 'R',
  TRY: '₺',
  ILS: '₪',
  THB: '฿',
  NZD: 'NZ$',
  // Add more currencies as needed
};

// Get currency symbol
export const getCurrencySymbol = (currency) => {
  return CURRENCY_SYMBOLS[currency?.toUpperCase()] || currency || '$';
};

/**
 * Normalize currency codes for display purposes
 * Handles special cases like GBp (British Pence)
 */
export const normalizeCurrency = (currencyCode) => {
  if (!currencyCode) return 'USD';

  // Handle special currency codes
  const code = currencyCode.trim();
  if (code === 'GBp') {
    return 'GBP'; // Display GBp as GBP symbol
  }

  return code;
};

/**
 * Normalize currency amounts for display purposes
 * Converts special units like pence to their base currency
 */
export const normalizeCurrencyAmount = (amount, currencyCode) => {
  if (!amount && amount !== 0) return 0;

  const code = currencyCode?.trim();

  // Convert pence to pounds for display (1 GBp = 0.01 GBP)
  if (code === 'GBp') {
    return amount * 0.01;
  }

  return amount;
};

/**
 * Format currency with proper normalization for special currency codes
 * This replaces the existing formatCurrency functions throughout the app
 */
export const formatCurrency = (amount, currencyCode = 'USD', compact = false, showSymbol = true) => {
  // Your existing normalization logic
  const normalizedCurrency = normalizeCurrency(currencyCode);
  const normalizedAmount = normalizeCurrencyAmount(amount, currencyCode);

  // Handle null/undefined values
  if (normalizedAmount === null || normalizedAmount === undefined || isNaN(normalizedAmount)) {
    return showSymbol ? `${getCurrencySymbol(normalizedCurrency)}0.00` : '0.00';
  }

  // Convert to number
  const numValue = typeof normalizedAmount === 'string' ? parseFloat(normalizedAmount) : normalizedAmount;

  // Handle invalid numbers
  if (isNaN(numValue)) {
    return showSymbol ? `${getCurrencySymbol(normalizedCurrency)}0.00` : '0.00';
  }

  // NEW: Compact formatting for large numbers (for charts)
  if (compact) {
    const absValue = Math.abs(numValue);

    if (absValue >= 1000000) {
      const formatted = (numValue / 1000000).toFixed(1);
      return showSymbol ? `${getCurrencySymbol(normalizedCurrency)}${formatted}M` : `${formatted}M`;
    } else if (absValue >= 1000) {
      const formatted = (numValue / 1000).toFixed(1);
      return showSymbol ? `${getCurrencySymbol(normalizedCurrency)}${formatted}K` : `${formatted}K`;
    }
  }

  // Your existing Intl.NumberFormat logic (enhanced)
  try {
    const formatter = new Intl.NumberFormat('en-US', {
      style: showSymbol ? 'currency' : 'decimal',
      currency: normalizedCurrency,
      minimumFractionDigits: normalizedCurrency === 'JPY' ? 0 : 2,
      maximumFractionDigits: normalizedCurrency === 'JPY' ? 0 : 2,
    });

    return formatter.format(numValue);
  } catch (error) {
    // Fallback formatting
    const formatted = numValue.toFixed(2);
    return showSymbol ? `${getCurrencySymbol(normalizedCurrency)}${formatted}` : formatted;
  }
};

/**
 * Check if a currency needs special handling for conversion
 */
export const isSpecialCurrency = (currencyCode) => {
  const code = currencyCode?.trim();
  return code === 'GBp';
};

/**
 * NEW CHART-SPECIFIC FUNCTIONS
 */

// Format percentage
export const formatPercentage = (value, decimalPlaces = 2) => {
  if (value === null || value === undefined || isNaN(value)) {
    return '0.00%';
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return '0.00%';
  }

  return `${numValue.toFixed(decimalPlaces)}%`;
};

// Format number with appropriate suffix
export const formatNumber = (value, compact = false) => {
  if (value === null || value === undefined || isNaN(value)) {
    return '0';
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return '0';
  }

  if (compact) {
    const absValue = Math.abs(numValue);

    if (absValue >= 1000000000) {
      return `${(numValue / 1000000000).toFixed(1)}B`;
    } else if (absValue >= 1000000) {
      return `${(numValue / 1000000).toFixed(1)}M`;
    } else if (absValue >= 1000) {
      return `${(numValue / 1000).toFixed(1)}K`;
    }
  }

  return numValue.toLocaleString('en-US');
};

// Format currency change (with + or -)
export const formatCurrencyChange = (value, currency = 'USD', compact = false) => {
  if (value === null || value === undefined || isNaN(value)) {
    return `${getCurrencySymbol(currency)}0.00`;
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return `${getCurrencySymbol(currency)}0.00`;
  }

  const formatted = formatCurrency(Math.abs(numValue), currency, compact);
  return numValue >= 0 ? `+${formatted}` : `-${formatted}`;
};

// Format percentage change (with + or -)
export const formatPercentageChange = (value, decimalPlaces = 2) => {
  if (value === null || value === undefined || isNaN(value)) {
    return '0.00%';
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return '0.00%';
  }

  const formatted = Math.abs(numValue).toFixed(decimalPlaces);
  return numValue >= 0 ? `+${formatted}%` : `-${formatted}%`;
};

// Get color for value (green for positive, red for negative)
export const getValueColor = (value) => {
  if (value === null || value === undefined || isNaN(value)) {
    return 'text.secondary';
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue) || numValue === 0) {
    return 'text.secondary';
  }

  return numValue > 0 ? 'success.main' : 'error.main';
};

// Currency validation
export const isValidCurrency = (currency) => {
  return currency && typeof currency === 'string' && currency.length === 3;
};

// Convert currency display name to code
export const getCurrencyCode = (displayName) => {
  const currencyMap = {
    'US Dollar': 'USD',
    'Euro': 'EUR',
    'British Pound': 'GBP',
    'Japanese Yen': 'JPY',
    'Canadian Dollar': 'CAD',
    'Australian Dollar': 'AUD',
    'Swiss Franc': 'CHF',
    'Chinese Yuan': 'CNY',
    // Add more mappings as needed
  };

  return currencyMap[displayName] || displayName;
};

// Chart formatting utilities
export const chartFormatters = {
  // Y-axis currency formatter
  yAxis: (value, currency = 'USD') => {
    return formatCurrency(value, currency, true, false);
  },

  // Tooltip currency formatter
  tooltip: (value, currency = 'USD') => {
    return formatCurrency(value, currency, false, true);
  },

  // Legend formatter
  legend: (value, currency = 'USD') => {
    return `Portfolio Value (${currency})`;
  },

  // Data label formatter
  dataLabel: (value, currency = 'USD') => {
    return formatCurrency(value, currency, true, true);
  }
};

// Default export (keeping your existing structure)
export default {
  normalizeCurrency,
  normalizeCurrencyAmount,
  formatCurrency,
  isSpecialCurrency,
  // NEW functions
  formatPercentage,
  formatNumber,
  formatCurrencyChange,
  formatPercentageChange,
  getCurrencySymbol,
  getValueColor,
  isValidCurrency,
  getCurrencyCode,
  chartFormatters
};