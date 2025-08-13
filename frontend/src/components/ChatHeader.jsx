import React, { useState, useEffect } from "react";
import { useChatContext } from "../context/ChatContext";

/**
 * ChatHeader displays the chat title (inline editable) and provider selector.
 */
export default function ChatHeader({
  chats,
  activeChatId,
  switchProvider,
  activeProvider,
  providers,
}) {
  const { renameChat } = useChatContext();
  const chat = chats.find((c) => c.id === activeChatId);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(chat?.title || "");

  useEffect(() => {
    setTitle(chat?.title || "");
  }, [chat?.title]);

  const commit = () => {
    if (title && title !== chat?.title) renameChat(chat.id, title);
    setEditing(false);
  };

  return (
    <div className="w-full mx-auto max-w-7xl mb-4 flex items-center justify-between gap-4 sticky top-0 z-30 bg-gradient-to-b from-[#0b1120]/90 via-[#0b1120]/70 to-transparent backdrop-blur py-3 px-1">
      <div className="flex items-center gap-2 min-w-0">
        {editing ? (
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") {
                setTitle(chat.title);
                setEditing(false);
              }
            }}
            className="bg-slate-800 text-slate-100 text-sm px-2 py-1 rounded border border-slate-600 w-64"
          />
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-sm font-semibold text-slate-200 truncate max-w-xs text-left hover:text-white"
          >
            {chat?.title || "Untitled chat"}
          </button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <label className="text-[11px] text-slate-400">LLM</label>
        <select
          value={activeProvider}
          onChange={(e) => switchProvider(e.target.value)}
          className="bg-slate-800 text-slate-100 text-xs rounded px-2 py-1 border border-slate-600 focus:outline-none focus:ring focus:ring-blue-500/40"
        >
          {providers.map((p) => (
            <option key={p.name} value={p.name}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
