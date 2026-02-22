import { useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { TaskLog } from '@/lib/types'

interface TaskActivityFeedProps {
  logs: TaskLog[]
  isPolling: boolean
  maxHeight?: string
}

const logTypeConfig: Record<string, { label: string; color: string; icon: string }> = {
  info: { label: 'Info', color: 'bg-blue-100 text-blue-700', icon: 'info' },
  agent_assigned: { label: 'Assigned', color: 'bg-purple-100 text-purple-700', icon: 'user' },
  skill_start: { label: 'Executing', color: 'bg-amber-100 text-amber-700', icon: 'play' },
  agent_output: { label: 'Output', color: 'bg-green-100 text-green-700', icon: 'terminal' },
  error: { label: 'Error', color: 'bg-red-100 text-red-700', icon: 'alert' },
  status_change: { label: 'Status', color: 'bg-slate-100 text-slate-700', icon: 'refresh' },
}

function LogIcon({ type }: { type: string }) {
  const iconType = logTypeConfig[type]?.icon || 'info'
  
  switch (iconType) {
    case 'user':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      )
    case 'play':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    case 'terminal':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      )
    case 'alert':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      )
    case 'refresh':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      )
    default:
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
  }
}

function formatTime(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function TaskActivityFeed({ logs, isPolling, maxHeight = '400px' }: TaskActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs.length])

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Activity Feed</CardTitle>
          {isPolling && (
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-xs text-slate-500">Live</span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={scrollRef}
          className="space-y-3 overflow-y-auto pr-2"
          style={{ maxHeight }}
        >
          {logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="rounded-full bg-slate-100 p-3 mb-3">
                <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p className="text-sm text-slate-500">No activity yet</p>
              <p className="text-xs text-slate-400 mt-1">Logs will appear here when the task starts</p>
            </div>
          ) : (
            logs.map((log) => {
              const config = logTypeConfig[log.log_type] || logTypeConfig.info
              return (
                <div
                  key={log.id}
                  className="flex gap-3 p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                >
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${config.color}`}>
                    <LogIcon type={log.log_type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className={`text-xs ${config.color}`}>
                        {config.label}
                      </Badge>
                      {log.agent_name && (
                        <span className="text-xs font-medium text-slate-600">
                          {log.agent_name}
                        </span>
                      )}
                      <span className="text-xs text-slate-400">
                        {formatTime(log.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap break-words">
                      {log.message}
                    </p>
                    {log.details && log.log_type === 'agent_output' && 'full_output' in log.details && log.details.full_output != null && (
                      <details className="mt-2">
                        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">
                          View full output
                        </summary>
                        <pre className="mt-2 p-2 bg-slate-900 text-slate-100 rounded text-xs overflow-x-auto max-h-[200px] overflow-y-auto">
                          {String(log.details.full_output)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </CardContent>
    </Card>
  )
}
