import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BillingPage from '@/pages/BillingPage'
import { createBillingCheckout, getBillingSummary, listOwnedTeams } from '@/lib/billingApi'
import type { BillingSummary, Team } from '@/lib/types'

vi.mock('@/lib/billingApi', () => ({
  listOwnedTeams: vi.fn(),
  getBillingSummary: vi.fn(),
  createBillingCheckout: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BillingPage />
    </QueryClientProvider>,
  )
}

function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 'team-1',
    name: 'Core Workspace',
    description: null,
    owner_id: 'user-1',
    created_at: '2026-02-21T10:00:00Z',
    agent_count: 2,
    ...overrides,
  }
}

function makeSummary(overrides: Partial<BillingSummary> = {}): BillingSummary {
  return {
    team_id: 'team-1',
    subscription: {
      status: 'active',
      active_agent_subscriptions: 2,
      stripe_subscription_id: 'sub_123',
      seat_count: 5,
    },
    total_usage_cost: 12.5,
    usage_by_agent: [
      {
        marketplace_agent_id: 'market-1',
        marketplace_agent_name: 'Code Agent Pro',
        total_quantity: 4,
        total_cost: 12.5,
      },
    ],
    recent_usage: [
      {
        id: 'usage-1',
        marketplace_agent_id: 'market-1',
        marketplace_agent_name: 'Code Agent Pro',
        usage_type: 'task_completion',
        quantity: 2,
        cost: 5.0,
        created_at: '2026-02-21T11:00:00Z',
      },
    ],
    ...overrides,
  }
}

describe('BillingPage', () => {
  const mockedListOwnedTeams = vi.mocked(listOwnedTeams)
  const mockedGetBillingSummary = vi.mocked(getBillingSummary)
  const mockedCreateBillingCheckout = vi.mocked(createBillingCheckout)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('renders team selector, subscribe CTA, and usage widgets on success', async () => {
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockResolvedValue(makeSummary())

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Billing & Settings' })).toBeInTheDocument()
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Subscribe' })).toBeInTheDocument()
    expect(await screen.findByText('Total usage cost')).toBeInTheDocument()
    expect((await screen.findAllByText('$12.50')).length).toBeGreaterThan(0)
    expect(screen.getByText('active')).toBeInTheDocument()
    expect((await screen.findAllByText('Code Agent Pro')).length).toBeGreaterThan(0)
  })

  it('subscribes and redirects to checkout on success', async () => {
    const assignSpy = vi.fn()
    vi.stubGlobal('location', {
      ...window.location,
      assign: assignSpy,
      origin: 'http://localhost',
    })
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockResolvedValue(makeSummary())
    mockedCreateBillingCheckout.mockResolvedValue({
      checkout_url: 'https://checkout.stripe.test/session/team-1',
      team_id: 'team-1',
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Subscribe' }))

    await waitFor(() => {
      expect(mockedCreateBillingCheckout).toHaveBeenCalledWith({
        team_id: 'team-1',
        success_url: expect.stringContaining('/billing'),
        cancel_url: expect.stringContaining('/billing'),
      })
    })
    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith('https://checkout.stripe.test/session/team-1')
    })
    expect(screen.getByText('Redirecting to Stripe checkout...')).toBeInTheDocument()
  })

  it('shows subscribe error message when checkout fails', async () => {
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockResolvedValue(makeSummary())
    mockedCreateBillingCheckout.mockRejectedValue(new Error('Checkout is unavailable'))

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Subscribe' }))

    expect(await screen.findByText('Checkout is unavailable')).toBeInTheDocument()
  })

  it('renders empty-state messaging when summary has no usage', async () => {
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockResolvedValue(
      makeSummary({
        total_usage_cost: 0,
        usage_by_agent: [],
        recent_usage: [],
      }),
    )

    renderPage()

    expect(await screen.findByText('$0.00')).toBeInTheDocument()
    expect(screen.getByText('No usage has been recorded for this workspace yet.')).toBeInTheDocument()
    expect(screen.getByText('No recent usage records found.')).toBeInTheDocument()
  })

  it('renders loading state while summary is fetching', async () => {
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockImplementation(() => new Promise(() => {}))

    renderPage()

    expect(await screen.findByText('Loading billing summary...')).toBeInTheDocument()
  })

  it('renders summary fetch error state', async () => {
    mockedListOwnedTeams.mockResolvedValue([makeTeam()])
    mockedGetBillingSummary.mockRejectedValue(new Error('billing summary failed'))

    renderPage()

    expect(await screen.findByText('Failed to load billing summary.')).toBeInTheDocument()
  })
})
