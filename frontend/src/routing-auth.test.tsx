import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/routing/ProtectedRoute'
import { PublicOnlyRoute } from '@/components/routing/PublicOnlyRoute'
import { AuthProvider } from '@/context/AuthContext'
import { loginUser, registerUser } from '@/lib/authApi'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'

vi.mock('@/lib/authApi', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
}))

function renderAuthApp(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>

            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route path="/dashboard" element={<div>Dashboard content</div>} />
              </Route>
            </Route>

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('auth routing and screens', () => {
  const mockedLoginUser = vi.mocked(loginUser)
  const mockedRegisterUser = vi.mocked(registerUser)

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders login and register screens', async () => {
    const loginView = renderAuthApp(['/login'])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
    loginView.unmount()

    renderAuthApp(['/register'])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create account' })).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument()
  })

  it('blocks unauthenticated access to protected routes and redirects to login', async () => {
    renderAuthApp(['/dashboard'])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    })
    expect(screen.queryByText('Dashboard content')).not.toBeInTheDocument()
  })

  it('shows validation errors for login/register forms', async () => {
    const loginView = renderAuthApp(['/login'])

    fireEvent.click(await screen.findByRole('button', { name: 'Login' }))
    expect(await screen.findByText('Username is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    loginView.unmount()

    renderAuthApp(['/register'])

    fireEvent.click(await screen.findByRole('button', { name: 'Register' }))
    expect(await screen.findByText('Email is required.')).toBeInTheDocument()
    expect(screen.getByText('Username is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(screen.getByText('Please confirm your password.')).toBeInTheDocument()
  })

  it('updates navigation by auth state and supports logout', async () => {
    localStorage.setItem('hackeurope.auth.token', 'persisted-token')
    renderAuthApp(['/login'])

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument()
    })
    expect(screen.getByText('Dashboard content')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Logout' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    })
    expect(localStorage.getItem('hackeurope.auth.token')).toBeNull()
  })

  it('shows API error feedback on login/register submit failures', async () => {
    mockedLoginUser.mockRejectedValue(new Error('Invalid credentials'))

    const loginView = renderAuthApp(['/login'])

    fireEvent.change(await screen.findByLabelText('Username'), { target: { value: 'marin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))

    expect(await screen.findByText('Failed to login.')).toBeInTheDocument()
    loginView.unmount()

    mockedRegisterUser.mockRejectedValue(new Error('Email already exists'))

    renderAuthApp(['/register'])

    fireEvent.change(await screen.findByLabelText('Email'), { target: { value: 'marin@example.com' } })
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'marin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(await screen.findByText('Failed to register.')).toBeInTheDocument()
  })
})
