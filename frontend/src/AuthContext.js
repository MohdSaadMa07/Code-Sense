import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE = (
  window.location.hostname === 'localhost'
    ? 'http://127.0.0.1:8000'
    : process.env.REACT_APP_API_URL || ''
);
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || '';

const AuthContext = createContext(null);

function loadGsiScript() {
  return new Promise((resolve) => {
    if (window.google) { resolve(); return; }
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    document.head.appendChild(s);
  });
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('codesense_token'));
  const [loading, setLoading] = useState(true);
  const [gsiReady, setGsiReady] = useState(false);

  useEffect(() => {
    loadGsiScript().then(() => setGsiReady(true));
  }, []);

  useEffect(() => {
    if (token) {
      localStorage.setItem('codesense_token', token);
      fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((u) => {
          if (u) setUser(u);
          else { setToken(null); localStorage.removeItem('codesense_token'); }
        })
        .catch(() => { setToken(null); localStorage.removeItem('codesense_token'); })
        .finally(() => setLoading(false));
    } else {
      localStorage.removeItem('codesense_token');
      setLoading(false);
    }
  }, [token]);

  const signIn = useCallback(async (credential) => {
    const res = await fetch(`${API_BASE}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Google sign-in failed');
    }
    const data = await res.json();
    setToken(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('codesense_token');
  }, []);

  const promptGoogleSignIn = useCallback(() => {
    if (!GOOGLE_CLIENT_ID) {
      alert('Google Sign-In not configured. Set REACT_APP_GOOGLE_CLIENT_ID in .env');
      return;
    }
    if (!gsiReady) return;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (resp) => {
        if (resp.credential) {
          try { await signIn(resp.credential); } catch (e) { alert('Sign in failed: ' + e.message); }
        }
      },
    });
    window.google.accounts.id.prompt();
  }, [gsiReady, signIn]);

  return (
    <AuthContext.Provider value={{ user, token, loading, gsiReady, signIn, signOut, promptGoogleSignIn }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
