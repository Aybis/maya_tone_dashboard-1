import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import {
  extractChartSpec,
  extractExportData,
  renderCardMarkdown,
  sanitizeRender,
} from '../../utils/markdown';

/**
 * Orchestrates fetching historic messages, realtime streaming via socket.io,
 * export payload parsing, auto-scroll handling, and sending new prompts.
 */
export function useChatCanvas({
  activeChatId,
  setActiveChatHasMessages,
  setActiveChatId,
  refreshChats,
  navigate,
  chatIdParam,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasInteracted, setHasInteracted] = useState(false); // controls hero state
  const socketRef = useRef(null);
  const endRef = useRef(null);

  // Sync route param -> context
  useEffect(() => {
    if (chatIdParam && chatIdParam !== activeChatId)
      setActiveChatId(chatIdParam);
  }, [chatIdParam, activeChatId, setActiveChatId]);

  // Initial load of existing messages
  useEffect(() => {
    if (!activeChatId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/chat/${activeChatId}`);
        if (res.status === 404 || res.status === 401) {
          if (!cancelled) {
            setError('Chat not found or access denied');
            setTimeout(() => navigate('/', { replace: true }), 1800);
          }
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          const processed = data.map((m) => {
            if (m.sender !== 'assistant' || !m.content) return m;
            const { cleaned, downloadData } = extractExportData(m.content);
            return downloadData?.download_link
              ? { ...m, content: cleaned, downloadData }
              : m;
          });
          setMessages(processed);
        }
      } catch (e) {
        !cancelled && setError('Failed to load messages');
      } finally {
        !cancelled && setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeChatId, navigate]);

  // Socket streaming lifecycle
  useEffect(() => {
    if (!activeChatId) return;
    const socketUrl = `${window.location.protocol}//${window.location.hostname}:4000`;
    socketRef.current = io(socketUrl);
    const s = socketRef.current;
    s.emit('join_chat', { chat_id: activeChatId });

    s.on('new_message', (data) => {
      if (data.chat_id !== activeChatId) return;
      setMessages((prev) => {
        if (data.sender === 'assistant') {
          const lastAssistant = [...prev]
            .reverse()
            .find((m) => m.sender === 'assistant');
          if (lastAssistant && lastAssistant.content === data.content)
            return prev;
        }
        let messageObj = {
          sender: data.sender,
          content: data.content,
          timestamp: data.timestamp || new Date().toISOString(),
        };
        if (data.sender === 'assistant') {
          const { cleaned, downloadData } = extractExportData(data.content);
          messageObj.content = cleaned;
          if (downloadData?.download_link)
            messageObj.downloadData = downloadData;
        }
        return [...prev, messageObj];
      });
      setLoading(false);
    });
    s.on('assistant_start', ({ chat_id, timestamp }) => {
      if (chat_id !== activeChatId) return;
      setLoading(true);
      setMessages((p) => [
        ...p,
        {
          sender: 'assistant',
          content: '',
          timestamp: timestamp || new Date().toISOString(),
          partial: true,
        },
      ]);
    });
    s.on('assistant_delta', ({ chat_id, delta, timestamp }) => {
      if (chat_id !== activeChatId) return;
      setMessages((prev) => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].sender === 'assistant') {
            copy[i] = {
              ...copy[i],
              content: (copy[i].content || '') + delta,
              timestamp:
                copy[i].timestamp || timestamp || new Date().toISOString(),
            };
            break;
          }
        }
        return copy;
      });
    });
    s.on('assistant_end', ({ chat_id, content, timestamp }) => {
      if (chat_id !== activeChatId) return;
      setMessages((prev) => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].sender === 'assistant') {
            const { cleaned, downloadData } = extractExportData(content);
            copy[i] = {
              ...copy[i],
              content: cleaned,
              timestamp: timestamp || copy[i].timestamp,
              partial: false,
            };
            if (downloadData?.download_link)
              copy[i].downloadData = downloadData;
            break;
          }
        }
        return copy;
      });
      setLoading(false);
      setActiveChatHasMessages(true);
    });
    s.on('assistant_error', ({ chat_id, error }) => {
      if (chat_id !== activeChatId) return;
      setError(error);
      setLoading(false);
    });
    return () => {
      s.disconnect();
    };
  }, [activeChatId, setActiveChatHasMessages]);

  // Auto scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = useCallback(
    async (eOrOpts) => {
      const override = eOrOpts?.contentOverride;
      eOrOpts?.preventDefault?.();
      const content = (override !== undefined ? override : input).trim();
      if (!content || loading) return;
      setInput('');
      setLoading(true);
      setError('');
      setHasInteracted(true);
      if (!activeChatId) {
        try {
          const res = await fetch('/api/chat/ask_new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content }),
          });
          const data = await res.json();
          if (!res.ok || !data.success) throw new Error(data.answer || 'Fail');
          setMessages([
            { sender: 'user', content },
            { sender: 'assistant', content: data.answer },
          ]);
          setActiveChatId(data.chat_id);
          setActiveChatHasMessages(true);
          refreshChats?.();
          navigate(`/chat/${data.chat_id}`, { replace: true });
        } catch (err) {
          setError('Failed to start chat');
        } finally {
          setLoading(false);
        }
        return;
      }
      setMessages((prev) => [
        ...prev,
        { sender: 'user', content, timestamp: new Date().toISOString() },
      ]);
      try {
        await fetch(`/api/chat/${activeChatId}/ask_stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content }),
        });
      } catch (err) {
        setError('Failed to send');
        setLoading(false);
      }
    },
    [
      input,
      loading,
      activeChatId,
      navigate,
      refreshChats,
      setActiveChatHasMessages,
      setActiveChatId,
    ],
  );

  const getExportForId = (id) =>
    messages.find((m, idx) => idx === id)?.downloadData || null;

  const transformAssistantContent = (raw) => {
    const contentForMd = sanitizeRender(
      (raw || '').replace(/```chart[\s\S]*?```/gi, ''),
    );
    return renderCardMarkdown(contentForMd);
  };

  return {
    messages,
    hasInteracted,
    input,
    setInput,
    loading,
    error,
    send,
    getExportForId,
    transformAssistantContent,
    extractChartSpec,
    sanitizeRender,
    endRef,
  };
}
