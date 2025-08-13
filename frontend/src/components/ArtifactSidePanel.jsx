import React, { useRef } from "react";
import { marked } from "marked";
import InlineArtifactBlock from "./InlineArtifactBlock";
import ChartControls from "./ChartControls";

export default function ArtifactSidePanel({
  panelOpen,
  sideArtifact,
  panelWidth,
  setSideArtifact,
  setPanelOpen,
  parsedMessages,
  exportPNG,
  exportCSV,
  exportJSON,
  setDragging,
  panelRef,
  dragRef,
  onChartControlsChange,
  chartAutoInsightDefault = true,
}) {
  if (!sideArtifact) return null;
  return (
    <div
      ref={panelRef}
      className={`h-full flex flex-col bg-[#0b1120]/95 backdrop-blur-md border-l border-slate-700 shadow-2xl transition-all duration-300 ease-out absolute top-0 right-0 ${
        panelOpen && sideArtifact ? "translate-x-0" : "translate-x-full"
      } ${panelOpen ? "" : "pointer-events-none"}`}
      style={{
        width: panelOpen ? `${panelWidth}%` : `${panelWidth}%`,
        minWidth: "320px",
      }}
    >
      <div
        ref={dragRef}
        onMouseDown={(e) => {
          setDragging(true);
          e.preventDefault();
        }}
        className="absolute left-0 top-0 h-full w-1 cursor-col-resize bg-slate-500/10 hover:bg-slate-500/30 transition"
      />
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/70">
        <div className="flex items-center gap-2">
          <h3
            className="text-sm font-semibold text-slate-200 truncate max-w-[340px]"
            title={sideArtifact.label}
            dangerouslySetInnerHTML={{
              __html: (() => {
                try {
                  return marked.parseInline(sideArtifact.label || "");
                } catch {
                  return sideArtifact.label;
                }
              })(),
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const flat = parsedMessages.flatMap((m) => m.artifacts || []);
              const idx = flat.findIndex((a) => a.id === sideArtifact.id);
              if (idx > 0) setSideArtifact(flat[idx - 1]);
            }}
            className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
          >
            Prev
          </button>
          <button
            onClick={() => {
              const flat = parsedMessages.flatMap((m) => m.artifacts || []);
              const idx = flat.findIndex((a) => a.id === sideArtifact.id);
              if (idx >= 0 && idx < flat.length - 1)
                setSideArtifact(flat[idx + 1]);
            }}
            className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
          >
            Next
          </button>
          {sideArtifact.type === "chart" && (
            <button
              onClick={() => exportPNG(sideArtifact)}
              className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
            >
              PNG
            </button>
          )}
          <button
            onClick={() => exportCSV(sideArtifact)}
            className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
          >
            CSV
          </button>
          <button
            onClick={() => exportJSON(sideArtifact)}
            className="px-2 py-1 text-[11px] rounded bg-slate-700 hover:bg-slate-600"
          >
            JSON
          </button>
          <button
            onClick={() => setPanelOpen(false)}
            className="px-2 py-1 text-[11px] rounded bg-red-600/80 hover:bg-red-600"
          >
            Close
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {sideArtifact.type === "chart" && (
          <ChartControls
            artifact={sideArtifact}
            onChange={onChartControlsChange}
            autoInsightDefault={chartAutoInsightDefault}
          />
        )}
        <InlineArtifactBlock
          artifact={sideArtifact}
          onExpand={() => {}}
          forceRender
        />
      </div>
    </div>
  );
}
