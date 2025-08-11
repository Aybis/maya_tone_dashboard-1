import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import AiSearch from './pages/AiSearch'

function NavBar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0f0f23]/80 backdrop-blur border-b border-blue-500/10 shadow-lg">
      <div className="max-w-6xl mx-auto flex justify-between items-center py-3 px-6">
        <a href="/" className="text-blue-400 font-bold text-lg">Jira Dashboard</a>
        <ul className="hidden md:flex gap-6">
          <li>
            <NavLink to="/" end className={({isActive}) => isActive ? 'text-blue-400 bg-blue-400/10 px-3 py-1 rounded' : 'text-slate-400 hover:text-blue-400'}>
              Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to="/ai-search" className={({isActive}) => isActive ? 'text-blue-400 bg-blue-400/10 px-3 py-1 rounded' : 'text-slate-400 hover:text-blue-400'}>
              AI Search
            </NavLink>
          </li>
        </ul>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="pt-20">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ai-search" element={<AiSearch />} />
        </Routes>
      </main>
    </div>
  )
}
