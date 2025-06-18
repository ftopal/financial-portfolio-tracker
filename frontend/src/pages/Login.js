import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextField, Button, Container, Typography, Box, Alert } from '@mui/material';
import api from '../services/api';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // In your Login.js component
const handleSubmit = async (e) => {
  e.preventDefault();
  setError('');

  try {
    const response = await api.auth.login(username, password);
    console.log('Login response:', response.data);  // Debug the response

    // Make sure the token is in the response
    if (response.data.token) {
      localStorage.setItem('token', response.data.token);
      navigate('/dashboard');
    } else {
      setError('Authentication failed: No token received');
    }
  } catch (err) {
    setError('Invalid username or password');
    console.error('Login error:', err);
  }
};

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography component="h1" variant="h5">
          Financial Portfolio Tracker
        </Typography>
        <Typography component="h2" variant="h5" sx={{ mt: 2 }}>
          Sign In
        </Typography>

        {error && <Alert severity="error" sx={{ mt: 2, width: '100%' }}>{error}</Alert>}

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1, width: '100%' }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="username"
            label="Username"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label="Password"
            type="password"
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
          >
            Sign In
          </Button>
        </Box>
      </Box>
    </Container>
  );
};

export default Login;