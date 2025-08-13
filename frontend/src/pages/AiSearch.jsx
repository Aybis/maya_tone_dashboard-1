import React, { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { marked } from 'marked';
import { useChatContext } from '../context/ChatContext';

// Helper component for user/AI avatars
const Avatar = ({ sender }) => {
  const isUser = sender === 'user';
  return (
    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold self-start ${isUser ? 'bg-blue-500' : 'bg-slate-600'}`}>
      {isUser ? 'U' : 'M'}
    </div>
  );
};

// Main Chat Component
export default function AiChat() {
  const { activeChatId, createNewChat, setActiveChatHasMessages } = useChatContext();
  // Ensure a chat exists when landing directly on AI Search
  useEffect(() => {
    if (!activeChatId) createNewChat();
  }, [activeChatId, createNewChat]);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);
  const socketRef = useRef(null);

  // Scroll to the bottom of the messages list
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  // Initialize and manage Socket.IO connection
  useEffect(() => {
    socketRef.current = io('http://localhost:4000');
    socketRef.current.on('connect', () => console.log('Socket connected successfully'));
    socketRef.current.on('new_message', (data) => {
      if (data.chat_id === activeChatId) {
        setMessages(prev => {
          if (data.sender === 'assistant') {
            const lastAssistant = [...prev].reverse().find(m => m.sender === 'assistant');
            if (lastAssistant && lastAssistant.content === data.content) return prev;
          }
          return [...prev, { sender: data.sender, content: data.content }];
        });
        setIsLoading(false);
      }
    });
  socketRef.current.on('assistant_start', ({ chat_id }) => { if (chat_id === activeChatId) { setIsLoading(true); setMessages(prev => [...prev, { sender: 'assistant', content: '' }]); }});
  socketRef.current.on('assistant_delta', ({ chat_id, delta }) => { if (chat_id === activeChatId) { setMessages(prev => { const copy=[...prev]; for (let i=copy.length-1;i>=0;i--){ if(copy[i].sender==='assistant'){ copy[i]={...copy[i], content:(copy[i].content||'')+delta}; break;} } return copy; }); }});
  socketRef.current.on('assistant_end', ({ chat_id, content }) => { if (chat_id === activeChatId) { setMessages(prev => { const copy=[...prev]; for (let i=copy.length-1;i>=0;i--){ if(copy[i].sender==='assistant'){ copy[i]={...copy[i], content}; break;} } return copy; }); setIsLoading(false); }});
  socketRef.current.on('assistant_error', ({ chat_id, error }) => { if (chat_id === activeChatId) { setError(error); setIsLoading(false); }});
    return () => {
      socketRef.current.disconnect();
    };
  }, [activeChatId]);

  // Fetch messages for the active chat
  useEffect(() => {
    if (!activeChatId) return;

    const fetchMessages = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/chat/${activeChatId}`);
        const data = await res.json();
        setMessages(data);
        socketRef.current.emit('join_chat', { chat_id: activeChatId });
      } catch (err) {
        setError('Failed to fetch messages.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchMessages();
  }, [activeChatId]);


  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !activeChatId || isLoading) return;

    const userMessage = { sender: 'user', content: newMessage };
    setMessages(prev => [...prev, userMessage]);
    const currentMessage = newMessage;
    setNewMessage('');
    setIsLoading(true);
    setError('');

    try {
  await fetch(`/api/chat/${activeChatId}/ask_stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: currentMessage }) });
  setActiveChatHasMessages(true);
    } catch (err) {
      setError(`Failed to send message: ${err.message}`);
      setNewMessage(currentMessage);
      setMessages(prev => prev.filter(msg => msg !== userMessage));
      setIsLoading(false);
    }
  };

  // Configure marked options (safe-ish basic) with code block highlighting placeholders
  marked.setOptions({
    breaks: true,
    gfm: true
  });

  const renderMarkdown = (raw) => {
    try {
      return marked.parse(raw || '');
    } catch (e) {
      return raw;
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="flex h-[calc(100vh-0px)] bg-[#0f0f23]/60 text-slate-50">
      <main className="flex-1 flex flex-col p-4">
        <div className="flex-1 overflow-y-auto mb-4 pr-4">
          {messages.map((msg, index) => {
            const isUser = msg.sender === 'user';
            return (
              <div key={index} className={`group relative flex items-start gap-3 my-6 ${isUser ? 'flex-row-reverse' : ''}`}>
                <Avatar sender={msg.sender} />
                <div className={`max-w-2xl w-full rounded-lg prose prose-invert prose-sm leading-relaxed ${isUser ? 'bg-blue-600 p-3' : 'bg-slate-700/70 p-4 border border-blue-500/10'} [&_pre]:bg-slate-900 [&_pre]:p-3 [&_pre]:rounded-md [&_code]:text-pink-300 [&_a]:text-blue-300 [&_table]:w-full [&_table]:text-xs [&_table]:border [&_table]:border-slate-600/50 [&_th]:bg-slate-800/70 [&_th]:border [&_th]:border-slate-700/50 [&_td]:border [&_td]:border-slate-700/50 [&_tbody_tr:nth-child(even)]:bg-slate-800/30 overflow-x-scroll`}>
                  <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                  {!isUser && (
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-2 text-[10px] mt-2 overflow-x-auto">
                      <button onClick={() => copyToClipboard(msg.content)} className="px-2 py-1 rounded bg-slate-800/70 hover:bg-slate-700 text-slate-300">Copy</button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {isLoading && (
            <div className="flex items-start gap-3 my-4">
              <Avatar sender="assistant" />
              <div className="p-3 rounded-lg bg-slate-700">
                <div className="flex items-center justify-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse [animation-delay:0.2s]"></div>
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse [animation-delay:0.4s]"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        {error && <p className="text-red-400 text-center text-sm mb-2">{error}</p>}
        <form onSubmit={handleSendMessage} className="flex gap-4">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Ask Maya anything about Jira... (Markdown supported)"
            rows={2}
            className="flex-1 resize-none px-5 py-3 rounded-lg border-2 border-blue-500/20 bg-[#0f0f23]/80 text-slate-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
          <div className="flex flex-col gap-2">
            <button
              type="submit"
              disabled={isLoading || !newMessage.trim()}
              className="h-full px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow hover:-translate-y-1 transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Send
            </button>
            <span className="text-[10px] text-slate-500 text-center">Shift+Enter = newline</span>
          </div>
        </form>
      </main>
    </div>
  );
}