import React, { createContext, useContext, useState, useEffect } from 'react';
import { INITIAL_USERS, INITIAL_COMPANY } from '../data/seedData';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_user');
    return saved ? JSON.parse(saved) : INITIAL_USERS[0]; // Default: Admin (Rajesh Sharma)
  });

  const [company, setCompany] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_company');
    return saved ? JSON.parse(saved) : INITIAL_COMPANY;
  });

  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [theme, setTheme] = useState(() => localStorage.getItem('fleetpulse_theme') || 'dark');
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    localStorage.setItem('fleetpulse_user', JSON.stringify(currentUser));
  }, [currentUser]);

  useEffect(() => {
    localStorage.setItem('fleetpulse_company', JSON.stringify(company));
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

  const login = (email, password) => {
    const user = INITIAL_USERS.find((u) => u.email.toLowerCase() === email.toLowerCase()) || {
      id: 'USR-TEMP',
      name: email.split('@')[0].toUpperCase(),
      email,
      role: 'Fleet Manager',
      companyId: company.id
    };
    setCurrentUser(user);
    setIsAuthenticated(true);
    return { success: true, user };
  };

  const registerCompany = (compDetails, adminUser) => {
    const newComp = { id: `COMP-${Date.now()}`, ...compDetails };
    const newUser = {
      id: `USR-${Date.now()}`,
      name: adminUser.name,
      email: adminUser.email,
      role: 'Admin',
      companyId: newComp.id
    };
    setCompany(newComp);
    setCurrentUser(newUser);
    setIsAuthenticated(true);
    return { success: true };
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
        theme,
        isOffline,
        login,
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
