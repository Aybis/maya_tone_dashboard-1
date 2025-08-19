import React, {
  useEffect,
  useState,
  useRef,
  useCallback,
  useMemo,
} from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { marked } from 'marked';
import { io } from 'socket.io-client';
import { useChatContext } from '../context/ChatContext';
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Doughnut, Pie, Line } from 'react-chartjs-2';

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
);

const Avatar = ({ sender }) => (
  <div
    className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${sender === 'user' ? 'bg-blue-500' : 'bg-slate-600'
      }`}
  >
    {sender === 'user' ? 'U' : 'M'}
  </div>
);

export default function Canvas() {
  const {
    activeChatId,
    setActiveChatHasMessages,
    setActiveChatId,
    refreshChats,
  } = useChatContext();
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const socketRef = useRef(null);
  const endRef = useRef(null);

  // Sync route param to context
  useEffect(() => {
    if (chatId && chatId !== activeChatId) {
      setActiveChatId(chatId);
    }
  }, [chatId, activeChatId, setActiveChatId]);

  useEffect(() => {
    if (!activeChatId) return; // wait until context ready
    let ignore = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/chat/${activeChatId}`);
        if (res.status === 404 || res.status === 401) {
          // Chat doesn't exist or user doesn't have access
          if (!ignore) {
            setError('Chat not found or access denied');
            // Redirect to dashboard after a short delay
            setTimeout(() => {
              navigate('/', { replace: true });
            }, 2000);
          }
          return;
        }
        const data = await res.json();
        if (!ignore) setMessages(data);
      } catch (e) {
        if (!ignore) setError('Failed to load messages');
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    load();
    return () => {
      ignore = true;
    };
  }, [activeChatId, navigate]);

  useEffect(() => {
    if (!activeChatId) return;
    // Use current host instead of hardcoded localhost for network access
    const socketUrl = `${window.location.protocol}//${window.location.hostname}:4000`;
    socketRef.current = io(socketUrl);
    socketRef.current.emit('join_chat', { chat_id: activeChatId });
    socketRef.current.on('new_message', (data) => {
      if (data.chat_id === activeChatId) {
        setMessages((prev) => {
          if (data.sender === 'assistant') {
            const lastAssistant = [...prev]
              .reverse()
              .find((m) => m.sender === 'assistant');
            if (lastAssistant && lastAssistant.content === data.content)
              return prev; // dedupe
          }
          return [...prev, { sender: data.sender, content: data.content }];
        });
        setLoading(false);
      }
    });
    // Streaming events
    socketRef.current.on('assistant_start', ({ chat_id }) => {
      if (chat_id === activeChatId) {
        setLoading(true);
        setMessages((prev) => [...prev, { sender: 'assistant', content: '' }]);
      }
    });
    socketRef.current.on('assistant_delta', ({ chat_id, delta }) => {
      if (chat_id === activeChatId) {
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].sender === 'assistant') {
              copy[i] = {
                ...copy[i],
                content: (copy[i].content || '') + delta,
              };
              break;
            }
          }
          return copy;
        });
      }
    });
    socketRef.current.on('assistant_end', ({ chat_id, content }) => {
      if (chat_id === activeChatId) {
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].sender === 'assistant') {
              copy[i] = { ...copy[i], content };
              break;
            }
          }
          return copy;
        });
        setLoading(false);
        setActiveChatHasMessages(true);
      }
    });
    socketRef.current.on('assistant_error', ({ chat_id, error }) => {
      if (chat_id === activeChatId) {
        setError(error);
        setLoading(false);
      }
    });
    return () => {
      socketRef.current?.disconnect();
    };
  }, [activeChatId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const content = input;
    setInput('');
    setLoading(true);
    setError('');
    // If no active chat yet (user just on /canvas), create + ask in one go
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
    // Existing chat flow
    const msg = { sender: 'user', content };
    setMessages((prev) => [...prev, msg]);
    try {
      await fetch(`/api/chat/${activeChatId}/ask_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
      });
      // Stream events will handle state updates
    } catch (err) {
      setError('Failed to send');
      setLoading(false);
    }
  };

  // Extract latest assistant message containing a markdown table (| ... |) to show on canvas; ignore pure text
  // Extract latest assistant message containing either a markdown table OR a chart specification fence
  const latestAssistant = useMemo(() => {
    return [...messages].reverse().find((m) => {
      if (m.sender === 'user') return false;
      const content = m.content || '';
      const hasTable = /\|[^\n]*\|/.test(content);
      const hasChartFence = /```chart[\s\S]*?```/i.test(content);
      return hasTable || hasChartFence;
    });
  }, [messages]);

  // Parse chart specification from assistant message (if present)
  const chartSpec = useMemo(() => {
    if (!latestAssistant) return null;
    const content = latestAssistant.content || '';
    const match = content.match(/```chart\s*\n([\s\S]*?)```/i);
    if (!match) return null;
    try {
      const json = JSON.parse(match[1]);
      return json;
    } catch (e) {
      return null;
    }
  }, [latestAssistant]);

  // Live chart (B) + auto insight (C)
  const [liveChart, setLiveChart] = useState(null);
  const [autoInsight, setAutoInsight] = useState(true);
  const fetchingRef = useRef(false);

  const effectiveChartSpec = liveChart || chartSpec;

  const chartComponent = useMemo(() => {
    if (!effectiveChartSpec) return null;
    const { type, labels = [], datasets = [] } = effectiveChartSpec;
    const data = { labels, datasets: datasets.map((ds) => ({ ...ds })) };
    const baseOptions = {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: type === 'doughnut' || type === 'pie' ? 1.4 : 1.6,
      plugins: {
        legend: { display: true, position: 'bottom' },
        title: {
          display: !!effectiveChartSpec.title,
          text: effectiveChartSpec.title,
        },
      },
    };
    if (type === 'bar' || type === 'bar-vertical') {
      return <Bar data={data} options={baseOptions} />;
    }
    if (type === 'bar-horizontal') {
      const options = { ...baseOptions, indexAxis: 'y' };
      return <Bar data={data} options={options} />;
    }
    if (type === 'line') return <Line data={data} options={baseOptions} />;
    if (type === 'pie') return <Pie data={data} options={baseOptions} />;
    if (type === 'doughnut')
      return <Doughnut data={data} options={baseOptions} />;
    return null;
  }, [effectiveChartSpec]);

  // Dynamic filter scaffold (future: will re-request data with refined filters via AI)
  const [filters, setFilters] = useState({
    status: [],
    assignee: [],
    project: [],
  });
  const availableFilters = useMemo(
    () => chartSpec?.meta?.filters || {},
    [chartSpec],
  );
  const updateFilter = (key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: prev[key].includes(value)
        ? prev[key].filter((v) => v !== value)
        : [...prev[key], value],
    }));
  };
  // --- Dynamic Form State ---
  const [form, setForm] = useState({ group_by: '', from: '', to: '' });
  // Initialize form whenever a new chart arrives
  useEffect(() => {
    if (chartSpec?.meta) {
      setForm({
        group_by: chartSpec.meta.group_by || 'status',
        from: chartSpec.meta.from || '',
        to: chartSpec.meta.to || '',
      });
      // seed filters from meta
      if (chartSpec.meta.filters) setFilters(chartSpec.meta.filters);
    }
  }, [chartSpec]);

  const derivedFilterChoices = useMemo(() => {
    const distincts = chartSpec?.distincts || chartSpec?.meta?.distincts;
    if (distincts) {
      return {
        status: distincts.status || [],
        assignee: distincts.assignee || [],
        project: distincts.project || [],
      };
    }
    return {
      status:
        chartSpec?.meta?.group_by === 'status'
          ? chartSpec?.labels || []
          : chartSpec?.meta?.filters?.status || [],
      assignee:
        chartSpec?.meta?.group_by === 'assignee'
          ? chartSpec?.labels || []
          : chartSpec?.meta?.filters?.assignee || [],
      project:
        chartSpec?.meta?.group_by === 'project'
          ? chartSpec?.labels || []
          : chartSpec?.meta?.filters?.project || [],
    };
  }, [chartSpec]);

  // When a new AI chart (chartSpec) appears and no insight line present, prepare an insight prompt automatically
  useEffect(() => {
    if (!chartSpec) return;
    if (!autoInsight) return;
    const content = latestAssistant?.content || '';
    if (/Insight:/i.test(content)) return; // already has insight
    setInput(
      (prev) =>
        prev ||
        `Berikan insight singkat (1-2 kalimat) tentang distribusi ${chartSpec.meta?.group_by || 'data'
        } di atas. Mulai langsung tanpa salam.`,
    );
  }, [chartSpec, autoInsight, latestAssistant]);

  const updateForm = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const buildRefinePrompt = () => {
    const { group_by, from, to } = form;
    const filterSegments = Object.entries(filters)
      .filter(([, arr]) => arr.length)
      .map(([k, arr]) => `${k}=${arr.join(',')}`);
    return `Refine the previous chart using aggregate_issues. group_by=${group_by}. from=${from || 'unchanged'
      } to=${to || 'unchanged'} filters=${filterSegments.join('; ') || 'none'
      }. Return ONLY a chart spec code fence (chart).`;
  };

  const requestRefine = () => {
    if (!chartSpec) return;
    // Basic validation: if both dates provided and reversed, swap
    if (form.from && form.to && form.from > form.to) {
      setForm((f) => ({ ...f, from: form.to, to: form.from }));
    }
    setInput(buildRefinePrompt());
  };

  // Direct backend aggregation call (B)
  const callBackendAggregate = useCallback(
    async (reason = 'change') => {
      if (fetchingRef.current) return;
      fetchingRef.current = true;
      try {
        const res = await fetch('/api/chart/aggregate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            group_by: form.group_by,
            from: form.from || null,
            to: form.to || null,
            filters,
          }),
        });
        const data = await res.json();
        if (data.success) {
          if (autoInsight && reason === 'change') {
            setLiveChart(data.chart);
            const prompt = `Provide a concise updated insight (no greeting). Group by ${form.group_by
              }. Range ${form.from || 'default'} to ${form.to || 'default'}.`;
            setInput(prompt);
          }
        }
      } catch (e) {
        /* ignore */
      } finally {
        fetchingRef.current = false;
      }
    },
    [form, filters, autoInsight],
  );

  // Auto trigger (A) debounce
  // useEffect(() => {
  //   if (!form.group_by) return;
  //   const t = setTimeout(() => callBackendAggregate('change'), 350);
  //   return () => clearTimeout(t);
  // }, [form.group_by, form.from, form.to, filters, callBackendAggregate]);

  const [canvasWidth, setCanvasWidth] = useState(0.55); // fraction of container (slightly smaller chart pane)
  const [chartSize, setChartSize] = useState('md'); // sm | md | lg
  const chartSizeClass =
    chartSize === 'sm'
      ? 'max-w-[380px]'
      : chartSize === 'lg'
        ? 'max-w-[860px]'
        : 'max-w-[640px]';
  const dragRef = useRef(null);
  const containerRef = useRef(null);

  const startDrag = useCallback(
    (e) => {
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
    },
    [canvasWidth],
  );

  return (
    <div className="flex h-[calc(100vh-0px)]" ref={containerRef}>
      <div
        className="overflow-y-auto p-6 bg-[#0f0f23]/40 border-r border-blue-500/10"
        style={{ width: `${canvasWidth * 100}%` }}
      >
        <h1 className="text-2xl font-bold mb-4 text-slate-50">Canvas</h1>
        <p className="text-slate-400 mb-6 max-w-2xl">
          Use the chat on the right to request charts, tables, or summaries.
        </p>
        <div className="space-y-6">
          {latestAssistant ? (
            <div className="bg-[#0f0f23]/70 border border-blue-500/10 rounded-lg p-4 space-y-4">
              <h2 className="text-slate-200 font-semibold">Latest Output</h2>
              {loading && !chartComponent && (
                <div className="text-[13px] text-slate-500 italic animate-pulse">
                  Thinking…
                </div>
              )}
              {chartComponent && (
                <div className="space-y-4">
                  <div
                    className={`w-full mx-auto ${chartSizeClass} transition-all duration-300 bg-slate-900/40 rounded-lg p-4 shadow-inner flex items-center justify-center`}
                  >
                    <div className="w-full">{chartComponent}</div>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500">
                    <label className="flex items-center gap-1 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        className="accent-blue-600"
                        checked={autoInsight}
                        onChange={(e) => setAutoInsight(e.target.checked)}
                      />
                      Auto insight
                    </label>
                    {liveChart && !chartSpec && (
                      <span className="text-amber-400">
                        Live preview (no AI summary yet)
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2 text-xs">
                    <span className="text-slate-500">Size:</span>
                    {['sm', 'md', 'lg'].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setChartSize(s)}
                        className={`px-2 py-1 rounded border text-[11px] ${chartSize === s
                          ? 'bg-blue-600 border-blue-500 text-white'
                          : 'bg-slate-800/60 border-slate-600 hover:border-slate-500'
                          }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  {effectiveChartSpec?.meta && (
                    <div className="text-xs text-slate-300 space-y-3">
                      <div className="flex flex-wrap gap-4">
                        <div className="space-y-1">
                          <label className="block text-[10px] uppercase tracking-wide text-slate-500">
                            Group By
                          </label>
                          <select
                            value={form.group_by}
                            onChange={(e) =>
                              updateForm('group_by', e.target.value)
                            }
                            className="bg-slate-800/70 border border-slate-600 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
                          >
                            {[
                              'status',
                              'priority',
                              'assignee',
                              'type',
                              'created_date',
                            ].map((g) => (
                              <option key={g} value={g}>
                                {g}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="block text-[10px] uppercase tracking-wide text-slate-500">
                            From
                          </label>
                          <input
                            type="date"
                            value={form.from}
                            onChange={(e) => updateForm('from', e.target.value)}
                            className="bg-slate-800/70 border border-slate-600 rounded px-2 py-1 text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="block text-[10px] uppercase tracking-wide text-slate-500">
                            To
                          </label>
                          <input
                            type="date"
                            value={form.to}
                            onChange={(e) => updateForm('to', e.target.value)}
                            className="bg-slate-800/70 border border-slate-600 rounded px-2 py-1 text-xs"
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-4">
                        {Object.entries(derivedFilterChoices).map(
                          ([k, arr]) => (
                            <div
                              key={k}
                              className="bg-slate-800/40 p-2 rounded min-w-[140px]"
                            >
                              <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">
                                {k}
                              </div>
                              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto pr-1">
                                {arr.slice(0, 50).map((val) => (
                                  <button
                                    type="button"
                                    key={val}
                                    onClick={() => updateFilter(k, val)}
                                    className={`px-2 py-0.5 rounded text-[10px] border ${filters[k]?.includes(val)
                                      ? 'bg-blue-600 border-blue-500 text-white'
                                      : 'bg-slate-700/60 border-slate-600 hover:border-slate-500'
                                      }`}
                                  >
                                    {val}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="flex gap-2 pt-1">
                        <button
                          type="button"
                          onClick={requestRefine}
                          className="px-3 py-1.5 rounded bg-gradient-to-r from-blue-500 to-blue-700 text-white text-xs hover:from-blue-400 hover:to-blue-600"
                        >
                          AI Refine (Prompt)
                        </button>
                        <button
                          type="button"
                          onClick={() => callBackendAggregate('manual')}
                          className="px-3 py-1.5 rounded bg-slate-700 text-slate-200 text-xs hover:bg-slate-600"
                        >
                          Refresh Data
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setFilters({
                              status: [],
                              assignee: [],
                              project: [],
                            });
                            setForm((f) => ({
                              ...f,
                              group_by: chartSpec.meta.group_by,
                              from: chartSpec.meta.from,
                              to: chartSpec.meta.to,
                            }));
                          }}
                          className="px-3 py-1.5 rounded bg-slate-700 text-slate-200 text-xs hover:bg-slate-600"
                        >
                          Reset
                        </button>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Prompt will be prepared in the input; you can adjust
                        before sending.
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div
                className="prose prose-invert max-w-none [&_table]:w-full [&_table]:text-xs [&_table]:border [&_table]:border-slate-600/50 [&_th]:font-semibold [&_th]:text-slate-300 [&_th]:border [&_th]:border-slate-700/50 [&_td]:border [&_td]:border-slate-700/50 [&_td]:align-top [&_tbody_tr:nth-child(even)]:bg-slate-800/30"
                dangerouslySetInnerHTML={{
                  __html: marked.parse(
                    (latestAssistant.content || '').replace(
                      /```chart[\s\S]*?```/gi,
                      '',
                    ),
                  ),
                }}
              />
            </div>
          ) : (
            <div className="text-slate-500 italic">
              No AI output yet. Ask something like: "Show a bar chart of tickets
              by status".
            </div>
          )}
        </div>
      </div>
      <div
        ref={dragRef}
        onMouseDown={startDrag}
        className="w-1 bg-blue-500/30 cursor-col-resize hover:bg-blue-400/60 transition"
      />
      <div
        className="flex flex-col bg-slate-900/70 min-w-[300px]"
        style={{ width: `${(1 - canvasWidth) * 100}%` }}
      >
        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {messages.map((m, i) => {
            const isTable = /\|[^\n]*\|/.test(m.content || '');
            // Skip assistant table messages (they go to canvas) but always show user + non-table assistant text
            if (m.sender !== 'user' && isTable) return null;
            return (
              <div
                key={i}
                className={`flex gap-3 my-4 ${m.sender === 'user' ? 'flex-row-reverse' : ''
                  }`}
              >
                <Avatar sender={m.sender} />
                <div
                  className={`max-w-full md:max-w-md lg:max-w-lg xl:max-w-xl p-3 rounded-lg prose prose-invert prose-sm break-words ${m.sender === 'user' ? 'bg-blue-600' : 'bg-slate-700'
                    } [&_pre]:whitespace-pre-wrap [&_pre]:max-h-60 [&_pre]:overflow-y-auto [&_code]:break-words`}
                  dangerouslySetInnerHTML={{
                    __html: marked.parse(m.content || ''),
                  }}
                />
              </div>
            );
          })}
          {loading && <div className="text-slate-400 text-sm">Thinking…</div>}
          <div ref={endRef} />
        </div>
        {error && <div className="text-red-400 text-xs px-4 mb-2">{error}</div>}
        <form
          onSubmit={send}
          className="p-4 border-t border-blue-500/10 bg-slate-900/80 flex gap-2"
        >
          <input
            className="flex-1 rounded-lg bg-[#0f0f23]/80 border border-blue-500/30 px-3 py-2 text-slate-50 focus:outline-none focus:border-blue-400"
            placeholder="Ask for a visualization..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            disabled={loading || !input.trim()}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
