import React, { useEffect, useMemo, useState, useCallback } from 'react';
import ArtifactList from './chart-canvas/ArtifactList';
import ArtifactDetail from './chart-canvas/ArtifactDetail';

// Unified & refactored visualization pane with inline rename, delete, JSON export
export default function ChartCanvasPane({ messages, chatId }) {
  const [selectedId, setSelectedId] = useState();
  const [pins, setPins] = useState({});
  const [customNames, setCustomNames] = useState({});
  const [deletedIds, setDeletedIds] = useState(new Set()); // local-only deletes

  // Parse messages for artifacts (charts & tables) supporting multiple syntaxes
  const artifacts = useMemo(() => {
    const list = [];
    messages.forEach((m, msgIdx) => {
      if (m.sender !== 'assistant' || !m.content) return;
      const text = m.content;

      // Code-fence based chart specs: ```json { type, data } ``` or legacy ```chart
      const fenceRegex = /```(json|chart)\n([\s\S]*?)```/gi;
      let match;
      while ((match = fenceRegex.exec(text)) !== null) {
        const body = match[2];
        try {
          const spec = JSON.parse(body);
          if (spec && (spec.type && (spec.data || spec.datasets))) {
            const id = `chart-${msgIdx}-${match.index}`;
            list.push({ id, type: 'chart', data: spec, sourceIndex: msgIdx, defaultLabel: spec.title || spec?.options?.plugins?.title?.text || `Chart #${list.length+1}` });
          }
        } catch { /* ignore */ }
      }

      // Table via ```table fence containing JSON { columns, rows }
      const tableFence = /```table\n([\s\S]*?)```/gi;
      while ((match = tableFence.exec(text)) !== null) {
        try {
          const tbl = JSON.parse(match[1]);
          if (Array.isArray(tbl.columns) && Array.isArray(tbl.rows)) {
            const id = `table-${msgIdx}-${match.index}`;
            list.push({ id, type: 'table', data: tbl, sourceIndex: msgIdx, defaultLabel: `Table #${list.length+1}` });
          }
        } catch { /* ignore */ }
      }

      // Markdown table fallback (simple heuristic)
      if (/\n?\|[^\n]*\|/.test(text)) {
        const mdTableRegex = /(\|.+\|\n\|[-:| ]+\|[\s\S]*?)(\n\n|$)/g;
        while ((match = mdTableRegex.exec(text)) !== null) {
          const block = match[1];
          const lines = block.trim().split('\n').filter(Boolean);
            if (lines.length < 2) continue;
            const header = lines[0];
            const bodyLines = lines.slice(2);
            const toCells = line => line.split('|').slice(1,-1).map(c => c.trim());
            const columns = toCells(header);
            const rows = bodyLines.map(l => toCells(l));
            if (columns.length) {
              const id = `table-${msgIdx}-${match.index}-${list.length}`;
              list.push({ id, type: 'table', data: { columns, rows }, sourceIndex: msgIdx, defaultLabel: `Table ${columns[0]}…` });
            }
        }
      }
    });
    return list;
  }, [messages]);

  // Load persisted state (selection, pins, names)
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
    } catch {/* ignore */}
  }, [chatId]);

  const persist = useCallback((next = {}) => {
    if (!chatId) return;
    try {
      const payload = {
        selectedId: next.selectedId ?? selectedId,
        pins: next.pins ?? pins,
        customNames: next.customNames ?? customNames
      };
      localStorage.setItem(`artifact_state_${chatId}`, JSON.stringify(payload));
    } catch {/* ignore */}
  }, [chatId, selectedId, pins, customNames]);

  // Auto-select last artifact (not deleted) if none selected or previous removed
  useEffect(() => {
    if (!artifacts.length) { setSelectedId(undefined); return; }
    setSelectedId(prev => {
      if (prev && artifacts.some(a => a.id === prev && !deletedIds.has(a.id))) return prev;
      const candidates = artifacts.filter(a => !deletedIds.has(a.id));
      return candidates.length ? candidates[candidates.length - 1].id : undefined;
    });
  }, [artifacts, deletedIds]);

  const togglePin = (id) => setPins(prev => { const next = { ...prev, [id]: !prev[id] }; persist({ pins: next }); return next; });
  const renameArtifactInline = (id, newName) => setCustomNames(prev => { const next = { ...prev, [id]: newName }; persist({ customNames: next }); return next; });
  const deleteArtifact = (id) => setDeletedIds(prev => new Set([...prev, id]));

  const allArtifacts = useMemo(() => {
    return artifacts
      .filter(a => !deletedIds.has(a.id))
      .map(a => ({
        ...a,
        pinned: !!pins[a.id],
        label: customNames[a.id] || a.defaultLabel || a.id
      }))
      .sort((a,b) => (b.pinned - a.pinned));
  }, [artifacts, pins, customNames, deletedIds]);

  const selected = allArtifacts.find(a => a.id === selectedId);

  const exportPNG = (artifact) => {
    if (!artifact || artifact.type !== 'chart') return;
    const canvas = document.querySelector('canvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `${artifact.label || 'chart'}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };
  const exportCSV = (artifact) => {
    if (!artifact) return;
    if (artifact.type === 'chart') {
      const spec = artifact.data || {};
      const data = spec.data || { labels: spec.labels || [], datasets: spec.datasets || [] };
      const labels = data.labels || [];
      const datasets = data.datasets || [];
      let csv = 'label,' + datasets.map(ds=>ds.label).join(',') + '\n';
      labels.forEach((lbl,i) => {
        const row = [lbl];
        datasets.forEach(ds => row.push(ds.data ? ds.data[i] : ''));
        csv += row.join(',') + '\n';
      });
      const blob = new Blob([csv], {type:'text/csv'});
      const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${artifact.label || 'chart'}.csv`; link.click();
    } else if (artifact.type === 'table') {
      const tbl = artifact.data;
      let csv = tbl.columns.join(',') + '\n';
      tbl.rows.forEach(r => { csv += r.join(',') + '\n'; });
      const blob = new Blob([csv], {type:'text/csv'});
      const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${artifact.label || 'table'}.csv`; link.click();
    }
  };
  const exportJSON = (artifact) => {
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.data, null, 2)], {type:'application/json'});
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${artifact.label || artifact.id}.json`; link.click();
  };

  const hasArtifacts = allArtifacts.length > 0;

  return (
  <div className="flex h-full bg-zinc-50 dark:bg-[#0f0f23]/40 border-l border-blue-200/40 dark:border-blue-500/10 p-3 text-xs">
      <div className="w-60 pr-3 border-r border-slate-700/60">
        <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Artifacts</div>
        <ArtifactList
          artifacts={allArtifacts}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onTogglePin={togglePin}
          onRename={renameArtifactInline}
          onDelete={deleteArtifact}
        />
      </div>
      <div className="flex-1 pl-4 overflow-y-auto">
        {!hasArtifacts && <div className="text-slate-500 italic h-full flex items-center justify-center">No visualization yet.</div>}
        {hasArtifacts && (
          <ArtifactDetail
            artifact={selected}
            exportPNG={exportPNG}
            exportCSV={exportCSV}
            exportJSON={exportJSON}
          />
        )}
      </div>
    </div>
  );
}
