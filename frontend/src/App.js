import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import PortfolioTransactions from './pages/assets/PortfolioTransactions';
import Navigation from './components/Navigation';
import Assets from './pages/Assets';
import GroupedAssets from './pages/GroupedAssets';
import Portfolios from './pages/Portfolios';
import ConsolidatedPortfolioDetails from './pages/ConsolidatedPortfolioDetails';
import Settings from './pages/Settings';
import { CurrencyProvider } from './contexts/CurrencyContext';

// Create a helper component for protected routes
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return (
    <>
      <Navigation />
      {children}
    </>
  );
};

// Create a theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <CurrencyProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/:portfolioId"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios"
              element={
                <ProtectedRoute>
                  <Portfolios />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/:portfolioId"
              element={
                <ProtectedRoute>
                  <ConsolidatedPortfolioDetails />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/:portfolioId/assets"
              element={
                <ProtectedRoute>
                  <PortfolioTransactions />
                </ProtectedRoute>
              }
            />
            <Route
              path="/assets"
              element={
                <ProtectedRoute>
                  <Assets />
                </ProtectedRoute>
              }
            />
            <Route
              path="/assets/grouped"
              element={
                <ProtectedRoute>
                  <GroupedAssets />
                </ProtectedRoute>
              }
            />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/preferences" element={<Settings />} />
          </Routes>
        </Router>
      </CurrencyProvider>
    </ThemeProvider>
  );
}

export default App;