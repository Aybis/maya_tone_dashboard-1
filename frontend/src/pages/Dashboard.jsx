import React, { useMemo } from 'react';
import { Bar, Doughnut, Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { useDashboard } from '../context/DashboardContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
);

function SummaryCard({ title, value, subtitle = null, className = '' }) {
  return (
    <div
      className={`bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4 shadow flex flex-col justify-between ${className}`}
    >
      <div className="text-slate-400 text-sm font-medium">{title}</div>
      <div className="text-2xl font-bold text-slate-50 mt-1">
        {value !== null && value !== undefined ? value : '–'}
      </div>
      {subtitle && (
        <div className="text-xs text-slate-500 mt-1">{subtitle}</div>
      )}
    </div>
  );
}

function PersonalStatsSection({ title, stats, icon = null }) {
  return (
    <div className="bg-[#0f0f23]/90 border border-blue-500/20 rounded-lg p-5 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        {icon && <div className="text-blue-400">{icon}</div>}
        <h3 className="text-lg font-semibold text-slate-200">{title}</h3>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 flex-1">
        {stats.map((stat, index) => (
          <SummaryCard
            key={index}
            title={stat.title}
            value={stat.value}
            subtitle={stat.subtitle}
            className="bg-[#0f0f23]/60 border-blue-500/5 h-full"
          />
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const {
    dashboard: data,
    loadingDashboard: loading,
    dashboardError: error,
    refreshDashboard,
    lastFetched,
    isStale,
  } = useDashboard();

  const statusChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.status || {});
    const values = Object.values(data?.distributions?.status || {});
    return {
      labels,
      datasets: [
        {
          label: 'Status',
          data: values,
          backgroundColor: labels.map((l) => '#60a5fa'),
        },
      ],
    };
  }, [data]);

  const priorityChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.priority || {});
    const values = Object.values(data?.distributions?.priority || {});
    const colors = ['#f87171', '#fbbf24', '#4ade80', '#a78bfa', '#60a5fa'];
    return {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: values.map((_, i) => colors[i % colors.length]),
        },
      ],
    };
  }, [data]);

  const assigneeChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.assignees || {});
    const values = Object.values(data?.distributions?.assignees || {});
    return {
      labels: labels.map((l) => (l.length > 20 ? l.slice(0, 17) + '…' : l)),
      datasets: [
        {
          label: 'Assigned Tickets',
          data: values,
          backgroundColor: '#4ade80',
          borderColor: '#22c55e',
          borderWidth: 1,
        },
      ],
    };
  }, [data]);

  const typeChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.types || {});
    const values = Object.values(data?.distributions?.types || {});
    const colors = [
      '#a78bfa',
      '#34d399',
      '#fbbf24',
      '#f87171',
      '#60a5fa',
      '#c084fc',
      '#fde047',
      '#fb7185',
      '#4ade80',
      '#94a3b8',
    ];
    return {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: values.map((_, i) => colors[i % colors.length]),
          borderWidth: 0,
        },
      ],
    };
  }, [data]);

  // Personal stats configuration
  const todayStats = useMemo(() => {
    const personal = data?.personal?.today || {};
    return [
      { title: 'Due Today', value: personal.due_today },
      { title: 'Overdue', value: personal.overdue },
      { title: 'Reviews', value: personal.reviews_waiting },
    ];
  }, [data]);

  const riskStats = useMemo(() => {
    const personal = data?.personal?.risks || {};
    return [
      {
        title: 'Pred. Slips',
        value: personal.predicted_slips,
      },
      {
        title: 'Blocked',
        value: personal.blocked_count,
      },
      {
        title: 'Aging p90 (d)',
        value: personal.aging_p90_days,
      },
    ];
  }, [data]);

  const capacityStats = useMemo(() => {
    const personal = data?.personal?.capacity || {};
    return [
      { title: 'Hours Today', value: personal.hours_logged_today },
      { title: 'Target', value: personal.target_hours_today },
      { title: 'Suggestions', value: personal.suggested_logs },
    ];
  }, [data]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <header className="mb-8 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-50 mb-1">Summary</h1>
          <p className="text-slate-400">Overview of your Jira activity</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={refreshDashboard}
            className="px-3 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          {lastFetched && (
            <span className="text-[11px] text-slate-500">
              Updated {new Date(lastFetched).toLocaleTimeString()}
              {isStale && <em className="text-amber-400 ml-1">(stale)</em>}
            </span>
          )}
        </div>
      </header>

      {loading && !data && (
        <div className="text-center py-12 text-slate-400">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          Loading dashboard…
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded text-center my-4">
          Error: {error}
        </div>
      )}

      {data && (
        <div className="space-y-8">
          {/* Personal Stats Section */}
          <section className="space-y-6">
            <h2 className="text-xl font-semibold text-slate-200">
              Personal Overview
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <PersonalStatsSection
                title="Today"
                stats={todayStats}
                icon={
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"
                      clipRule="evenodd"
                    />
                  </svg>
                }
              />

              <PersonalStatsSection
                title="Risks"
                stats={riskStats}
                icon={
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                }
              />

              <PersonalStatsSection
                title="Capacity"
                stats={capacityStats}
                icon={
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                      clipRule="evenodd"
                    />
                  </svg>
                }
              />
            </div>
          </section>

          {/* Original Summary Cards */}
          <section>
            <h2 className="text-xl font-semibold text-slate-200 mb-4">
              General Overview
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <SummaryCard
                title="My open tickets"
                value={data.summary?.my_open_tickets ?? 0}
              />
              <SummaryCard
                title="My total tickets"
                value={data.summary?.my_total_tickets ?? 0}
              />
              <SummaryCard
                title="Reported by me"
                value={data.summary?.reported_by_me ?? 0}
              />
              <SummaryCard
                title="Recent activity"
                value={data.summary?.recent_activity ?? 0}
              />
            </div>
          </section>

          {/* Charts Section */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">
                Status Distribution
              </h3>
              <div className="h-56 md:h-64">
                <Bar
                  data={statusChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: { display: true, labels: { color: '#94a3b8' } },
                    },
                    scales: {
                      x: {
                        ticks: { color: '#94a3b8' },
                        grid: { display: false },
                      },
                      y: {
                        beginAtZero: true,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(59,130,246,0.1)' },
                      },
                    },
                  }}
                />
              </div>
            </div>
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">Priority</h3>
              <div className="h-56 md:h-64">
                <Doughnut
                  data={priorityChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                      legend: {
                        position: 'bottom',
                        labels: {
                          color: '#94a3b8',
                          boxWidth: 14,
                          font: { size: 12 },
                        },
                      },
                    },
                  }}
                />
              </div>
            </div>
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">
                Top Assignees
              </h3>
              <div className="h-56 md:h-64">
                <Bar
                  data={assigneeChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: {
                      x: {
                        beginAtZero: true,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(59,130,246,0.1)' },
                      },
                      y: {
                        ticks: { color: '#94a3b8' },
                        grid: { display: false },
                      },
                    },
                  }}
                />
              </div>
            </div>
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">Issue Types</h3>
              <div className="h-56 md:h-64">
                <Pie
                  data={typeChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8' },
                      },
                    },
                  }}
                />
              </div>
            </div>
          </section>

          {/* Recent Tickets Section */}
          <section className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
            <h3 className="text-slate-200 font-semibold mb-3">
              Recent Tickets
            </h3>
            {data.recent_tickets?.length ? (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.recent_tickets.map((t) => (
                  <div
                    key={t.key}
                    className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <a
                        href={t.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-400 font-semibold hover:text-blue-300 transition-colors"
                      >
                        {t.key}
                      </a>
                      <span className="text-xs px-2 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300">
                        {t.status}
                      </span>
                    </div>
                    <div className="text-slate-100 font-medium mb-2 text-sm leading-relaxed">
                      {t.summary}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span
                        className={`px-2 py-1 rounded-full border ${
                          t.priority === 'High' || t.priority === 'Highest'
                            ? 'bg-red-500/10 text-red-300 border-red-500/30'
                            : t.priority === 'Medium'
                            ? 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30'
                            : 'bg-green-500/10 text-green-300 border-green-500/30'
                        }`}
                      >
                        {t.priority}
                      </span>
                      <span className="text-slate-400">
                        Updated: {t.updated}
                      </span>
                      <span className="text-slate-400">
                        Assignee: {t.assignee}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-400 text-center py-8">
                No recent tickets found.
              </div>
            )}
          </section>

          {/* Additional metrics if needed */}
          {data.trends && (
            <section className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">
                Monthly Trends
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SummaryCard
                  title="Created This Month"
                  value={data.trends.created_this_month}
                />
                <SummaryCard
                  title="Created Last Month"
                  value={data.trends.created_last_month}
                />
                <SummaryCard
                  title="Growth Rate"
                  value={`${data.trends.growth_rate}%`}
                  className={
                    data.trends.growth_rate > 0
                      ? 'border-green-500/20'
                      : data.trends.growth_rate < 0
                      ? 'border-red-500/20'
                      : ''
                  }
                />
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
