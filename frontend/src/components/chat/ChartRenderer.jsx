import React from 'react';
import { Line, Bar, Pie, Doughnut } from 'react-chartjs-2';

export default function ChartRenderer({ spec }) {
  if (!spec) return null;
  // Accept both new format { type, data, options } and legacy { type, labels, datasets }
  const { type } = spec;
  let chartData = spec.data;
  if (!chartData && spec.labels && spec.datasets) {
    chartData = { labels: spec.labels, datasets: spec.datasets };
  }
  if (!chartData) {
    return (
      <div className="text-base text-amber-500">Invalid chart spec format.</div>
    );
  }
  // Ensure datasets array has basic styling defaults to avoid Chart.js errors
  chartData = {
    ...chartData,
    datasets: (chartData.datasets || []).map((ds, i) => ({
      borderWidth: 1,
      ...ds,
      backgroundColor:
        ds.backgroundColor ||
        ['#3b82f6', '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][
          i % 6
        ],
    })),
  };
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' },
      title: spec.title ? { display: true, text: spec.title } : undefined,
    },
    ...(spec.options || {}),
  };
  const common = { data: chartData, options: baseOptions };
  const cls =
    'w-full h-72 bg-zinc-900/40 border border-zinc-700/60 rounded-lg p-4';
  const t = (type || '').toLowerCase();
  switch (t) {
    case 'line':
      return (
        <div className={cls}>
          <Line {...common} />
        </div>
      );
    case 'bar':
    case 'bar-vertical':
      return (
        <div className={cls}>
          <Bar {...common} />
        </div>
      );
    case 'bar-horizontal':
      return (
        <div className={cls}>
          <Bar {...common} options={{ ...baseOptions, indexAxis: 'y' }} />
        </div>
      );
    case 'pie':
      return (
        <div className={cls}>
          <Pie {...common} />
        </div>
      );
    case 'doughnut':
      return (
        <div className={cls}>
          <Doughnut {...common} />
        </div>
      );
    default:
      return (
        <div className="text-base text-red-500">
          Unsupported chart type: {type}
        </div>
      );
  }
}
