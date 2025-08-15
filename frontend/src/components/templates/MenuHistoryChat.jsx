import React from 'react';
import { NavLink } from 'react-router-dom';

export default function MenuHistoryChat({
  c,
  location,
  renameChat,
  deleteChat,
}) {
  return (
    <NavLink
      to={`/chat/${c.id}`}
      key={c.id}
      className={`group flex items-center gap-1 rounded ${
        location.pathname === `/chat/${c.id}`
          ? 'bg-blue-500/30 text-blue-200'
          : 'hover:bg-blue-500/10 text-slate-400 group-hover:text-blue-200'
      }`}
    >
      <span className={`flex-1 text-left px-3 py-2 text-xs truncate`}>
        {c.title}
      </span>
      <button
        title="Rename"
        onClick={() => {
          const t = prompt('New title', c.title);
          if (t) renameChat(c.id, t);
        }}
        className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-blue-300 pr-1"
      >
        ✎
      </button>
      <button
        title="Delete"
        onClick={() => {
          if (confirm('Delete this chat?')) deleteChat(c.id);
        }}
        className="opacity-0 group-hover:opacity-100 text-[10px] text-slate-400 hover:text-red-400 px-1"
      >
        ✕
      </button>
    </NavLink>
  );
}
