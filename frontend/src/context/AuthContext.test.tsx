import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { apiClient } from '@/lib/apiClient'
import { loginUser, registerUser } from '@/lib/authApi'

vi.mock('@/lib/authApi', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
}))

function Harness() {
  const { token, isAuthenticated, isHydrating, login, register, logout } = useAuth()

  return (
    <div>
      <div data-testid="token">{token ?? 'null'}</div>
      <div data-testid="is-authenticated">{String(isAuthenticated)}</div>
      <div data-testid="is-hydrating">{String(isHydrating)}</div>

      <button
        type="button"
        onClick={async () => {
          try {
            await login({ username: 'marin', password: 'secret123' })
          } catch {
            // read from screen for failures
          }
        }}
      >
        login
      </button>

      <button
        type="button"
        onClick={async () => {
          try {
            await register({
              email: 'marin@example.com',
              username: 'marin',
              password: 'secret123',
            })
          } catch {
            // read from screen for failures
          }
        }}
      >
        register
      </button>

      <button type="button" onClick={logout}>
        logout
      </button>
    </div>
  )
}

describe('AuthProvider', () => {
  const mockedLoginUser = vi.mocked(loginUser)
  const mockedRegisterUser = vi.mocked(registerUser)

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete apiClient.defaults.headers.common.Authorization
  })

  it('handles login success by setting auth state, storage, and auth header', async () => {
    mockedLoginUser.mockResolvedValue({
      access_token: 'token-123',
      token_type: 'bearer',
      expires_in: 3600,
    })

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    )

    expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false')

    fireEvent.click(screen.getByRole('button', { name: 'login' }))

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('token-123')
    })

    expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true')
    expect(localStorage.getItem('hackeurope.auth.token')).toBe('token-123')
    expect(apiClient.defaults.headers.common.Authorization).toBe('Bearer token-123')
  })

  it('surfaces API failures for login/register without mutating auth state', async () => {
    mockedLoginUser.mockRejectedValue(new Error('Invalid credentials'))
    mockedRegisterUser.mockRejectedValue(new Error('Email already exists'))

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'login' }))
    fireEvent.click(screen.getByRole('button', { name: 'register' }))

    expect(screen.getByTestId('token')).toHaveTextContent('null')
    expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false')
    expect(localStorage.getItem('hackeurope.auth.token')).toBeNull()
    expect(apiClient.defaults.headers.common.Authorization).toBeUndefined()
  })

  it('hydrates token from storage on initial load', async () => {
    localStorage.setItem('hackeurope.auth.token', 'persisted-token')

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    )

    expect(screen.getByTestId('is-hydrating')).toHaveTextContent('false')

    expect(screen.getByTestId('token')).toHaveTextContent('persisted-token')
    expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true')
    expect(apiClient.defaults.headers.common.Authorization).toBe('Bearer persisted-token')
  })

  it('cleans up token state, storage, and header on logout', async () => {
    localStorage.setItem('hackeurope.auth.token', 'persisted-token')

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true')
    })

    fireEvent.click(screen.getByRole('button', { name: 'logout' }))

    expect(screen.getByTestId('token')).toHaveTextContent('null')
    expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false')
    expect(localStorage.getItem('hackeurope.auth.token')).toBeNull()
    expect(apiClient.defaults.headers.common.Authorization).toBeUndefined()
  })
})
