/**
 * Extract data array from API response
 * Handles both paginated and non-paginated responses
 * @param {Object} response - API response object
 * @returns {Array} - Data array
 */
export const extractDataArray = (response) => {
  // Check if response has data property
  if (!response || !response.data) {
    return [];
  }

  const data = response.data;

  // Check if it's a paginated response
  if (data.results !== undefined && Array.isArray(data.results)) {
    return data.results;
  }

  // Check if data itself is an array
  if (Array.isArray(data)) {
    return data;
  }

  // If it's neither, return empty array
  return [];
};

/**
 * Check if response is paginated
 * @param {Object} response - API response object
 * @returns {boolean}
 */
export const isPaginatedResponse = (response) => {
  return response?.data?.results !== undefined &&
         response?.data?.count !== undefined;
};

/**
 * Get pagination info from response
 * @param {Object} response - API response object
 * @returns {Object} - Pagination metadata
 */
export const getPaginationInfo = (response) => {
  if (!isPaginatedResponse(response)) {
    return null;
  }

  return {
    count: response.data.count,
    next: response.data.next,
    previous: response.data.previous,
    currentPage: response.data.current_page || 1,
    totalPages: response.data.total_pages || Math.ceil(response.data.count / 100)
  };
};