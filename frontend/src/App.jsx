import React from "react";
import { Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AiSearch from "./pages/AiSearch";
import Canvas from "./pages/Canvas";
import { ChatProvider } from "./context/ChatContext";
import { DashboardProvider } from "./context/DashboardContext";
import { ThemeProvider } from "./layout/ThemeProvider";
import AppLayout from "./layout/AppLayout";
import { UIProvider } from "./layout/UIContext";
// import { ComingSoon } from "./components/ComingSoon"; // Added import for ComingSoon

export default function App() {
  return (
    <ChatProvider>
      <DashboardProvider>
        <ThemeProvider>
          <UIProvider>
            <AppLayout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/canvas" element={<Canvas />} />
                <Route path="/chat/:chatId" element={<AiSearch />} />
                <Route path="/ai-search" element={<AiSearch />} />
                <Route
                  path="/library"
                  element={<ComingSoon label="Library - Coming soon" />}
                />
                <Route
                  path="/codex"
                  element={<ComingSoon label="Codex - Coming soon" />}
                />
                <Route
                  path="/sora"
                  element={<ComingSoon label="Sora - Coming soon" />}
                />
                <Route
                  path="/gpts"
                  element={<ComingSoon label="GPTs - Coming soon" />}
                />
              </Routes>
            </AppLayout>
          </UIProvider>
        </ThemeProvider>
      </DashboardProvider>
    </ChatProvider>
  );
}

const ComingSoon = ({ label }) => (
  <div className="p-10 text-center text-slate-500">
    {label || "Coming soon"}
  </div>
);
