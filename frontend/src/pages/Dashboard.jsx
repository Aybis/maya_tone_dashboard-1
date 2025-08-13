import React, { useMemo } from 'react'
import { Bar, Doughnut, Pie } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend
} from 'chart.js'
import { useDashboard } from '../context/DashboardContext'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend)

function SummaryCard({ title, value }) {
  return (
    <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-5 shadow">
      <div className="text-slate-400 text-sm">{title}</div>
      <div className="text-2xl font-bold text-slate-50 mt-1">{value}</div>
    </div>
  )
}

export default function Dashboard() {
  const { dashboard: data, loadingDashboard: loading, dashboardError: error, refreshDashboard, lastFetched, isStale } = useDashboard();

  const statusChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.status || {})
    const values = Object.values(data?.distributions?.status || {})
    return {
      labels,
      datasets: [{
        label: 'Status',
        data: values,
        backgroundColor: labels.map(l => '#60a5fa'),
      }]
    }
  }, [data])

  const priorityChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.priority || {})
    const values = Object.values(data?.distributions?.priority || {})
    const colors = ['#f87171', '#fbbf24', '#4ade80', '#a78bfa', '#60a5fa']
    return {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => colors[i % colors.length])
      }]
    }
  }, [data])

  const assigneeChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.assignees || {})
    const values = Object.values(data?.distributions?.assignees || {})
    return {
      labels: labels.map(l => (l.length > 20 ? l.slice(0, 17) + '…' : l)),
      datasets: [{
        label: 'Assigned Tickets',
        data: values,
        backgroundColor: '#4ade80',
        borderColor: '#22c55e',
        borderWidth: 1,
      }]
    }
  }, [data])

  const typeChart = useMemo(() => {
    const labels = Object.keys(data?.distributions?.types || {})
    const values = Object.values(data?.distributions?.types || {})
    const colors = ['#a78bfa', '#34d399', '#fbbf24', '#f87171', '#60a5fa', '#c084fc', '#fde047', '#fb7185', '#4ade80', '#94a3b8']
    return {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => colors[i % colors.length]),
        borderWidth: 0,
      }]
    }
  }, [data])

  return (
    <div className="max-w-6xl mx-auto px-4">
      <header className="mb-8 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-50 mb-1">Jira Dashboard</h1>
          <p className="text-slate-400">Overview of your Jira activity</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={refreshDashboard} className="px-3 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50" disabled={loading}>Refresh</button>
          {lastFetched && (
            <span className="text-[11px] text-slate-500">Updated {new Date(lastFetched).toLocaleTimeString()} {isStale && <em className="text-amber-400">(stale)</em>}</span>
          )}
        </div>
      </header>

      {loading && !data && (
        <div className="text-center py-12 text-slate-400">Loading dashboard…</div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded text-center my-4">
          Error: {error}
        </div>
      )}

      {data && (
        <div className="space-y-8">
          <section>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <SummaryCard title="My open tickets" value={data.summary?.my_open_tickets ?? 0} />
              <SummaryCard title="My total tickets" value={data.summary?.my_total_tickets ?? 0} />
              <SummaryCard title="Reported by me" value={data.summary?.reported_by_me ?? 0} />
              <SummaryCard title="Recent activity" value={data.summary?.recent_activity ?? 0} />
            </div>
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">Status Distribution</h3>
              <div className="h-56 md:h-64">
                <Bar
                  data={statusChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: true, labels: { color: '#94a3b8' } } },
                    scales: {
                      x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                      y: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(59,130,246,0.1)' } }
                    }
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
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 14, font: { size: 12 } } } }
                  }}
                />
              </div>
            </div>
            <div className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
              <h3 className="text-slate-200 font-semibold mb-3">Top Assignees</h3>
              <div className="h-56 md:h-64">
                <Bar
                  data={assigneeChart}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: {
                      x: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(59,130,246,0.1)' } },
                      y: { ticks: { color: '#94a3b8' }, grid: { display: false } }
                    }
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
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } }
                  }}
                />
              </div>
            </div>
          </section>

          <section className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
            <h3 className="text-slate-200 font-semibold mb-3">Recent Tickets</h3>
            {data.recent_tickets?.length ? (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.recent_tickets.map((t) => (
                  <div key={t.key} className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <a href={t.url} target="_blank" rel="noreferrer" className="text-blue-400 font-semibold">{t.key}</a>
                      <span className="text-xs px-2 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300">{t.status}</span>
                    </div>
                    <div className="text-slate-100 font-medium mb-2">{t.summary}</div>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="px-2 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300">{t.status}</span>
                      <span className={`px-2 py-1 rounded-full border text-red-300 border-red-500/30 ${t.priority === 'High' ? 'bg-red-500/10' : t.priority === 'Medium' ? 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30' : 'bg-green-500/10 text-green-300 border-green-500/30'}`}>{t.priority}</span>
                      <span className="text-slate-400">Updated: {t.updated}</span>
                      <span className="text-slate-400">Assignee: {t.assignee}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-400">No recent tickets.</div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
