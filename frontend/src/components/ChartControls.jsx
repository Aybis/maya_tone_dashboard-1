import React, { useState, useEffect, useMemo } from "react";

function useDebouncedEffect(fn, deps, delay) {
  useEffect(() => {
    const t = setTimeout(fn, delay);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, delay]);
}

export default function ChartControls({
  artifact,
  onChange,
  autoInsightDefault = true,
}) {
  const initialLabels =
    artifact?.data?.data?.labels || artifact?.data?.labels || [];
  const [size, setSize] = useState("md");
  const [groupBy, setGroupBy] = useState("status");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [statuses] = useState(initialLabels);
  const [selectedStatuses, setSelectedStatuses] = useState(initialLabels);
  const [assignee, setAssignee] = useState("");
  const [project, setProject] = useState("");
  const [autoInsight, setAutoInsight] = useState(autoInsightDefault);

  const controls = useMemo(
    () => ({
      size,
      groupBy,
      dateFrom: dateFrom || null,
      dateTo: dateTo || null,
      statuses: selectedStatuses,
      assignee: assignee || null,
      project: project || null,
      autoInsight,
    }),
    [
      size,
      groupBy,
      dateFrom,
      dateTo,
      selectedStatuses,
      assignee,
      project,
      autoInsight,
    ],
  );

  useDebouncedEffect(
    () => {
      onChange && onChange(controls);
    },
    [controls],
    600,
  );

  useEffect(() => {
    const h = size === "sm" ? 220 : size === "md" ? 320 : 460;
    document.documentElement.style.setProperty("--chart-height", h + "px");
  }, [size]);

  const toggleStatus = (s) => {
    setSelectedStatuses((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
  };

  return (
    <div className="mb-4 space-y-4 text-[11px]">
      <div className="flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            Size
          </label>
          <div className="flex gap-1">
            {["sm", "md", "lg"].map((s) => (
              <button
                key={s}
                onClick={() => setSize(s)}
                className={`px-2 py-1 rounded border text-[10px] ${
                  size === s
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-slate-800 border-slate-600 hover:border-slate-400"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            Group by
          </label>
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1"
          >
            <option value="status">Status</option>
            <option value="priority">Priority</option>
            <option value="assignee">Assignee</option>
            <option value="project">Project</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            Assignee
          </label>
          <input
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            placeholder="any"
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="uppercase tracking-wide text-[10px] text-slate-400">
            Project
          </label>
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            placeholder="any"
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1"
          />
        </div>
        <div className="flex items-center gap-2 mt-4">
          <label className="text-[10px] text-slate-400">Auto Insight</label>
          <input
            type="checkbox"
            checked={autoInsight}
            onChange={(e) => setAutoInsight(e.target.checked)}
          />
        </div>
      </div>
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-400">
          Statuses
        </div>
        <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => toggleStatus(s)}
              className={`px-2 py-1 rounded text-[10px] border ${
                selectedStatuses.includes(s)
                  ? "bg-blue-600 text-white border-blue-500"
                  : "bg-slate-800 border-slate-600 hover:border-slate-400 text-slate-300"
              }`}
            >
              {s || "∅"}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
