import { useState, useMemo, useEffect } from "react";

export function useArtifacts(messages, chartOverrides = {}) {
  const [sideArtifact, setSideArtifact] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(() => {
    const stored =
      typeof window !== "undefined"
        ? localStorage.getItem("artifact_panel_width")
        : null;
    return stored ? parseInt(stored, 10) : 60;
  });
  const [autoOpened, setAutoOpened] = useState(false);

  const parsedMessages = useMemo(() => {
    const all = [];
    const msgResults = messages.map((m, idx) => {
      if (m.sender !== "assistant" || !m.content)
        return { ...m, artifacts: [], cleaned: m.content };
      const text = m.content;
      const artifacts = [];
      let cleaned = text;
      const tryParse = (str) => {
        try {
          return JSON.parse(str);
        } catch {
          return null;
        }
      };
      cleaned = cleaned.replace(
        /```(json|chart)\n([\s\S]*?)```/gi,
        (full, lang, body, offset) => {
          const spec = tryParse(body);
          if (
            spec &&
            (spec.type || spec.labels) &&
            (spec.data || spec.datasets || spec.labels)
          ) {
            const id = `chart-${idx}-${offset}-${artifacts.length}`;
            // Normalize minimal spec (labels + datasets) into Chart.js full config if needed
            let normalized = spec;
            if (!spec.type && spec.labels && spec.datasets) {
              normalized = {
                type: "bar",
                data: { labels: spec.labels, datasets: spec.datasets },
                options: spec.options || {
                  responsive: true,
                  plugins: { legend: { position: "bottom" } },
                },
              };
            }
            const artifact = {
              id,
              type: "chart",
              data: chartOverrides[id] || normalized,
              _orig: normalized, // keep original for local transforms
              label:
                normalized.title ||
                normalized?.options?.plugins?.title?.text ||
                "Chart",
            };
            artifacts.push(artifact);
            return "";
          }
          return full;
        },
      );
      cleaned = cleaned.replace(
        /```table\n([\s\S]*?)```/gi,
        (full, body, offset) => {
          const tbl = tryParse(body);
          if (tbl && Array.isArray(tbl.columns) && Array.isArray(tbl.rows)) {
            const id = `table-${idx}-${offset}-${artifacts.length}`;
            artifacts.push({ id, type: "table", data: tbl, label: "Table" });
            return "";
          }
          return full;
        },
      );
      const mdTableRegex = /(\|.+\|\n\|[-:| ]+\|[\s\S]*?)(\n\n|$)/g;
      let match;
      let guard = 0;
      while ((match = mdTableRegex.exec(text)) !== null && guard < 25) {
        guard++;
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
          const id = `table-${idx}-md-${match.index}-${artifacts.length}`;
          artifacts.push({
            id,
            type: "table",
            data: { columns, rows },
            label: "Table",
          });
        }
      }
      artifacts.forEach((a) => all.push(a));
      return { ...m, artifacts, cleaned };
    });
    if (!autoOpened && all.length) {
      setSideArtifact((prev) => prev || all[0]);
      setPanelOpen(true);
      setAutoOpened(true);
    }
    return msgResults;
  }, [messages, autoOpened, chartOverrides]);

  useEffect(() => {
    if (typeof window !== "undefined")
      localStorage.setItem("artifact_panel_width", String(panelWidth));
  }, [panelWidth]);

  return {
    parsedMessages,
    sideArtifact,
    setSideArtifact,
    panelOpen,
    setPanelOpen,
    panelWidth,
    setPanelWidth,
  };
}
