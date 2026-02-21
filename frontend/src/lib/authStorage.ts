const TOKEN_STORAGE_KEY = 'hackeurope.auth.token'

export const authStorage = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  },
  setToken(token: string): void {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  },
  clearToken(): void {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  },
}
