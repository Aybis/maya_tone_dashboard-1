import React, { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { marked } from 'marked'; // Import library marked

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
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
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
        setMessages(prev => [...prev, { sender: data.sender, content: data.content }]);
        setIsLoading(false);
      }
    });
    return () => {
      socketRef.current.disconnect();
    };
  }, [activeChatId]);

  // Fetch chat history and initialize first chat session
  useEffect(() => {
    const initializeChat = async () => {
      try {
        const historyRes = await fetch('/api/chat/history');
        const historyData = await historyRes.json();
        setChats(historyData);

        if (historyData.length > 0) {
          setActiveChatId(historyData[0].id);
        } else {
          await createNewChat();
        }
      } catch (err) {
        setError('Failed to initialize chat history.');
      }
    };
    initializeChat();
  }, []);

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

  const createNewChat = async () => {
    try {
        const res = await fetch('/api/chat/new', { method: 'POST' });
        const data = await res.json();
        setChats(prev => [{ id: data.chat_id, title: `Chat ${new Date().getHours()}:${new Date().getMinutes()}` }, ...prev]);
        setActiveChatId(data.chat_id);
        setMessages([]);
    } catch (err) {
        setError('Failed to create a new chat.');
    }
  };

  // --- NEW --- Function to handle chat deletion
  const handleDeleteChat = async (chatIdToDelete, e) => {
    e.stopPropagation(); // Prevent selecting the chat when clicking the delete button

    if (!window.confirm('Are you sure you want to permanently delete this chat?')) {
      return;
    }

    try {
      const res = await fetch(`/api/chat/${chatIdToDelete}/delete`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || 'Failed to delete chat.');
      }

      const updatedChats = chats.filter(chat => chat.id !== chatIdToDelete);
      setChats(updatedChats);

      // If the deleted chat was the active one, switch to another chat
      if (activeChatId === chatIdToDelete) {
        if (updatedChats.length > 0) {
          setActiveChatId(updatedChats[0].id);
        } else {
          await createNewChat(); // Create a new chat if no chats are left
        }
      }
    } catch (err) {
      setError(err.message);
    }
  };


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
      const res = await fetch(`/api/chat/${activeChatId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentMessage }),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.answer || 'Network response was not ok.');
      }
    } catch (err) {
      setError(`Failed to send message: ${err.message}`);
      setNewMessage(currentMessage);
      setMessages(prev => prev.filter(msg => msg !== userMessage));
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-100px)] bg-[#0f0f23]/60 text-slate-50">
      {/* Sidebar for Chat History */}
      <aside className="w-64 bg-slate-900/50 p-4 flex flex-col border-r border-blue-500/10">
        <button
          onClick={createNewChat}
          className="w-full mb-4 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow hover:-translate-y-1 transition"
        >
          + New Chat
        </button>
        <div className="flex-1 overflow-y-auto">
          {/* --- MODIFIED --- Mapped chats to include delete button */}
          {chats.map(chat => (
            <div
              key={chat.id}
              onClick={() => setActiveChatId(chat.id)}
              className={`group flex items-center justify-between p-2 my-1 rounded cursor-pointer text-sm ${activeChatId === chat.id ? 'bg-blue-500/30 font-bold' : 'hover:bg-slate-700/50'}`}
            >
              <span className="truncate pr-2">{chat.title}</span>
              <button
                onClick={(e) => handleDeleteChat(chat.id, e)}
                className="text-slate-500 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                aria-label="Delete chat"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Chat Window */}
      <main className="flex-1 flex flex-col p-4">
        <div className="flex-1 overflow-y-auto mb-4 pr-4">
          {messages.map((msg, index) => (
            <div key={index} className={`flex items-start gap-3 my-4 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}>
              <Avatar sender={msg.sender} />
              <div
                className={`max-w-xl p-3 rounded-lg prose prose-invert prose-sm ${
                  msg.sender === 'user'
                    ? 'bg-blue-600'
                    : 'bg-slate-700'
                }`}
                dangerouslySetInnerHTML={{ __html: marked.parse(msg.content || '') }}
              />
            </div>
          ))}
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
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Ask Maya anything about Jira..."
            className="flex-1 px-5 py-3 rounded-lg border-2 border-blue-500/20 bg-[#0f0f23]/80 text-slate-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
          <button
            type="submit"
            disabled={isLoading || !newMessage.trim()}
            className="px-8 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow hover:-translate-y-1 transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}