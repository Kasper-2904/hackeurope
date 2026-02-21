import { apiClient } from '@/lib/apiClient'
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from '@/types/auth'

export async function registerUser(payload: RegisterRequest): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>('/auth/register', payload)
  return data
}

export async function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
  return data
}
