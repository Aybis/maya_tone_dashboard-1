import React, { createContext, useContext, useCallback, useEffect, useRef, useState } from 'react';

const DashboardContext = createContext(null);

export function DashboardProvider({ children, staleMs = 5 * 60 * 1000, autoRefreshMs = null }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastFetched, setLastFetched] = useState(null);
  const inFlight = useRef(false);
  const timerRef = useRef(null);

  const fetchDashboard = useCallback(async (force = false) => {
    if (inFlight.current) return; // prevent duplicate
    if (!force && lastFetched && Date.now() - lastFetched < staleMs) return; // cache valid
    try {
      inFlight.current = true;
      setLoading(true); setError('');
      const res = await fetch('/api/dashboard-stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setLastFetched(Date.now());
    } catch (e) {
      setError(e.message || 'Failed loading dashboard');
    } finally {
      setLoading(false);
      inFlight.current = false;
    }
  }, [lastFetched, staleMs]);

  // initial load
  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // optional auto refresh
  useEffect(() => {
    if (!autoRefreshMs) return;
    timerRef.current = setInterval(() => fetchDashboard(true), autoRefreshMs);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [autoRefreshMs, fetchDashboard]);

  const value = {
    dashboard: data,
    loadingDashboard: loading,
    dashboardError: error,
    lastFetched,
    refreshDashboard: () => fetchDashboard(true),
    isStale: lastFetched ? (Date.now() - lastFetched > staleMs) : true,
  };
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider');
  return ctx;
}
