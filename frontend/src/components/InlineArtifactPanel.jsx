import React, { useEffect, useMemo, useState, useCallback } from "react";
import ArtifactList from "./chart-canvas/ArtifactList";
import ArtifactDetail from "./chart-canvas/ArtifactDetail";

// Inline artifact panel displayed within chat scroll allowing toggle of detail canvas
export default function InlineArtifactPanel({ messages, chatId }) {
  const [selectedId, setSelectedId] = useState();
  const [pins, setPins] = useState({});
  const [customNames, setCustomNames] = useState({});
  const [deletedIds, setDeletedIds] = useState(new Set());
  const [showCanvas, setShowCanvas] = useState(true); // inline collapsed/expanded
  const [showOverlay, setShowOverlay] = useState(false); // full-screen canvas modal

  // Extract artifacts from assistant messages
  const artifacts = useMemo(() => {
    const list = [];
    messages.forEach((m, msgIdx) => {
      if (m.sender !== "assistant" || !m.content) return;
      const text = m.content;
      // Chart specs inside ```json or ```chart fences
      const fenceRegex = /```(json|chart)\n([\s\S]*?)```/gi;
      let match;
      while ((match = fenceRegex.exec(text)) !== null) {
        try {
          const spec = JSON.parse(match[2]);
          if (spec && spec.type && (spec.data || spec.datasets)) {
            const id = `chart-${msgIdx}-${match.index}`;
            list.push({
              id,
              type: "chart",
              data: spec,
              sourceIndex: msgIdx,
              defaultLabel:
                spec.title ||
                spec?.options?.plugins?.title?.text ||
                `Chart #${list.length + 1}`,
            });
          }
        } catch {
          /* ignore */
        }
      }
      // Explicit table fence
      const tableFence = /```table\n([\s\S]*?)```/gi;
      while ((match = tableFence.exec(text)) !== null) {
        try {
          const tbl = JSON.parse(match[1]);
          if (Array.isArray(tbl.columns) && Array.isArray(tbl.rows)) {
            const id = `table-${msgIdx}-${match.index}`;
            list.push({
              id,
              type: "table",
              data: tbl,
              sourceIndex: msgIdx,
              defaultLabel: `Table #${list.length + 1}`,
            });
          }
        } catch {
          /* ignore */
        }
      }
      // Markdown table heuristic
      if (/\n?\|[^\n]*\|/.test(text)) {
        const mdTableRegex = /(\|.+\|\n\|[-:| ]+\|[\s\S]*?)(\n\n|$)/g;
        while ((match = mdTableRegex.exec(text)) !== null) {
          const block = match[1];
          const lines = block.trim().split("\n").filter(Boolean);
          if (lines.length < 2) continue;
          const header = lines[0];
          const bodyLines = lines.slice(2);
          const toCells = (line) =>
            line
              .split("|")
              .slice(1, -1)
              .map((c) => c.trim());
          const columns = toCells(header);
          const rows = bodyLines.map((l) => toCells(l));
          if (columns.length) {
            const id = `table-${msgIdx}-${match.index}-${list.length}`;
            list.push({
              id,
              type: "table",
              data: { columns, rows },
              sourceIndex: msgIdx,
              defaultLabel: `Table ${columns[0]}…`,
            });
          }
        }
      }
    });
    return list;
  }, [messages]);

  // Load persisted artifact UI state
  useEffect(() => {
    if (!chatId) return;
    try {
      const raw = localStorage.getItem(`artifact_state_${chatId}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        setSelectedId(parsed.selectedId);
        setPins(parsed.pins || {});
        setCustomNames(parsed.customNames || {});
      }
    } catch {
      /* ignore */
    }
  }, [chatId]);

  const persist = useCallback(
    (next = {}) => {
      if (!chatId) return;
      try {
        const payload = {
          selectedId: next.selectedId ?? selectedId,
          pins: next.pins ?? pins,
          customNames: next.customNames ?? customNames,
        };
        localStorage.setItem(
          `artifact_state_${chatId}`,
          JSON.stringify(payload),
        );
      } catch {
        /* ignore */
      }
    },
    [chatId, selectedId, pins, customNames],
  );

  // Auto-select most recent artifact
  useEffect(() => {
    if (!artifacts.length) {
      setSelectedId(undefined);
      return;
    }
    setSelectedId((prev) => {
      if (prev && artifacts.some((a) => a.id === prev && !deletedIds.has(a.id)))
        return prev;
      const candidates = artifacts.filter((a) => !deletedIds.has(a.id));
      return candidates.length
        ? candidates[candidates.length - 1].id
        : undefined;
    });
  }, [artifacts, deletedIds]);

  const togglePin = (id) =>
    setPins((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      persist({ pins: next });
      return next;
    });
  const renameArtifactInline = (id, newName) =>
    setCustomNames((prev) => {
      const next = { ...prev, [id]: newName };
      persist({ customNames: next });
      return next;
    });
  const deleteArtifact = (id) =>
    setDeletedIds((prev) => new Set([...prev, id]));

  const allArtifacts = useMemo(
    () =>
      artifacts
        .filter((a) => !deletedIds.has(a.id))
        .map((a) => ({
          ...a,
          pinned: !!pins[a.id],
          label: customNames[a.id] || a.defaultLabel || a.id,
        }))
        .sort((a, b) => b.pinned - a.pinned),
    [artifacts, pins, customNames, deletedIds],
  );

  const selected = allArtifacts.find((a) => a.id === selectedId);

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
      let csv = "label," + datasets.map((ds) => ds.label).join(",") + "\n";
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

  if (!allArtifacts.length) return null;

  return (
    <>
      <div className="mt-6 bg-slate-800/40 border border-slate-700 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">
              Artifacts ({allArtifacts.length})
            </div>
            {selected && (
              <button
                title="Open Canvas"
                onClick={() => setShowOverlay(true)}
                className="p-1 rounded bg-slate-700/70 hover:bg-slate-600 text-[10px] border border-slate-600/60 shadow-inner"
              >
                ⤢
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCanvas((s) => !s)}
              className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
            >
              {showCanvas ? "Hide" : "Show"}
            </button>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-52 overflow-y-auto pr-1 custom-scrollbar">
          {allArtifacts.map((a) => (
            <div
              key={a.id}
              onClick={() => {
                setSelectedId(a.id);
              }}
              className={`cursor-pointer transition ${
                a.id === selectedId
                  ? "ring-1 ring-blue-400"
                  : "hover:ring-1 hover:ring-slate-600"
              }`}
            >
              <ArtifactList
                artifacts={[a]}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onTogglePin={togglePin}
                onRename={renameArtifactInline}
                onDelete={deleteArtifact}
              />
            </div>
          ))}
        </div>
        {showCanvas && selected && (
          <div className="mt-4 border-t border-slate-700 pt-3">
            <ArtifactDetail
              artifact={selected}
              exportPNG={exportPNG}
              exportCSV={exportCSV}
              exportJSON={exportJSON}
            />
          </div>
        )}
      </div>

      {showOverlay && selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/70 backdrop-blur-sm animate-fadeIn"
          onKeyDown={(e) => {
            if (e.key === "Escape") setShowOverlay(false);
          }}
          tabIndex={-1}
        >
          <div
            className="absolute inset-0"
            onClick={() => setShowOverlay(false)}
          />
          <div className="relative z-10 w-full max-w-6xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-600 bg-slate-900/95 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-200 truncate pr-4">
                {selected.label}
              </h3>
              <div className="flex gap-2">
                {selected.type === "chart" && (
                  <button
                    onClick={() => exportPNG(selected)}
                    className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
                  >
                    PNG
                  </button>
                )}
                <button
                  onClick={() => exportCSV(selected)}
                  className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
                >
                  CSV
                </button>
                <button
                  onClick={() => exportJSON(selected)}
                  className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
                >
                  JSON
                </button>
                <button
                  onClick={() => setShowOverlay(false)}
                  className="px-2 py-1 text-[11px] rounded bg-red-600/80 hover:bg-red-600"
                >
                  Close
                </button>
              </div>
            </div>
            <ArtifactDetail
              artifact={selected}
              exportPNG={exportPNG}
              exportCSV={exportCSV}
              exportJSON={exportJSON}
            />
          </div>
        </div>
      )}
    </>
  );
}
