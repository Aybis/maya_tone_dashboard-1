import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useChatContext } from "../context/ChatContext";
import { ThemeToggle } from "./ThemeProvider";
import { useUI } from "./UIContext";

export default function Sidebar() {
  const {
    chats,
    activeChatId,
    setActiveChatId,
    createNewChat,
    deleteChat,
    renameChat,
    loadingChats,
  } = useChatContext();
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar, sidebarAutoHidden } = useUI();
  const baseWidth = sidebarCollapsed ? "w-[60px]" : "w-64";
  const hidden = sidebarAutoHidden
    ? "-translate-x-full pointer-events-none"
    : "translate-x-0";
  return (
    <aside
      className={`group ${baseWidth} bg-white/90 dark:bg-[#0f0f23]/90 backdrop-blur border-r border-blue-200/50 dark:border-blue-500/10 flex flex-col h-screen sticky top-0 theme-fade-all transition-all duration-300 ease-in-out max-md:fixed max-md:z-40 max-md:inset-y-0 max-md:left-0 transform ${hidden}`}
    >
      <div
        className={`px-3 py-3 border-b border-blue-500/10 flex items-center justify-between gap-2`}
      >
        {!sidebarCollapsed && (
          <h1 className="text-blue-500 dark:text-blue-400 font-bold text-lg whitespace-nowrap">
            Maya Tone
          </h1>
        )}
        <button
          onClick={toggleSidebar}
          className="text-xs px-2 py-1 rounded bg-slate-700/70 hover:bg-slate-600 text-slate-200"
          title={sidebarCollapsed ? "Expand" : "Collapse"}
        >
          {sidebarCollapsed ? "»" : "«"}
        </button>
        <ThemeToggle />
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
        <div className="flex items-center gap-1">
          {!sidebarCollapsed && (
            <button
              onClick={() => {
                const id = createNewChat();
                navigate(`/chat/${id}`);
              }}
              className="text-xs px-3 py-1.5 w-full rounded bg-blue-600 text-white hover:bg-blue-500 shadow"
            >
              + New Chat
            </button>
          )}
        </div>
        <div>
          {!sidebarCollapsed && (
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
              Menu
            </div>
          )}
          <nav className="flex flex-col gap-1 text-sm">
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="/chat/new"
              icon="✏️"
              label="New chat"
              onClick={() => {
                const id = createNewChat();
                navigate(`/chat/${id}`);
              }}
            />
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="#search"
              icon="🔍"
              label="Search chats"
              onClick={(e) => {
                e.preventDefault();
                const ev = new Event("open-search");
                window.dispatchEvent(ev);
              }}
            />
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="/library"
              icon="📚"
              label="Library"
            />
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="/codex"
              icon="🧪"
              label="Codex"
            />
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="/sora"
              icon="🎬"
              label="Sora"
            />
            <SidebarLink
              collapsed={sidebarCollapsed}
              to="/gpts"
              icon="🧩"
              label="GPTs"
            />
          </nav>
        </div>
        <div>
          {!sidebarCollapsed && (
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
              History
            </div>
          )}
          <div className="space-y-1 h-full overflow-y-auto pr-1">
            {loadingChats && (
              <div className="text-slate-500 text-xs">Loading...</div>
            )}
            {chats.map((c) => {
              const prov = c.provider || "";
              const provColor =
                prov === "openai"
                  ? "bg-emerald-600/50 text-emerald-300"
                  : prov === "azure"
                  ? "bg-indigo-600/50 text-indigo-300"
                  : "bg-fuchsia-600/50 text-fuchsia-200";
              return (
                <div
                  key={c.id}
                  className={`group flex items-center gap-1 rounded ${
                    activeChatId === c.id
                      ? "bg-blue-500/30"
                      : "hover:bg-blue-500/10"
                  } theme-fade-all`}
                >
                  <button
                    onClick={() => {
                      setActiveChatId(c.id);
                      navigate(`/chat/${c.id}`);
                    }}
                    className={`flex-1 text-left ${
                      sidebarCollapsed
                        ? "px-2 py-2 text-[11px]"
                        : "px-3 py-2 text-xs"
                    } truncate ${
                      activeChatId === c.id
                        ? "text-blue-200"
                        : "text-slate-400 group-hover:text-blue-200"
                    }`}
                  >
                    {sidebarCollapsed ? "💬" : c.title}
                  </button>
                  {!sidebarCollapsed && c._temp && (
                    <span
                      className="text-[9px] mr-1 px-1 py-0.5 rounded bg-amber-500/60 text-amber-100"
                      title="Not saved yet"
                    >
                      temp
                    </span>
                  )}
                  {!sidebarCollapsed && prov && !c._temp && (
                    <span
                      className={`text-[9px] mr-1 px-1 py-0.5 rounded ${provColor}`}
                    >
                      {prov}
                    </span>
                  )}
                  {!sidebarCollapsed && (
                    <button
                      title="Rename"
                      onClick={() => {
                        const t = prompt("New title", c.title);
                        if (t) renameChat(c.id, t);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-blue-300 pr-1"
                    >
                      ✎
                    </button>
                  )}
                  {!sidebarCollapsed && (
                    <button
                      title="Delete"
                      onClick={() => {
                        if (confirm("Delete this chat?")) deleteChat(c.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-red-400 px-1"
                    >
                      ✕
                    </button>
                  )}
                </div>
              );
            })}
            {!loadingChats && chats.length === 0 && (
              <div className="text-slate-500 text-xs">No chats yet.</div>
            )}
          </div>
        </div>
      </div>
      <div
        className={`p-3 border-t border-blue-500/10 text-[10px] text-slate-500 ${
          sidebarCollapsed ? "text-center" : ""
        }`}
      >
        © {new Date().getFullYear()} Jira AI
      </div>
    </aside>
  );
}

function SidebarLink({ to, icon, label, collapsed, onClick }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center gap-2 rounded px-2 py-2 text-xs font-medium transition-colors ${
          collapsed ? "justify-center" : ""
        } ${
          isActive
            ? "bg-blue-500/20 text-blue-500"
            : "text-slate-600 dark:text-slate-400 hover:bg-blue-500/10 hover:text-blue-500"
        }`
      }
    >
      <span className="text-base leading-none">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </NavLink>
  );
}
