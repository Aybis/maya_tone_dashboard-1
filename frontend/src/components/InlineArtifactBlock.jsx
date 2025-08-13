import React, { useEffect, useRef, useState, useMemo } from "react";
import ChartRenderer from "./chart-canvas/ChartRenderer";
import { marked } from "marked";

export default function InlineArtifactBlock({
  artifact,
  onExpand,
  forceRender = false, // force immediate render (e.g., in side panel)
}) {
  const { type, data, label } = artifact;
  const containerRef = useRef(null);
  const [visible, setVisible] = useState(forceRender);

  // When forced (panel) ensure visibility
  useEffect(() => {
    if (forceRender) setVisible(true);
  }, [forceRender]);

  // Intersection Observer for lazy mount
  useEffect(() => {
    if (visible || forceRender) return;
    const el = containerRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setVisible(true);
            obs.disconnect();
          }
        });
      },
      { rootMargin: "200px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [visible, forceRender]);

  const renderMD = (s) => {
    try {
      return marked.parseInline(s || "");
    } catch {
      return s;
    }
  };

  // Normalize chart spec if model emitted a minimal form { labels, datasets }
  const normalizedChartSpec = useMemo(() => {
    if (type !== "chart") return null;
    if (!data || typeof data !== "object") return null;
    if (data.type && data.data) return data; // already full spec
    // minimal form
    if (!data.data && data.labels && data.datasets) {
      return {
        type: data.type || "bar",
        data: { labels: data.labels, datasets: data.datasets },
        options: data.options || {
          responsive: true,
          plugins: { legend: { position: "bottom" } },
        },
      };
    }
    return data;
  }, [type, data]);

  return (
    <div
      ref={containerRef}
      className="relative group my-4 border border-slate-600/50 rounded-lg bg-slate-800/60 p-3 overflow-hidden min-h-[3.5rem]"
    >
      <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition">
        <button
          onClick={onExpand}
          title="Expand"
          className="px-2 py-1 text-[10px] rounded bg-slate-700 hover:bg-slate-600 shadow"
        >
          ↗
        </button>
      </div>
      <div
        className="text-[11px] font-medium mb-2 text-slate-300 flex items-center gap-2"
        title={label}
        dangerouslySetInnerHTML={{ __html: renderMD(label) }}
      />
      {visible && type === "chart" && (
        <div className="bg-slate-900/40 rounded p-2">
          {normalizedChartSpec &&
          normalizedChartSpec.type &&
          normalizedChartSpec.data ? (
            <ChartRenderer spec={normalizedChartSpec} />
          ) : (
            <div className="text-[10px] text-amber-300">
              Invalid chart spec (expected keys: <code>type</code>,{" "}
              <code>data</code>)
            </div>
          )}
        </div>
      )}
      {visible && type === "table" && (
        <div className="overflow-x-auto max-h-80 border border-slate-600/60 rounded bg-slate-900/30">
          <table className="w-full text-[11px]">
            <thead className="bg-slate-700/60">
              <tr>
                {data.columns.map((col) => (
                  <th
                    key={col}
                    className="px-2 py-1 text-left font-medium whitespace-nowrap"
                    dangerouslySetInnerHTML={{ __html: renderMD(col) }}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr
                  key={i}
                  className="odd:bg-slate-800/30 even:bg-slate-800/10"
                >
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className="px-2 py-1 whitespace-nowrap"
                      dangerouslySetInnerHTML={{ __html: renderMD(cell) }}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!visible && (
        <div className="h-28 flex items-center justify-center text-[10px] text-slate-500 animate-pulse">
          Loading artifact…
        </div>
      )}
    </div>
  );
}
