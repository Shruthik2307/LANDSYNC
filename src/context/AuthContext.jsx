import React, { createContext, useContext, useState, useEffect } from 'react';
import { INITIAL_USERS, INITIAL_COMPANY } from '../data/seedData';
import { getApiBaseUrl } from '../api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('landsync_session_token');
    return saved ? null : null; // Start unauthenticated
  });

  const [company, setCompany] = useState(() => {
    return INITIAL_COMPANY;
  });


  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('fleetpulse_theme') || 'dark');

  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    // Token-based auth handled via secure cookies/headers now
  }, [currentUser]);

  useEffect(() => {
    // Company state managed via session/API
  }, [company]);

  useEffect(() => {
    localStorage.setItem('fleetpulse_theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const login = async (email, password) => {
    try {
      const apiBase = getApiBaseUrl();
      const response = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      }).then(res => res.json());

      if (response.mfa_required) {
        setMfaRequired(true);
        return { success: true, mfaRequired: true };
      }

      if (response.token) {
        setCurrentUser(response.user);
        setIsAuthenticated(true);
        return { success: true, user: response.user };
      }

      return { success: false, error: response.detail || 'Login failed' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  };

  const verifyMFA = async (email, token) => {
    try {
      const apiBase = getApiBaseUrl();
      const response = await fetch(`${apiBase}/auth/mfa-verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token })
      }).then(res => res.json());

      if (response.token) {
        setIsAuthenticated(true);
        setMfaRequired(false);
        return { success: true };
      }
      return { success: false, error: response.detail || 'Invalid OTP' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  };


  const registerCompany = async (compDetails, adminUser) => {
    try {
      const apiBase = getApiBaseUrl();
      const response = await fetch(`${apiBase}/auth/register-company`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ compDetails, adminUser })
      }).then(res => res.json());

      if (response.success) {
        setCompany(response.company);
        setCurrentUser(response.user);
        setIsAuthenticated(true);
        return { success: true };
      }
      return { success: false, error: response.detail || 'Registration failed' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  };

  const logout = () => {
    setIsAuthenticated(false);
  };

  const switchRole = (newRole) => {
    const targetUser = INITIAL_USERS.find((u) => u.role === newRole) || {
      ...currentUser,
      role: newRole
    };
    setCurrentUser(targetUser);
  };

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const hasPermission = (requiredRoles) => {
    if (!requiredRoles || requiredRoles.length === 0) return true;
    return requiredRoles.includes(currentUser.role);
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        company,
        isAuthenticated,
        mfaRequired,
        theme,
        isOffline,
        login,
        verifyMFA,
        registerCompany,
        logout,
        switchRole,
        toggleTheme,
        hasPermission
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
