import { apiClient, toApiErrorMessage } from '@/lib/apiClient'
import type {
  BillingSubscribeRequest,
  BillingSubscribeResponse,
  BillingSummary,
  Team,
} from '@/lib/types'

export async function listOwnedTeams(): Promise<Team[]> {
  try {
    const { data } = await apiClient.get<Team[]>('/teams')
    return data
  } catch (error) {
    throw new Error(toApiErrorMessage(error, 'Failed to load teams.'))
  }
}

export async function getBillingSummary(teamId: string): Promise<BillingSummary> {
  try {
    const { data } = await apiClient.get<BillingSummary>(`/billing/summary/${teamId}`)
    return data
  } catch (error) {
    throw new Error(toApiErrorMessage(error, 'Failed to load billing summary.'))
  }
}

export async function createBillingCheckout(
  payload: BillingSubscribeRequest,
): Promise<BillingSubscribeResponse> {
  try {
    const { data } = await apiClient.post<BillingSubscribeResponse>('/billing/subscribe', payload)
    return data
  } catch (error) {
    throw new Error(toApiErrorMessage(error, 'Failed to create checkout session.'))
  }
}
