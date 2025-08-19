import { useEffect, useState } from "react";
import { Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { ChatProvider } from "./context/ChatContext";
import { DashboardProvider } from "./context/DashboardContext";
import AiSearch from "./pages/AiSearch";
import Canvas from "./pages/Canvas";
import Dashboard from "./pages/Dashboard";
import ProjectOverview from "./pages/ProjectOverview";
import Login from "./pages/Login";
import Sidebar from "./app/Sidebar";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await fetch("/api/check-auth");
      if (response.ok) {
        const data = await response.json();
        setIsAuthenticated(data.authenticated);
        setUsername(data.username || "");
      } else {
        // If not authenticated and on a protected route, clear it
        if (location.pathname !== "/") {
          navigate("/", { replace: true });
        }
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      // On error, also clear any protected routes
      if (location.pathname !== "/") {
        navigate("/", { replace: true });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (user) => {
    setIsAuthenticated(true);
    setUsername(user);
    // Always redirect to dashboard after login to avoid stale routes
    navigate("/", { replace: true });
  };

  const handleLogout = async () => {
    try {
      await fetch("/api/logout", { method: "POST" });
      setIsAuthenticated(false);
      setUsername("");
      // Clear any existing route state
      navigate("/", { replace: true });
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f0f23] flex items-center justify-center">
        <div className="text-blue-400">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <ChatProvider>
      <DashboardProvider>
        <div className="relative flex min-h-screen bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f0f23] text-slate-200">
          <Sidebar username={username} onLogout={handleLogout} />
          <main className="relative flex-1 min-h-screen overflow-y-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/project-overview" element={<ProjectOverview />} />
              <Route path="/canvas" element={<Canvas />} />
              <Route path="/chat/:chatId" element={<Canvas />} />
              <Route path="/ai-search" element={<AiSearch />} />
              {/* Fallback route - redirect any unknown routes to dashboard */}
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </main>
        </div>
      </DashboardProvider>
    </ChatProvider>
  );
}
