import React from 'react';
import {
  ToggleButton,
  ToggleButtonGroup,
  Box,
  Typography,
  Chip
} from '@mui/material';
import {
  DateRange as DateRangeIcon,
  TrendingUp as TrendingUpIcon
} from '@mui/icons-material';

const TimePeriodSelector = ({
  selectedPeriod,
  onPeriodChange,
  showRetentionWarning = false,
  disabled = false
}) => {
  const periods = [
    { value: '1M', label: '1M', fullLabel: '1 Month' },
    { value: '3M', label: '3M', fullLabel: '3 Months' },
    { value: '6M', label: '6M', fullLabel: '6 Months' },
    { value: '1Y', label: '1Y', fullLabel: '1 Year' },
    { value: 'YTD', label: 'YTD', fullLabel: 'Year to Date' },
    { value: 'ALL', label: 'All', fullLabel: 'All Time' }
  ];

  const handlePeriodChange = (event, newPeriod) => {
    if (newPeriod !== null) {
      onPeriodChange(newPeriod);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <DateRangeIcon fontSize="small" color="action" />
        <Typography variant="body2" color="text.secondary">
          Time Period
        </Typography>
      </Box>

      <ToggleButtonGroup
        value={selectedPeriod}
        exclusive
        onChange={handlePeriodChange}
        disabled={disabled}
        size="small"
        sx={{
          '& .MuiToggleButton-root': {
            px: 2,
            py: 0.5,
            fontSize: '0.875rem',
            fontWeight: 500,
            textTransform: 'none',
            minWidth: 'auto',
            '&.Mui-selected': {
              backgroundColor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': {
                backgroundColor: 'primary.dark',
              }
            }
          }
        }}
      >
        {periods.map((period) => (
          <ToggleButton
            key={period.value}
            value={period.value}
            title={period.fullLabel}
          >
            {period.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      {/* Retention Warning for Free Users */}
      {showRetentionWarning && (
        <Box sx={{ mt: 1 }}>
          <Chip
            icon={<TrendingUpIcon fontSize="small" />}
            label="Free account: 1 year limit"
            size="small"
            color="warning"
            variant="outlined"
            sx={{ fontSize: '0.75rem' }}
          />
        </Box>
      )}
    </Box>
  );
};

export default TimePeriodSelector;