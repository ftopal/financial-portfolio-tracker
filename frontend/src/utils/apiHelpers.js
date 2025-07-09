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

  const data = response.data;

  // Get the actual page size from the current results
  const currentPageSize = data.results.length;

  // Calculate current page from pagination URLs or fall back to 1
  let currentPage = 1;

  if (data.next) {
    // Extract page number from next URL
    try {
      const nextUrl = new URL(data.next);
      const nextPageNum = parseInt(nextUrl.searchParams.get('page')) || 2;
      currentPage = nextPageNum - 1;
    } catch (e) {
      // If URL parsing fails, try to extract from URL string
      const nextMatch = data.next.match(/[?&]page=(\d+)/);
      if (nextMatch) {
        currentPage = parseInt(nextMatch[1]) - 1;
      }
    }
  } else if (data.previous) {
    // Extract page number from previous URL
    try {
      const prevUrl = new URL(data.previous);
      const prevPageNum = parseInt(prevUrl.searchParams.get('page')) || 1;
      currentPage = prevPageNum + 1;
    } catch (e) {
      // If URL parsing fails, try to extract from URL string
      const prevMatch = data.previous.match(/[?&]page=(\d+)/);
      if (prevMatch) {
        currentPage = parseInt(prevMatch[1]) + 1;
      }
    }
  }

  // Determine page size - prefer page_size from URL, then current results length, then default
  let pageSize = 20; // default

  // Try to get page_size from the next or previous URL
  if (data.next || data.previous) {
    try {
      const url = data.next || data.previous;
      const urlObj = new URL(url);
      const pageSizeParam = urlObj.searchParams.get('page_size');
      if (pageSizeParam) {
        pageSize = parseInt(pageSizeParam);
      } else if (currentPageSize > 0) {
        pageSize = currentPageSize;
      }
    } catch (e) {
      // Fallback to current results length if URL parsing fails
      if (currentPageSize > 0) {
        pageSize = currentPageSize;
      }
    }
  } else if (currentPageSize > 0) {
    // If no next/previous URLs, use current results length
    pageSize = currentPageSize;
  }

  // Calculate total pages correctly
  const totalPages = Math.ceil(data.count / pageSize);

  return {
    count: data.count,
    next: data.next,
    previous: data.previous,
    currentPage: currentPage,
    totalPages: totalPages,
    pageSize: pageSize
  };
};

/**
 * Build pagination parameters for API requests
 * @param {number} page - Current page number
 * @param {number} pageSize - Number of items per page
 * @param {Object} filters - Additional filters
 * @returns {Object} - Parameters object
 */
export const buildPaginationParams = (page = 1, pageSize = 20, filters = {}) => {
  const params = {
    page: page,
    page_size: pageSize,
    ...filters
  };

  // Remove undefined values
  Object.keys(params).forEach(key => {
    if (params[key] === undefined || params[key] === null) {
      delete params[key];
    }
  });

  return params;
};