import React from 'react';
import { Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import AiSearch from './pages/AiSearch';
import Canvas from './pages/Canvas';
import { ChatProvider, useChatContext } from './context/ChatContext';

function Sidebar() {
  const { chats, activeChatId, setActiveChatId, createNewChat, deleteChat, renameChat, loadingChats, activeChatHasMessages } = useChatContext();
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <aside className="w-64 bg-[#0f0f23]/90 backdrop-blur border-r border-blue-500/10 flex flex-col h-screen sticky top-0">
      <div className="px-5 py-4 border-b border-blue-500/10">
        <h1 className="text-blue-400 font-bold text-lg">Jira Dashboard</h1>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-8">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Main</div>
          <nav className="flex flex-col gap-1">
            <NavLink to="/" end className={({isActive}) => `px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-blue-500/20 text-blue-300' : 'text-slate-400 hover:text-blue-300 hover:bg-blue-500/10'}`}>Dashboard</NavLink>
            <button
              onClick={async () => { const id = await createNewChat(); if (id) navigate('/canvas'); }}
              className={`text-left px-3 py-2 rounded-md text-sm font-medium w-full ${location.pathname === '/canvas' && !activeChatHasMessages ? 'bg-blue-500/20 text-blue-300' : 'text-slate-400 hover:text-blue-300 hover:bg-blue-500/10'}`}
            >Canvas</button>
            <NavLink to="/ai-search" className={({isActive}) => `px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-blue-500/20 text-blue-300' : 'text-slate-400 hover:text-blue-300 hover:bg-blue-500/10'}`}>AI Search</NavLink>
          </nav>
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs uppercase tracking-wider text-slate-500">History</div>
            <button onClick={async () => { const id = await createNewChat(); if (id) navigate('/canvas'); }} className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-500">+ New</button>
          </div>
          <div className="space-y-1 max-h-72 overflow-y-auto pr-1">
            {loadingChats && <div className="text-slate-500 text-xs">Loading...</div>}
            {chats.map(c => (
              <div key={c.id} className={`group flex items-center gap-1 rounded ${activeChatId === c.id && activeChatHasMessages ? 'bg-blue-500/30' : 'hover:bg-blue-500/10'}`}> 
                <button onClick={() => { setActiveChatId(c.id); navigate('/canvas'); }} className={`flex-1 text-left px-3 py-2 text-xs truncate ${activeChatId === c.id && activeChatHasMessages ? 'text-blue-200' : 'text-slate-400 group-hover:text-blue-200'}`}>{c.title}</button>
                <button title="Rename" onClick={() => { const t = prompt('New title', c.title); if (t) renameChat(c.id, t); }} className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-blue-300 pr-1">✎</button>
                <button title="Delete" onClick={() => { if (confirm('Delete this chat?')) deleteChat(c.id); }} className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-red-400 px-1">✕</button>
              </div>
            ))}
            {!loadingChats && chats.length === 0 && <div className="text-slate-500 text-xs">No chats yet.</div>}
          </div>
        </div>
      </div>
      <div className="p-4 border-t border-blue-500/10 text-[10px] text-slate-500">© {new Date().getFullYear()} Jira AI</div>
    </aside>
  );
}

export default function App() {
  return (
    <ChatProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 min-h-screen overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/canvas" element={<Canvas />} />
            <Route path="/ai-search" element={<AiSearch />} />
          </Routes>
        </main>
      </div>
    </ChatProvider>
  );
}
