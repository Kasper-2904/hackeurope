import axios, { AxiosError } from 'axios'
import type { ApiErrorResponse } from '@/types/auth'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

export function setAuthHeader(token: string | null): void {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`
    return
  }

  delete apiClient.defaults.headers.common.Authorization
}

export function toApiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (!(error instanceof AxiosError)) {
    return fallback
  }

  const payload = error.response?.data as ApiErrorResponse | undefined
  const detail = payload?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) {
    return detail[0].msg
  }

  return fallback
}
