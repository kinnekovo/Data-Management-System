import { reactive } from 'vue'
import { apiRequest, getToken, setToken } from './api/client.js'

export const auth = reactive({ user: null, loading: false, initialized: false })

export async function restoreSession() {
  if (!getToken()) {
    auth.initialized = true
    return
  }
  auth.loading = true
  try {
    auth.user = await apiRequest('/auth/me')
  } catch {
    setToken(null)
    auth.user = null
  } finally {
    auth.loading = false
    auth.initialized = true
  }
}

export async function login(username, password) {
  const result = await apiRequest('/auth/login', { method: 'POST', body: { username, password } })
  setToken(result.access_token)
  auth.user = result.user
  auth.initialized = true
  return result
}

export function logout() {
  setToken(null)
  auth.user = null
}
