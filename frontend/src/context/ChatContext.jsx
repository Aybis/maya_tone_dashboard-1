import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [loadingChats, setLoadingChats] = useState(false);
  const [error, setError] = useState('');
  const [activeChatHasMessages, setActiveChatHasMessages] = useState(false);

  const createNewChat = useCallback(async () => {
    try {
  const res = await fetch('/api/chat/new', { method: 'POST' });
  const data = await res.json();
  const title = data.title || `Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  setChats(prev => [{ id: data.chat_id, title }, ...prev]);
  setActiveChatId(data.chat_id);
  return data.chat_id;
    } catch (e) {
      setError('Failed to create chat');
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    setLoadingChats(true);
    try {
      const res = await fetch('/api/chat/history');
      const data = await res.json();
      setChats(data);
      if (!activeChatId && data.length) {
        setActiveChatId(data[0].id);
      } else if (!data.length) {
        // auto create initial chat if none exist
        await createNewChat();
      }
    } catch (e) {
      setError('Failed to load chat history');
    } finally {
      setLoadingChats(false);
    }
  }, [activeChatId, createNewChat]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  // Delete a chat from DB and state
  const deleteChat = useCallback(async (chatId) => {
    try {
      await fetch(`/api/chat/${chatId}/delete`, { method: 'DELETE' });
      setChats(prev => prev.filter(c => c.id !== chatId));
      if (activeChatId === chatId) {
        // pick next chat or create new
        setTimeout(async () => {
          if (chats.length > 1) {
            const remaining = chats.filter(c => c.id !== chatId);
            setActiveChatId(remaining[0]?.id || null);
          } else {
            await createNewChat();
          }
        }, 0);
      }
    } catch (e) {
      setError('Failed to delete chat');
    }
  }, [activeChatId, chats, createNewChat]);

  // Rename chat title
  const renameChat = useCallback(async (chatId, newTitle) => {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const res = await fetch(`/api/chat/${chatId}/title`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) });
      if (!res.ok) throw new Error();
      setChats(prev => prev.map(c => c.id === chatId ? { ...c, title } : c));
    } catch {
      setError('Failed to rename chat');
    }
  }, []);

  const value = { chats, activeChatId, setActiveChatId, createNewChat, deleteChat, renameChat, refreshChats: fetchHistory, loadingChats, error, activeChatHasMessages, setActiveChatHasMessages };
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider');
  return ctx;
}
