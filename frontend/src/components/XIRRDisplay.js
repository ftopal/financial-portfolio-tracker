import React from 'react';
import { Typography, Skeleton, Tooltip } from '@mui/material';
import { InfoOutlined } from '@mui/icons-material';

const XIRRDisplay = ({
  value,
  loading = false,
  error = null,
  variant = "body2",
  showTooltip = false
}) => {
  if (loading) {
    return <Skeleton width={60} height={20} />;
  }

  if (error) {
    return (
      <Typography variant="caption" color="text.secondary">
        {error}
      </Typography>
    );
  }

  if (value === null || value === undefined) {
    return (
      <Typography variant="caption" color="text.secondary">
        Not enough data
      </Typography>
    );
  }

  const percentage = (value * 100).toFixed(2);
  const color = value >= 0 ? 'success.main' : 'error.main';

  const xirrElement = (
    <Typography
      variant={variant}
      color={color}
      fontWeight="medium"
    >
      {percentage}%
    </Typography>
  );

  if (showTooltip) {
    return (
      <Tooltip
        title={
          <div>
            <div>Extended Internal Rate of Return</div>
            <div>Annualized return considering timing of cash flows</div>
          </div>
        }
        placement="top"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {xirrElement}
          <InfoOutlined sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  }

  return xirrElement;
};

export default XIRRDisplay;