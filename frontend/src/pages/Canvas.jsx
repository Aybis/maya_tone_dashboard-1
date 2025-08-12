import React, { useEffect, useState, useRef, useCallback } from 'react';
import { marked } from 'marked';
import { io } from 'socket.io-client';
import { useChatContext } from '../context/ChatContext';

const Avatar = ({ sender }) => (
  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${sender === 'user' ? 'bg-blue-500' : 'bg-slate-600'}`}>{sender === 'user' ? 'U' : 'M'}</div>
);

export default function Canvas() {
  const { activeChatId, setActiveChatHasMessages } = useChatContext();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const socketRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (!activeChatId) return;
    let ignore = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/chat/${activeChatId}`);
        const data = await res.json();
        if (!ignore) setMessages(data);
      } catch (e) { if (!ignore) setError('Failed to load messages'); }
      finally { if (!ignore) setLoading(false); }
    };
    load();
    return () => { ignore = true; };
  }, [activeChatId]);

  useEffect(() => {
    if (!activeChatId) return;
    socketRef.current = io('http://localhost:4000');
    socketRef.current.emit('join_chat', { chat_id: activeChatId });
    socketRef.current.on('new_message', (data) => {
      if (data.chat_id === activeChatId) {
        setMessages(prev => [...prev, { sender: data.sender, content: data.content }]);
        setLoading(false);
      }
    });
    return () => { socketRef.current?.disconnect(); };
  }, [activeChatId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    if (!input.trim() || !activeChatId || loading) return;
    const msg = { sender: 'user', content: input };
    setMessages(prev => [...prev, msg]);
    const content = input; setInput(''); setLoading(true); setError('');
    try {
      const res = await fetch(`/api/chat/${activeChatId}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: content }) });
      if (!res.ok) throw new Error('Fail');
  setActiveChatHasMessages(true);
    } catch (e) { setError('Failed to send'); setLoading(false); }
  };

  // Extract latest assistant message containing a markdown table (| ... |) to show on canvas; ignore pure text
  const latestAssistant = [...messages].reverse().find(m => m.sender !== 'user' && /\|[^\n]*\|/.test(m.content || ''));

  const [canvasWidth, setCanvasWidth] = useState(0.65); // fraction of container
  const dragRef = useRef(null);
  const containerRef = useRef(null);

  const startDrag = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = canvasWidth;
    const onMove = (ev) => {
      const delta = ev.clientX - startX;
      const total = containerRef.current?.getBoundingClientRect().width || 1;
      let next = startWidth + delta / total;
      next = Math.min(0.8, Math.max(0.4, next));
      setCanvasWidth(next);
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [canvasWidth]);

  return (
    <div className="flex h-[calc(100vh-0px)]" ref={containerRef}>
      <div className="overflow-y-auto p-6 bg-[#0f0f23]/40 border-r border-blue-500/10" style={{ width: `${canvasWidth*100}%` }}>
        <h1 className="text-2xl font-bold mb-4 text-slate-50">Canvas</h1>
        <p className="text-slate-400 mb-6 max-w-2xl">Use the chat on the right to request charts, tables, or summaries. The AI can respond with markdown. Future enhancements will parse structured JSON blocks for dynamic charts.</p>
        <div className="space-y-6">
          {latestAssistant ? (
            <div className="bg-[#0f0f23]/70 border border-blue-500/10 rounded-lg p-4">
              <h2 className="text-slate-200 font-semibold mb-2">Latest Output</h2>
              <div className="prose prose-invert max-w-none [&_table]:w-full [&_table]:text-xs [&_table]:border [&_table]:border-slate-600/50 [&_th]:font-semibold [&_th]:text-slate-300 [&_th]:border [&_th]:border-slate-700/50 [&_td]:border [&_td]:border-slate-700/50 [&_td]:align-top [&_tbody_tr:nth-child(even)]:bg-slate-800/30" dangerouslySetInnerHTML={{ __html: marked.parse(latestAssistant.content || '') }} />
            </div>
          ) : (
            <div className="text-slate-500 italic">No AI output yet. Ask something like: "Show a bar chart of tickets by status".</div>
          )}
        </div>
      </div>
      <div ref={dragRef} onMouseDown={startDrag} className="w-1 bg-blue-500/30 cursor-col-resize hover:bg-blue-400/60 transition" />
      <div className="flex flex-col bg-slate-900/70" style={{ width: `${(1-canvasWidth)*100}%` }}>
        <div className="flex-1 overflow-y-auto p-4">
          {messages.map((m, i) => {
            const isTable = /\|[^\n]*\|/.test(m.content || '');
            // Skip assistant table messages (they go to canvas) but always show user + non-table assistant text
            if (m.sender !== 'user' && isTable) return null;
            return (
              <div key={i} className={`flex gap-3 my-4 ${m.sender === 'user' ? 'flex-row-reverse text-right' : ''}`}> 
                <Avatar sender={m.sender} />
                <div className={`max-w-xs md:max-w-sm p-3 rounded-lg prose prose-invert prose-sm ${m.sender === 'user' ? 'bg-blue-600' : 'bg-slate-700'}`} dangerouslySetInnerHTML={{ __html: marked.parse(m.content || '') }} />
              </div>
            );
          })}
          {loading && <div className="text-slate-400 text-sm">Thinking…</div>}
          <div ref={endRef} />
        </div>
        {error && <div className="text-red-400 text-xs px-4 mb-2">{error}</div>}
        <form onSubmit={send} className="p-4 border-t border-blue-500/10 bg-slate-900/80 flex gap-2">
          <input className="flex-1 rounded-lg bg-[#0f0f23]/80 border border-blue-500/30 px-3 py-2 text-slate-50 focus:outline-none focus:border-blue-400" placeholder="Ask for a visualization..." value={input} onChange={e => setInput(e.target.value)} />
          <button disabled={loading || !input.trim()} className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white disabled:opacity-50">Send</button>
        </form>
      </div>
    </div>
  );
}
