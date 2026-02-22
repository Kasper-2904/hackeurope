import { useState, useRef, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useQuery } from '@tanstack/react-query'
import { getTeams, getTeamProjects } from '@/lib/api'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 text-sm font-medium transition border-b-2 ${
    isActive 
      ? 'border-sky-600 text-sky-600' 
      : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
  }`

function TeamsDropdown() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: teams } = useQuery({
    queryKey: ['teams'],
    queryFn: getTeams,
  })

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition"
      >
        Teams
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-1 w-64 bg-white border border-slate-200 rounded-lg shadow-lg z-50">
          {teams && teams.length > 0 ? (
            teams.map((team) => (
              <TeamItem key={team.id} teamId={team.id} teamName={team.name} onSelect={() => setIsOpen(false)} />
            ))
          ) : (
            <div className="px-4 py-3 text-sm text-slate-500">No teams yet</div>
          )}
        </div>
      )}
    </div>
  )
}

function TeamItem({ teamId, teamName, onSelect }: { teamId: string; teamName: string; onSelect: () => void }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { data: projects } = useQuery({
    queryKey: ['team-projects', teamId],
    queryFn: () => getTeamProjects(teamId),
  })

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
      >
        <span className="font-medium">{teamName}</span>
        <svg className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {isExpanded && projects && projects.length > 0 && (
        <div className="bg-slate-50 py-1">
          {projects.map((project) => (
            <NavLink
              key={project.id}
              to={`/projects/${project.id}`}
              onClick={onSelect}
              className="block px-6 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              {project.name}
            </NavLink>
          ))}
          {projects.length === 0 && (
            <div className="px-6 py-2 text-xs text-slate-400">No projects</div>
          )}
        </div>
      )}
    </div>
  )
}

export function AppShell() {
  const navigate = useNavigate()
  const { logout, user } = useAuth()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto w-full px-4">
          <div className="flex h-12 items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-8">
              <h1 className="text-lg font-semibold text-slate-900">HackEurope</h1>
              
              {/* Main Navigation */}
              <nav className="flex items-center h-full">
                <NavLink to="/dashboard" className={navLinkClass}>
                  Dashboard
                </NavLink>
                <TeamsDropdown />
                <NavLink to="/marketplace" className={navLinkClass}>
                  Marketplace
                </NavLink>
                <NavLink to="/context" className={navLinkClass}>
                  Context
                </NavLink>
              </nav>
            </div>

            {/* Right Side - User Menu */}
            <div className="flex items-center gap-4">
              <NavLink to="/connections" className={navLinkClass}>
                Connections
              </NavLink>
              <NavLink to="/billing" className={navLinkClass}>
                Billing
              </NavLink>
              <div className="flex items-center gap-2 border-l border-slate-200 pl-4">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-sky-100 flex items-center justify-center text-xs font-medium text-sky-700">
                    {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
                  </div>
                  <span className="text-sm text-slate-700 hidden sm:inline">
                    {user?.full_name || user?.username}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="text-sm text-slate-500 hover:text-slate-700 transition"
                  title="Logout"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
