import React, { useState } from 'react'

const exampleQueries = [
  { label: 'My assigned tickets', query: 'Show me my tickets assigned to me' },
  { label: 'High priority this week', query: 'High priority tickets created this week' },
  { label: 'In progress tickets', query: 'All tickets in progress' },
  { label: 'My reported open tickets', query: 'Tickets reported by me that are still open' },
  { label: 'Updated today', query: 'Show me tickets updated today' },
]

export default function AiSearch() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [context, setContext] = useState(null)

  const performSearch = async (searchQuery) => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, context })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setResults(data)
      setContext(data.context)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-50 mb-1">AI Ticket Search</h1>
        <p className="text-slate-400">Ask natural questions about your Jira tickets</p>
      </header>

      <div className="bg-[#0f0f23]/60 backdrop-blur rounded-xl p-6 md:p-8 shadow-lg border border-blue-500/10 mb-8">
        <form
          className="flex flex-col md:flex-row gap-4 mb-4"
          onSubmit={(e) => { e.preventDefault(); if (query) performSearch(query) }}
        >
          <input
            type="text"
            className="flex-1 px-5 py-3 rounded-lg border-2 border-blue-500/20 bg-[#0f0f23]/80 text-slate-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            placeholder="Ask me anything about your tickets..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            required
          />
          <button
            type="submit"
            className="px-8 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-700 text-white font-semibold shadow hover:-translate-y-1 transition disabled:opacity-60"
            disabled={loading}
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        <div className="flex flex-wrap gap-2 mt-2 justify-center md:justify-start">
          {exampleQueries.map((ex, i) => (
            <button
              key={i}
              className="bg-[#0f0f23]/80 text-slate-400 px-4 py-2 rounded-full text-sm border border-blue-500/20 hover:bg-blue-500/10 hover:text-blue-400 transition"
              onClick={() => { setQuery(ex.query); performSearch(ex.query) }}
              type="button"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-center py-12 text-slate-400">
          <div className="mx-auto mb-4 w-10 h-10 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
          Searching tickets...
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded text-center my-4">
          Error: {error}
        </div>
      )}

      {results && (
        <div className="bg-[#0f0f23]/60 backdrop-blur rounded-xl p-6 md:p-8 shadow-lg border border-blue-500/10">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
            <div>
              <h2 className="text-xl font-bold text-slate-50">{results.description}</h2>
              <div className="text-slate-400 text-sm">{results.tickets.length} ticket{results.tickets.length !== 1 ? 's' : ''} found</div>
            </div>
          </div>
          <div className="bg-[#0f0f23]/80 p-4 rounded mb-6 border-l-4 border-blue-500">
            <div className="text-xs text-slate-400 uppercase font-semibold mb-2">Generated JQL Query:</div>
            <div className="font-mono bg-black/60 text-slate-200 p-3 rounded text-sm overflow-x-auto">{results.jql}</div>
          </div>

          {results.tickets.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <div className="text-5xl mb-2">⚠</div>
              <h3 className="text-lg font-bold">No tickets found</h3>
              <p>Try adjusting your search query or check if the filters are correct.</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.tickets.map((ticket) => (
                <div key={ticket.key} className="bg-[#0f0f23]/80 border border-blue-500/10 rounded-lg p-6 shadow hover:-translate-y-1 hover:border-blue-500 transition">
                  <div className="flex justify-between items-start mb-4">
                    <a href={ticket.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 font-bold text-lg hover:underline">{ticket.key}</a>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase
                      ${ticket.status === 'To Do' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : ''}
                      ${ticket.status === 'In Progress' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : ''}
                      ${ticket.status === 'Done' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : ''}
                      ${ticket.status === 'Blocked' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : ''}
                    `}>
                      {ticket.status}
                    </span>
                  </div>
                  <div className="font-semibold text-slate-50 mb-4">{ticket.summary}</div>
                  <div className="grid grid-cols-2 gap-2 text-sm text-slate-400">
                    <div><span className="font-medium text-slate-300">Assignee:</span> {ticket.assignee}</div>
                    <div><span className="font-medium text-slate-300">Reporter:</span> {ticket.reporter}</div>
                    <div>
                      <span className="font-medium text-slate-300">Priority:</span>
                      <span className={`ml-2 px-2 py-1 rounded text-xs font-semibold
                        ${ticket.priority === 'High' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : ''}
                        ${ticket.priority === 'Medium' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : ''}
                        ${ticket.priority === 'Low' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : ''}
                      `}>
                        {ticket.priority}
                      </span>
                    </div>
                    <div><span className="font-medium text-slate-300">Updated:</span> {ticket.updated}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
