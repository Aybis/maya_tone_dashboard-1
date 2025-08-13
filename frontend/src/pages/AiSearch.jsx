import React, { useState, useEffect, useRef, useCallback } from "react";
import { marked } from "marked";
import { useChatContext } from "../context/ChatContext";
import { useUI } from "../layout/UIContext";
import ChatHeader from "../components/ChatHeader";
import MessageBubble from "../components/MessageBubble";
import ArtifactSidePanel from "../components/ArtifactSidePanel";
import Avatar from "../components/ui/Avatar";
import { useSocketChat } from "../hooks/useSocketChat";
import { useArtifacts } from "../hooks/useArtifacts";

export default function AiChat() {
  const {
    activeChatId,
    finalizeTempChat,
    setActiveChatHasMessages,
    providers,
    activeProvider,
    switchProvider,
    chats,
  } = useChatContext();
  const { setSidebarAutoHidden } = useUI();
  const [newMessage, setNewMessage] = useState("");
  const messagesEndRef = useRef(null);
  const { messages, isLoading, error, sendUserMessage } = useSocketChat({
    activeChatId,
    chats,
    finalizeTempChat,
    activeProvider,
    setActiveChatHasMessages,
  });
  const [chartOverrides, setChartOverrides] = useState({}); // id -> overridden spec
  const {
    parsedMessages,
    sideArtifact,
    setSideArtifact,
    panelOpen,
    setPanelOpen,
    panelWidth,
    setPanelWidth,
  } = useArtifacts(messages, chartOverrides);
  const panelRef = useRef(null);
  const dragRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  // markdown helpers
  marked.setOptions({ breaks: true, gfm: true });
  const renderMarkdown = (raw) => {
    try {
      return marked.parse(raw || "");
    } catch {
      return raw;
    }
  };
  const copyToClipboard = (t) =>
    navigator.clipboard.writeText(t).catch(() => {});
  const scrollToBottom = () =>
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(scrollToBottom, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const msg = newMessage;
    if (!msg.trim()) return;
    setNewMessage("");
    await sendUserMessage({ content: msg });
  };

  // panel resize drag
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e) => {
      if (!panelRef.current) return;
      const rect = panelRef.current.parentElement.getBoundingClientRect();
      const rel = e.clientX - rect.left;
      let pct = ((rect.width - rel) / rect.width) * 100;
      pct = Math.min(80, Math.max(25, Math.round(pct)));
      setPanelWidth(pct);
    };
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, setPanelWidth]);

  // keep sidebar visible
  useEffect(() => {
    setSidebarAutoHidden(false);
  }, [panelOpen, setSidebarAutoHidden]);

  // shortcuts
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        window.dispatchEvent(new Event("open-search"));
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        window.dispatchEvent(new Event("toggle-sidebar"));
      }
      if (e.key === "ArrowLeft" && panelOpen) {
        const flat = parsedMessages.flatMap((m) => m.artifacts || []);
        if (!sideArtifact) return;
        const i = flat.findIndex((a) => a.id === sideArtifact.id);
        if (i > 0) setSideArtifact(flat[i - 1]);
      }
      if (e.key === "ArrowRight" && panelOpen) {
        const flat = parsedMessages.flatMap((m) => m.artifacts || []);
        if (!sideArtifact) return;
        const i = flat.findIndex((a) => a.id === sideArtifact.id);
        if (i >= 0 && i < flat.length - 1) setSideArtifact(flat[i + 1]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [panelOpen, sideArtifact, parsedMessages]);

  // export helpers
  const exportPNG = (artifact) => {
    if (!artifact || artifact.type !== "chart") return;
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    const link = document.createElement("a");
    link.download = `${artifact.label || "chart"}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  };
  const exportCSV = (artifact) => {
    if (!artifact) return;
    if (artifact.type === "chart") {
      const spec = artifact.data || {};
      const data = spec.data || {
        labels: spec.labels || [],
        datasets: spec.datasets || [],
      };
      const labels = data.labels || [];
      const datasets = data.datasets || [];
      let csv = "label," + datasets.map((d) => d.label).join(",") + "\n";
      labels.forEach((lbl, i) => {
        const row = [lbl];
        datasets.forEach((ds) => row.push(ds.data ? ds.data[i] : ""));
        csv += row.join(",") + "\n";
      });
      const blob = new Blob([csv], { type: "text/csv" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${artifact.label || "chart"}.csv`;
      link.click();
    } else if (artifact.type === "table") {
      const tbl = artifact.data;
      let csv = tbl.columns.join(",") + "\n";
      tbl.rows.forEach((r) => {
        csv += r.join(",") + "\n";
      });
      const blob = new Blob([csv], { type: "text/csv" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${artifact.label || "table"}.csv`;
      link.click();
    }
  };
  const exportJSON = (artifact) => {
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.data, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${artifact.label || artifact.id}.json`;
    link.click();
  };

  // dynamic chart control regeneration
  const onChartControlsChange = useCallback((controls, artifact) => {
    if (!artifact || artifact.type !== "chart") return;
    const base = JSON.parse(JSON.stringify(artifact._orig || artifact.data));
    // Filter by selected statuses (labels)
    if (
      Array.isArray(controls.statuses) &&
      controls.statuses.length &&
      base.data?.labels
    ) {
      const keep = new Set(controls.statuses);
      const indices = base.data.labels
        .map((l, i) => (keep.has(l) ? i : -1))
        .filter((i) => i >= 0);
      if (indices.length) {
        base.data.labels = indices.map((i) => base.data.labels[i]);
        base.data.datasets = (base.data.datasets || []).map((ds) => ({
          ...ds,
          data: indices.map((i) => ds.data?.[i] ?? 0),
        }));
      }
    }
    // Update title with groupBy
    if (controls.groupBy) {
      base.options = base.options || {};
      base.options.plugins = base.options.plugins || {};
      base.options.plugins.title = base.options.plugins.title || {};
      const originalTitle =
        artifact._orig?.options?.plugins?.title?.text ||
        base.options.plugins.title.text ||
        base.title ||
        "Chart";
      base.options.plugins.title.text =
        originalTitle.split(" (by ")[0] + ` (by ${controls.groupBy})`;
    }
    // Size mapping -> set CSS var
    const sizeH =
      controls.size === "sm" ? 220 : controls.size === "lg" ? 460 : 320;
    document.documentElement.style.setProperty("--chart-height", sizeH + "px");
    setChartOverrides((prev) => ({ ...prev, [artifact.id]: base }));
    // update sideArtifact reference for immediate panel refresh
    setSideArtifact((a) =>
      a && a.id === artifact.id ? { ...a, data: base } : a,
    );
  }, []);

  const mainWidth = panelOpen ? `${100 - panelWidth}%` : "100%";

  return (
    <div className="relative flex h-[calc(100vh-0px)] bg-zinc-100 text-slate-800 dark:bg-[#0f0f23]/60 dark:text-slate-50 overflow-hidden">
      <main
        className="flex flex-col p-4 transition-[width] duration-300 ease-out"
        style={{ width: mainWidth }}
      >
        {activeChatId && (
          <ChatHeader
            chats={chats}
            activeChatId={activeChatId}
            switchProvider={switchProvider}
            activeProvider={activeProvider}
            providers={providers}
          />
        )}

        {!messages.length && (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-8">
            <div className="space-y-4 max-w-xl">
              <h1 className="text-3xl font-semibold bg-gradient-to-r from-blue-400 to-fuchsia-400 bg-clip-text text-transparent">
                Start a New Chat
              </h1>
              <p className="text-slate-400 text-sm">
                Select a model below and ask anything about your Jira data.
                Switching models creates a new chat.
              </p>
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400">Model</label>
                  <select
                    value={activeProvider}
                    onChange={(e) => switchProvider(e.target.value)}
                    className="bg-slate-800 text-slate-100 text-xs rounded px-3 py-2 border border-slate-600"
                  >
                    {providers.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="text-[11px] text-slate-500">
                  Default provider set server-side.
                </div>
              </div>
            </div>
            <form
              onSubmit={handleSendMessage}
              className="w-full max-w-2xl flex flex-col gap-3"
            >
              <textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                rows={3}
                placeholder="Ask your first question..."
                className="w-full resize-none px-5 py-4 rounded-xl border-2 border-blue-300 dark:border-blue-500/20 bg-white dark:bg-[#0f0f23]/80 text-slate-800 dark:text-slate-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-500">
                  Shift+Enter newline
                </span>
                <button
                  type="submit"
                  disabled={!newMessage.trim()}
                  className="px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="flex-1 overflow-y-auto mb-4 pr-4">
          <div
            className={`${panelOpen ? "max-w-[1400px]" : "max-w-4xl"} mx-auto`}
          >
            {parsedMessages.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                index={i}
                panelOpen={panelOpen}
                renderMarkdown={renderMarkdown}
                copyToClipboard={copyToClipboard}
                onExpandArtifact={(a) => {
                  setSideArtifact(a);
                  setPanelOpen(true);
                }}
              />
            ))}
            {isLoading && (
              <div className="flex items-start gap-3 my-4">
                <Avatar sender="assistant" />
                <div className="p-3 rounded-lg bg-slate-700">
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                    <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse [animation-delay:0.2s]" />
                    <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse [animation-delay:0.4s]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {error && (
          <p className="text-red-400 text-center text-sm mb-2">{error}</p>
        )}

        {!!messages.length && (
          <form onSubmit={handleSendMessage} className="flex gap-4 mt-6">
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              placeholder="Ask Maya anything about Jira... (Markdown supported)"
              rows={2}
              className="flex-1 resize-none px-5 py-3 rounded-lg border-2 border-blue-300 dark:border-blue-500/20 bg-white dark:bg-[#0f0f23]/80 text-slate-800 dark:text-slate-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            />
            <div className="flex flex-col gap-2">
              <button
                type="submit"
                disabled={isLoading || !newMessage.trim()}
                className="h-full px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow hover:-translate-y-1 transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Send
              </button>
              <span className="text-[10px] text-slate-500 text-center">
                Shift+Enter = newline
              </span>
            </div>
          </form>
        )}

        <ArtifactSidePanel
          panelOpen={panelOpen}
          sideArtifact={sideArtifact}
          panelWidth={panelWidth}
          setSideArtifact={setSideArtifact}
          setPanelOpen={setPanelOpen}
          parsedMessages={parsedMessages}
          exportPNG={exportPNG}
          exportCSV={exportCSV}
          exportJSON={exportJSON}
          setDragging={setDragging}
          panelRef={panelRef}
          dragRef={dragRef}
          onChartControlsChange={onChartControlsChange}
        />
      </main>
    </div>
  );
}
