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
export const formatCurrency = (amount, currencyCode = 'USD') => {
  const normalizedCurrency = normalizeCurrency(currencyCode);
  const normalizedAmount = normalizeCurrencyAmount(amount, currencyCode);

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: normalizedCurrency
  }).format(normalizedAmount);
};

/**
 * Check if a currency needs special handling for conversion
 */
export const isSpecialCurrency = (currencyCode) => {
  const code = currencyCode?.trim();
  return code === 'GBp';
};

export default {
  normalizeCurrency,
  normalizeCurrencyAmount,
  formatCurrency,
  isSpecialCurrency
};