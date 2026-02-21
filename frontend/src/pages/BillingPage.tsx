import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { createBillingCheckout, getBillingSummary, listOwnedTeams } from '@/lib/billingApi'
import { toApiErrorMessage } from '@/lib/apiClient'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'n/a'
  }
  return date.toLocaleString()
}

export default function BillingPage() {
  const [selectedTeamId, setSelectedTeamId] = useState<string>('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const teamsQuery = useQuery({
    queryKey: ['owned-teams'],
    queryFn: listOwnedTeams,
  })

  const resolvedTeamId = selectedTeamId || teamsQuery.data?.[0]?.id || ''

  const billingSummaryQuery = useQuery({
    queryKey: ['billing-summary', resolvedTeamId],
    queryFn: () => getBillingSummary(resolvedTeamId),
    enabled: Boolean(resolvedTeamId),
  })

  const selectedTeam = useMemo(
    () => teamsQuery.data?.find((team) => team.id === resolvedTeamId) ?? null,
    [teamsQuery.data, resolvedTeamId],
  )

  const subscribeMutation = useMutation({
    mutationFn: (teamId: string) =>
      createBillingCheckout({
        team_id: teamId,
        success_url: `${window.location.origin}/billing`,
        cancel_url: `${window.location.origin}/billing`,
      }),
    onSuccess: (payload) => {
      setActionMessage('Redirecting to Stripe checkout...')
      window.location.assign(payload.checkout_url)
    },
    onError: (error) => {
      setActionMessage(error instanceof Error ? error.message : 'Failed to create checkout session.')
    },
  })

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Billing & Settings</h2>
        <p className="text-sm text-slate-600">Manage workspace subscription and monitor usage costs.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workspace Subscription</CardTitle>
          <CardDescription>Select a team you own, then start checkout.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {teamsQuery.isLoading && <p className="text-sm text-slate-600">Loading workspaces...</p>}

          {teamsQuery.isError && (
            <p className="text-sm text-red-600">
              {toApiErrorMessage(teamsQuery.error, 'Failed to load workspaces.')}
            </p>
          )}

          {!teamsQuery.isLoading && !teamsQuery.isError && (teamsQuery.data?.length ?? 0) === 0 && (
            <p className="text-sm text-slate-600">No owned workspaces found. Create a team to enable billing.</p>
          )}

          {(teamsQuery.data?.length ?? 0) > 0 && (
            <div className="flex flex-col gap-3 md:flex-row md:items-end">
              <label className="flex flex-1 flex-col gap-2 text-sm">
                <span className="font-medium text-slate-700">Workspace</span>
                <select
                  value={resolvedTeamId}
                  onChange={(event) => {
                    setSelectedTeamId(event.target.value)
                    setActionMessage(null)
                  }}
                  className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
                >
                  {teamsQuery.data?.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                type="button"
                onClick={() => {
                  if (!resolvedTeamId) {
                    return
                  }
                  subscribeMutation.mutate(resolvedTeamId)
                }}
                disabled={!resolvedTeamId || subscribeMutation.isPending}
              >
                {subscribeMutation.isPending ? 'Preparing checkout...' : 'Subscribe'}
              </Button>
            </div>
          )}

          {selectedTeam && (
            <p className="text-xs text-slate-500">
              Team ID: <span className="font-mono">{selectedTeam.id}</span>
            </p>
          )}

          {actionMessage && (
            <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">{actionMessage}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage Summary</CardTitle>
          <CardDescription>Cost and activity snapshots for the selected workspace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!resolvedTeamId && <p className="text-sm text-slate-600">Select a workspace to view billing usage.</p>}

          {resolvedTeamId && billingSummaryQuery.isLoading && (
            <p className="text-sm text-slate-600">Loading billing summary...</p>
          )}

          {resolvedTeamId && billingSummaryQuery.isError && (
            <p className="text-sm text-red-600">
              {toApiErrorMessage(billingSummaryQuery.error, 'Failed to load billing summary.')}
            </p>
          )}

          {billingSummaryQuery.data && (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Total usage cost</p>
                  <p className="text-xl font-semibold">{formatCurrency(billingSummaryQuery.data.total_usage_cost)}</p>
                </div>
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Subscription status</p>
                  <p className="text-xl font-semibold">{billingSummaryQuery.data.subscription.status}</p>
                </div>
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Active agent subscriptions</p>
                  <p className="text-xl font-semibold">
                    {billingSummaryQuery.data.subscription.active_agent_subscriptions}
                  </p>
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-semibold">Usage by marketplace agent</h3>
                {billingSummaryQuery.data.usage_by_agent.length === 0 ? (
                  <p className="text-sm text-slate-600">No usage has been recorded for this workspace yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Agent</TableHead>
                        <TableHead>Total quantity</TableHead>
                        <TableHead>Total cost</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {billingSummaryQuery.data.usage_by_agent.map((row) => (
                        <TableRow key={row.marketplace_agent_id}>
                          <TableCell>{row.marketplace_agent_name}</TableCell>
                          <TableCell>{row.total_quantity}</TableCell>
                          <TableCell>{formatCurrency(row.total_cost)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-sm font-semibold">Recent usage records</h3>
                {billingSummaryQuery.data.recent_usage.length === 0 ? (
                  <p className="text-sm text-slate-600">No recent usage records found.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Time</TableHead>
                        <TableHead>Agent</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Cost</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {billingSummaryQuery.data.recent_usage.map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>{formatDate(row.created_at)}</TableCell>
                          <TableCell>{row.marketplace_agent_name}</TableCell>
                          <TableCell>{row.usage_type}</TableCell>
                          <TableCell>{row.quantity}</TableCell>
                          <TableCell>{formatCurrency(row.cost)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
