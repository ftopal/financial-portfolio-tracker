import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Box,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  AccountBalance as AssetsIcon,
  Category as CategoryIcon,
  SwapHoriz as TransactionsIcon,
  Logout as LogoutIcon,
  Folder as FolderIcon,
  Settings as SettingsIcon,
  CurrencyExchange as CurrencyIcon, // Add currency icon
} from '@mui/icons-material';
import CurrencyManager from './CurrencyManager'; // Import the CurrencyManager component

const Navigation = () => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currencyManagerOpen, setCurrencyManagerOpen] = useState(false); // Add state for currency manager
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const toggleDrawer = (open) => (event) => {
    if (
      event.type === 'keydown' &&
      (event.key === 'Tab' || event.key === 'Shift')
    ) {
      return;
    }
    setDrawerOpen(open);
  };

  const handleCurrencyManagerOpen = () => {
    setCurrencyManagerOpen(true);
    setDrawerOpen(false); // Close drawer when opening currency manager
  };

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
    { text: 'Portfolios', icon: <FolderIcon />, path: '/portfolios' },
    { text: 'Assets', icon: <AssetsIcon />, path: '/assets' },
    { text: 'Grouped Assets', icon: <AssetsIcon />, path: '/assets/grouped' },
    { text: 'Categories', icon: <CategoryIcon />, path: '/categories' },
    { text: 'Transactions', icon: <TransactionsIcon />, path: '/transactions' },
  ];

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <IconButton
            edge="start"
            color="inherit"
            aria-label="menu"
            onClick={toggleDrawer(true)}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Financial Portfolio Tracker
          </Typography>

          {/* Currency Manager Button in AppBar */}
          <IconButton
            color="inherit"
            onClick={handleCurrencyManagerOpen}
            sx={{ mr: 1 }}
            title="Manage Currencies"
          >
            <CurrencyIcon />
          </IconButton>

          {/* Settings icon button in the AppBar */}
          <IconButton
            color="inherit"
            component={Link}
            to="/preferences"
            sx={{ mr: 1 }}
          >
            <SettingsIcon />
          </IconButton>

          <Button color="inherit" onClick={handleLogout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>

      <Drawer anchor="left" open={drawerOpen} onClose={toggleDrawer(false)}>
        <Box
          sx={{ width: 250 }}
          role="presentation"
          onClick={toggleDrawer(false)}
          onKeyDown={toggleDrawer(false)}
        >
          <List>
            {menuItems.map((item) => (
              <ListItem
                button
                key={item.text}
                component={Link}
                to={item.path}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItem>
            ))}
          </List>
          <Divider />
          <List>
            {/* Add Manage Currencies in the drawer menu */}
            <ListItem
              button
              onClick={handleCurrencyManagerOpen}
            >
              <ListItemIcon><CurrencyIcon /></ListItemIcon>
              <ListItemText primary="Manage Currencies" />
            </ListItem>

            {/* Settings in the drawer menu */}
            <ListItem
              button
              component={Link}
              to="/preferences"
            >
              <ListItemIcon><SettingsIcon /></ListItemIcon>
              <ListItemText primary="Settings" />
            </ListItem>

            <ListItem button onClick={handleLogout}>
              <ListItemIcon><LogoutIcon /></ListItemIcon>
              <ListItemText primary="Logout" />
            </ListItem>
          </List>
        </Box>
      </Drawer>

      {/* Currency Manager Dialog */}
      {currencyManagerOpen && (
        <CurrencyManager
          open={currencyManagerOpen}
          onClose={() => setCurrencyManagerOpen(false)}
        />
      )}
    </>
  );
};

export default Navigation;