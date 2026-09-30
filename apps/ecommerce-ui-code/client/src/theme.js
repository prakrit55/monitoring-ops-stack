import { createMuiTheme } from '@material-ui/core/styles';

const getTheme = (darkMode) => createMuiTheme({
  palette: {
    type: darkMode ? 'dark' : 'light',
    primary: {
      main: '#6366f1',      // Indigo
      dark: '#4f46e5',
      light: '#818cf8',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#10b981',      // Emerald / Mint Teal
      dark: '#059669',
      light: '#34d399',
      contrastText: '#ffffff',
    },
    background: {
      default: darkMode ? '#0f172a' : '#f8fafc',    // Slate 900 vs Slate 50
      paper: darkMode ? '#1e293b' : '#ffffff',      // Slate 800 vs White
    },
    text: {
      primary: darkMode ? '#f8fafc' : '#0f172a',    // Slate 50 vs Slate 900
      secondary: darkMode ? '#94a3b8' : '#475569',  // Slate 400 vs Slate 600
    },
  },
  typography: {
    fontFamily: [
      'Plus Jakarta Sans',
      'Inter',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontWeight: 800,
    },
    h2: {
      fontWeight: 700,
    },
    h3: {
      fontWeight: 700,
    },
    h4: {
      fontWeight: 700,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 16,
  },
  overrides: {
    MuiButton: {
      root: {
        borderRadius: 12,
        padding: '8px 20px',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': {
          transform: 'translateY(-1px)',
          boxShadow: darkMode ? '0 8px 20px -6px rgba(99, 102, 241, 0.5)' : '0 8px 20px -6px rgba(99, 102, 241, 0.3)',
        },
      },
      containedPrimary: {
        backgroundImage: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
        boxShadow: '0 4px 14px 0 rgba(99, 102, 241, 0.25)',
        border: 'none',
        '&:hover': {
          backgroundImage: 'linear-gradient(135deg, #4f46e5 0%, #3730a3 100%)',
          boxShadow: '0 6px 20px 0 rgba(99, 102, 241, 0.35)',
        },
      },
      outlined: {
        borderColor: darkMode ? '#334155' : '#e2e8f0',
        color: darkMode ? '#f8fafc' : 'inherit',
        '&:hover': {
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.04)',
        },
      },
    },
    MuiPaper: {
      rounded: {
        borderRadius: 16,
      },
      elevation3: {
        boxShadow: darkMode ? '0 10px 30px -10px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.1)' : '0 10px 30px -10px rgba(99, 102, 241, 0.08), 0 1px 3px rgba(0, 0, 0, 0.03)',
      },
    },
    MuiTextField: {
      root: {
        '& .MuiOutlinedInput-root': {
          borderRadius: 12,
          '& fieldset': {
            borderColor: darkMode ? '#334155' : '#e2e8f0',
            transition: 'border-color 0.2s ease',
          },
          '&:hover fieldset': {
            borderColor: darkMode ? '#475569' : '#cbd5e1',
          },
          '&.Mui-focused fieldset': {
            borderColor: '#6366f1',
          },
        },
        '& .MuiInputLabel-root': {
          color: darkMode ? '#94a3b8' : 'inherit',
        },
        '& .MuiOutlinedInput-input': {
          color: darkMode ? '#f8fafc' : 'inherit',
        },
      },
    },
  },
});

export default getTheme;
