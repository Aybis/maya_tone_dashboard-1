import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [loadingChats, setLoadingChats] = useState(false);
  const [error, setError] = useState('');
  const [activeChatHasMessages, setActiveChatHasMessages] = useState(false);
  const [providers, setProviders] = useState([]);
  const [activeProvider, setActiveProvider] = useState('gemini');

  // Lazy chat creation: produce a temporary client id until first message sent.
  const createNewChat = useCallback(() => {
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
    const title = `New Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    setChats(prev => [{ id: tempId, title, _temp: true }, ...prev]);
    setActiveChatId(tempId);
    setActiveChatHasMessages(false);
    return tempId;
  }, []);

  const fetchHistory = useCallback(async () => {
    setLoadingChats(true);
    try {
      const res = await fetch('/api/chat/history');
      const data = await res.json();
      setChats(data);
      if (!activeChatId && data.length) {
        setActiveChatId(data[0].id);
      }
    } catch (e) {
      setError('Failed to load chat history');
    } finally {
      setLoadingChats(false);
    }
  }, [activeChatId, createNewChat]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  // Load providers list once
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/llm/providers');
        const data = await res.json();
        setProviders(data);
      } catch {}
    })();
  }, []);

  // Fetch provider for active chat
  useEffect(() => {
    if (!activeChatId) return;
    (async () => {
      try {
        const res = await fetch(`/api/chat/${activeChatId}/provider`);
        const data = await res.json();
        if (data.provider) setActiveProvider(data.provider);
      } catch {}
    })();
  }, [activeChatId]);

  const finalizeTempChat = useCallback(async (tempId, provider) => {
    try {
      const res = await fetch('/api/chat/new', { method: 'POST' });
      const data = await res.json();
      setChats(prev => prev.map(c => c.id === tempId ? { id: data.chat_id, title: data.title || c.title } : c));
      setActiveChatId(data.chat_id);
      if (provider && provider !== data.provider) {
        // switch provider immediately if mismatch
        await fetch(`/api/chat/${data.chat_id}/provider`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider, create_new: false }) });
        setActiveProvider(provider);
      } else if (data.provider) {
        setActiveProvider(data.provider);
      }
      return data.chat_id;
    } catch (e) {
      setError('Failed to create chat');
      return tempId;
    }
  }, []);

  const switchProvider = useCallback(async (newProvider) => {
    if (!activeChatId) return;
    // If current chat is temp just change activeProvider state
    const current = chats.find(c => c.id === activeChatId);
    if (current && current._temp) { setActiveProvider(newProvider); return; }
    try {
      const res = await fetch(`/api/chat/${activeChatId}/provider`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider: newProvider, create_new: true }) });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Failed to switch');
      setChats(prev => [{ id: data.chat_id, title: (prev.find(c => c.id === activeChatId)?.title || 'Chat') + ' (switched)' }, ...prev]);
      setActiveChatId(data.chat_id);
      setActiveProvider(data.provider);
      setActiveChatHasMessages(false);
    } catch (e) { setError('Failed to switch provider'); }
  }, [activeChatId, chats]);

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

  const value = { chats, activeChatId, setActiveChatId, createNewChat, finalizeTempChat, deleteChat, renameChat, refreshChats: fetchHistory, loadingChats, error, activeChatHasMessages, setActiveChatHasMessages, providers, activeProvider, switchProvider };
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider');
  return ctx;
}
