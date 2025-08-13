import React from "react";
import Sidebar from "./Sidebar";
import { useUI } from "./UIContext";

export default function AppLayout({ children }) {
  const { sidebarCollapsed, sidebarAutoHidden } = useUI();
  return (
    <div className="flex min-h-screen bg-zinc-100 text-slate-800 dark:bg-gradient-to-b dark:from-[#1a1a2e] dark:via-[#16213e] dark:to-[#0f0f23] dark:text-slate-200 transition-colors overflow-hidden">
      <Sidebar />
      <main
        className={`flex-1 min-h-screen overflow-y-auto bg-slate-50 dark:bg-transparent transition-[margin,width] duration-300 ease-out ${
          sidebarAutoHidden ? "ml-0" : ""
        }`}
      >
        {children}
      </main>
    </div>
  );
}
