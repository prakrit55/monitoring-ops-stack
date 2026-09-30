import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import ProductList from './pages/ProductList';
import ProductDetail from './pages/ProductDetail';
import AuthPage from './pages/AuthPage';
import UserMenu from './components/UserMenu';
import Profile from './pages/Profile';
import Contact from './pages/Contact';
import ShippingHandling from './pages/ShippingHandling';
import Inventory from './pages/Inventory';
import Orders from './pages/Orders';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { ThemeProvider, makeStyles } from '@material-ui/core/styles';
import CssBaseline from '@material-ui/core/CssBaseline';
import IconButton from '@material-ui/core/IconButton';
import Brightness4Icon from '@material-ui/icons/Brightness4';
import Brightness7Icon from '@material-ui/icons/Brightness7';
import getTheme from './theme';

const useStyles = makeStyles((theme) => ({
  themeToggle: {
    position: 'fixed',
    top: theme.spacing(2),
    right: theme.spacing(9),
    zIndex: 1300,
    color: '#ffffff',
    backgroundColor: '#6366f1',
    width: 40,
    height: 40,
    '&:hover': {
      backgroundColor: '#4f46e5',
    },
  },
  themeToggleUnauth: {
    position: 'fixed',
    top: theme.spacing(2),
    right: theme.spacing(2),
    zIndex: 1300,
    color: '#ffffff',
    backgroundColor: '#6366f1',
    width: 40,
    height: 40,
    '&:hover': {
      backgroundColor: '#4f46e5',
    },
  }
}));

const App = () => {
  const classes = useStyles();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved === 'true';
  });

  useEffect(() => {
    localStorage.setItem('darkMode', darkMode);
    if (darkMode) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, [darkMode]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (token && storedUser) {
      try {
        setIsAuthenticated(true);
        setUser(JSON.parse(storedUser));
      } catch (error) {
        console.error("Error parsing stored user data:", error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
    setUser(null);
  };

  const theme = getTheme(darkMode);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div>
          <IconButton
            className={isAuthenticated ? classes.themeToggle : classes.themeToggleUnauth}
            onClick={() => setDarkMode(!darkMode)}
            aria-label="toggle dark mode"
          >
            {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
          {isAuthenticated && <UserMenu user={user} onLogout={handleLogout} />}
          <Routes>
            {/* Updated Route Logic */}
            <Route path="/" element={isAuthenticated ? <Home /> : <Navigate replace to="/auth" />} />
            <Route
              path="/auth"
              element={!isAuthenticated ? (
                <AuthPage setIsAuthenticated={setIsAuthenticated} setUser={setUser} />
              ) : (
                <Navigate replace to="/" />
              )}
            />
            <Route path="/products" element={isAuthenticated ? <ProductList /> : <Navigate replace to="/auth" />} />
            <Route path="/products/:id" element={isAuthenticated ? <ProductDetail /> : <Navigate replace to="/auth" />} />
            <Route path="/shipping" element={isAuthenticated ? <ShippingHandling /> : <Navigate replace to="/auth" />} />
            <Route path="/profile" element={isAuthenticated ? <Profile /> : <Navigate replace to="/auth" />} />
            <Route path="/contact" element={isAuthenticated ? <Contact /> : <Navigate replace to="/auth" />} />
            <Route path="/inventory" element={isAuthenticated ? <Inventory /> : <Navigate replace to="/auth" />} />
            <Route path="/orders" element={isAuthenticated ? <Orders /> : <Navigate replace to="/auth" />} />
          </Routes>
          <ToastContainer />
        </div>
      </Router>
    </ThemeProvider>
  );
};

export default App;