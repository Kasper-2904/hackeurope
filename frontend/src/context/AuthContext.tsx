import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { loginUser, registerUser } from '@/lib/authApi'
import { setAuthHeader, toApiErrorMessage } from '@/lib/apiClient'
import { authStorage } from '@/lib/authStorage'
import type { LoginRequest, RegisterRequest } from '@/types/auth'

interface AuthContextValue {
  token: string | null
  isAuthenticated: boolean
  isHydrating: boolean
  login: (payload: LoginRequest) => Promise<void>
  register: (payload: RegisterRequest) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => authStorage.getToken())
  const isHydrating = false

  useEffect(() => {
    setAuthHeader(token)
  }, [token])

  const login = useCallback(async (payload: LoginRequest) => {
    try {
      const response = await loginUser(payload)
      setToken(response.access_token)
      setAuthHeader(response.access_token)
      authStorage.setToken(response.access_token)
    } catch (error) {
      throw new Error(toApiErrorMessage(error, 'Failed to login.'))
    }
  }, [])

  const register = useCallback(async (payload: RegisterRequest) => {
    try {
      await registerUser(payload)
    } catch (error) {
      throw new Error(toApiErrorMessage(error, 'Failed to register.'))
    }
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setAuthHeader(null)
    authStorage.clearToken()
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      isHydrating,
      login,
      register,
      logout,
    }),
    [token, isHydrating, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
