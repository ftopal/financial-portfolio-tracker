import React from 'react';
import { Container, Typography, Box, Paper } from '@mui/material';
import Navigation from '../components/Navigation';
import UserPreferences from '../components/UserPreferences';

const Settings = () => {
  return (
    <>
      <Navigation />
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Typography variant="h4" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="textSecondary" gutterBottom>
          Manage your portfolio preferences and account settings
        </Typography>

        <Box mt={4}>
          <UserPreferences />
        </Box>
      </Container>
    </>
  );
};

export default Settings;