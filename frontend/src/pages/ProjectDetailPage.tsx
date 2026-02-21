import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toApiErrorMessage } from '@/lib/apiClient'
import {
  addProjectAllowedAgent,
  approvePlan,
  fetchPMDashboard,
  listOwnedAgents,
  rejectPlan,
  removeProjectAllowedAgent,
} from '@/lib/pmApi'

function formatDate(value: string | null): string {
  if (!value) {
    return 'n/a'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'n/a'
  }
  return date.toLocaleString()
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [rejectingPlanId, setRejectingPlanId] = useState<string | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const projectId = id ?? ''

  const dashboardQuery = useQuery({
    queryKey: ['pm-dashboard', projectId],
    queryFn: () => fetchPMDashboard(projectId),
    enabled: Boolean(projectId),
  })

  const agentsQuery = useQuery({
    queryKey: ['owned-agents'],
    queryFn: listOwnedAgents,
    enabled: Boolean(projectId),
  })

  const addAllowedAgentMutation = useMutation({
    mutationFn: (agentId: string) => addProjectAllowedAgent(projectId, agentId),
    onSuccess: () => {
      setActionMessage('Agent added to project allowlist.')
      setSelectedAgentId('')
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const removeAllowedAgentMutation = useMutation({
    mutationFn: (agentId: string) => removeProjectAllowedAgent(projectId, agentId),
    onSuccess: () => {
      setActionMessage('Agent removed from project allowlist.')
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const approvePlanMutation = useMutation({
    mutationFn: (planId: string) => approvePlan(planId),
    onSuccess: (plan) => {
      setActionMessage(`Plan ${plan.id} approved at ${formatDate(plan.approved_at)}.`)
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const rejectPlanMutation = useMutation({
    mutationFn: ({ planId, reason }: { planId: string; reason: string }) => rejectPlan(planId, reason),
    onSuccess: (plan) => {
      setRejectingPlanId(null)
      setRejectionReason('')
      setActionMessage(`Plan ${plan.id} rejected.`)
      void queryClient.invalidateQueries({ queryKey: ['pm-dashboard', projectId] })
    },
  })

  const allowedAgentIds = useMemo(
    () => new Set((dashboardQuery.data?.allowed_agents ?? []).map((entry) => entry.agent_id)),
    [dashboardQuery.data?.allowed_agents],
  )

  const candidateAgents = useMemo(
    () => (agentsQuery.data ?? []).filter((agent) => !allowedAgentIds.has(agent.id)),
    [agentsQuery.data, allowedAgentIds],
  )

  if (!projectId) {
    return <p className="text-sm text-red-600">Project id is missing.</p>
  }

  if (dashboardQuery.isLoading) {
    return <p className="text-sm text-slate-600">Loading PM dashboard...</p>
  }

  if (dashboardQuery.isError) {
    return <p className="text-sm text-red-600">{toApiErrorMessage(dashboardQuery.error, 'Failed to load PM dashboard.')}</p>
  }

  const dashboard = dashboardQuery.data

  if (!dashboard) {
    return <p className="text-sm text-slate-600">No dashboard data found.</p>
  }

  return (
    <section className="space-y-6">
      <div>
        <Link className="text-sm text-sky-700 hover:underline" to="/projects">
          Back to projects
        </Link>
        <h2 className="text-2xl font-semibold">{dashboard.project.name}</h2>
        <p className="text-sm text-slate-600">{dashboard.project.description ?? 'No description available.'}</p>
      </div>

      {actionMessage && <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700">{actionMessage}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Goals and Progress</CardTitle>
          <CardDescription>Project goals, milestones, timeline, and task status rollup.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="font-medium">Goals</h3>
            {dashboard.project.goals.length === 0 ? (
              <p className="text-sm text-slate-600">No goals defined.</p>
            ) : (
              <ul className="list-disc pl-6 text-sm text-slate-700">
                {dashboard.project.goals.map((goal) => (
                  <li key={goal}>{goal}</li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="font-medium">Task Status</h3>
            {Object.keys(dashboard.tasks_by_status).length === 0 ? (
              <p className="text-sm text-slate-600">No project tasks linked yet.</p>
            ) : (
              <div className="grid gap-2 md:grid-cols-3">
                {Object.entries(dashboard.tasks_by_status).map(([status, count]) => (
                  <div key={status} className="rounded-md border border-slate-200 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">{status.replaceAll('_', ' ')}</p>
                    <p className="text-xl font-semibold">{count}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3 className="font-medium">Timeline</h3>
            <p className="text-sm text-slate-700">
              Start: {String(dashboard.project.timeline.start ?? 'n/a')} | End: {String(dashboard.project.timeline.end ?? 'n/a')}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Team Progress Snapshot</CardTitle>
          <CardDescription>Current project members and workload.</CardDescription>
        </CardHeader>
        <CardContent>
          {dashboard.team_members.length === 0 ? (
            <p className="text-sm text-slate-600">No team members assigned yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member ID</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Capacity</TableHead>
                  <TableHead>Current Load</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboard.team_members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>{member.user_id}</TableCell>
                    <TableCell>{member.role}</TableCell>
                    <TableCell>{member.capacity.toFixed(2)}</TableCell>
                    <TableCell>{member.current_load.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Plan Approval Gate</CardTitle>
          <CardDescription>Pending OA plans that require PM approval or rejection.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {dashboard.pending_approvals.length === 0 ? (
            <p className="text-sm text-slate-600">No plans pending PM decision.</p>
          ) : (
            dashboard.pending_approvals.map((plan) => (
              <div key={plan.id} className="space-y-2 rounded-md border border-slate-200 p-4">
                <p className="text-sm font-medium">Plan {plan.id}</p>
                <p className="text-sm text-slate-600">
                  Created: {formatDate(plan.created_at)} | Status: {plan.status}
                </p>
                <p className="text-sm text-slate-700">
                  Summary:{' '}
                  {typeof plan.plan_data.summary === 'string'
                    ? plan.plan_data.summary
                    : 'No summary provided.'}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    onClick={() => {
                      if (!window.confirm(`Approve plan ${plan.id}?`)) {
                        return
                      }
                      approvePlanMutation.mutate(plan.id)
                    }}
                    disabled={approvePlanMutation.isPending || rejectPlanMutation.isPending}
                  >
                    Approve
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setRejectingPlanId(plan.id)
                      setRejectionReason('')
                    }}
                    disabled={approvePlanMutation.isPending || rejectPlanMutation.isPending}
                  >
                    Reject
                  </Button>
                </div>

                {rejectingPlanId === plan.id && (
                  <form
                    className="space-y-2"
                    onSubmit={(event) => {
                      event.preventDefault()
                      const reason = rejectionReason.trim()
                      if (!reason) {
                        setActionMessage('Rejection reason is required.')
                        return
                      }
                      if (!window.confirm(`Reject plan ${plan.id}?`)) {
                        return
                      }
                      rejectPlanMutation.mutate({ planId: plan.id, reason })
                    }}
                  >
                    <Input
                      aria-label={`Rejection reason for plan ${plan.id}`}
                      placeholder="Provide rejection reason"
                      value={rejectionReason}
                      onChange={(event) => setRejectionReason(event.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button type="submit" variant="destructive" disabled={rejectPlanMutation.isPending}>
                        Confirm rejection
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setRejectingPlanId(null)
                          setRejectionReason('')
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            ))
          )}

          {(approvePlanMutation.error || rejectPlanMutation.error) && (
            <p className="text-sm text-red-600">
              {toApiErrorMessage(
                approvePlanMutation.error ?? rejectPlanMutation.error,
                'Plan action failed.',
              )}
            </p>
          )}

          {dashboard.recent_plans.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-medium">Recent Plan Decisions</h3>
              {dashboard.recent_plans.map((plan) => (
                <p key={plan.id} className="text-sm text-slate-700">
                  {plan.id}: {plan.status} at {formatDate(plan.approved_at ?? plan.updated_at ?? plan.created_at)}
                </p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Project Agent Allowlist</CardTitle>
          <CardDescription>Add and remove agents available to OA for this project.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              if (!selectedAgentId) {
                return
              }
              addAllowedAgentMutation.mutate(selectedAgentId)
            }}
          >
            <select
              className="h-9 min-w-64 rounded-md border border-slate-300 bg-white px-3 text-sm"
              aria-label="Select agent to allow"
              value={selectedAgentId}
              onChange={(event) => setSelectedAgentId(event.target.value)}
            >
              <option value="">Select an owned agent</option>
              {candidateAgents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name} ({agent.role})
                </option>
              ))}
            </select>
            <Button type="submit" disabled={!selectedAgentId || addAllowedAgentMutation.isPending}>
              Add agent
            </Button>
          </form>

          {agentsQuery.isLoading && <p className="text-sm text-slate-600">Loading available agents...</p>}
          {agentsQuery.isError && (
            <p className="text-sm text-red-600">{toApiErrorMessage(agentsQuery.error, 'Failed to load agents.')}</p>
          )}
          {addAllowedAgentMutation.error && (
            <p className="text-sm text-red-600">
              {toApiErrorMessage(addAllowedAgentMutation.error, 'Failed to add agent to allowlist.')}
            </p>
          )}
          {removeAllowedAgentMutation.error && (
            <p className="text-sm text-red-600">
              {toApiErrorMessage(removeAllowedAgentMutation.error, 'Failed to remove agent from allowlist.')}
            </p>
          )}

          {dashboard.allowed_agents.length === 0 ? (
            <p className="text-sm text-slate-600">No agents currently allowed for this project.</p>
          ) : (
            <div className="space-y-2">
              {dashboard.allowed_agents.map((entry) => (
                <div key={entry.id} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
                  <div>
                    <p className="font-medium">{entry.agent.name}</p>
                    <p className="text-sm text-slate-600">
                      Role: {entry.agent.role} | Added: {formatDate(entry.created_at)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      if (!window.confirm(`Remove ${entry.agent.name} from allowlist?`)) {
                        return
                      }
                      removeAllowedAgentMutation.mutate(entry.agent_id)
                    }}
                    disabled={removeAllowedAgentMutation.isPending}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
