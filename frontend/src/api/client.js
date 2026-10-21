const TOKEN_KEY = 'survey_system_token'

export class ApiError extends Error {
  constructor(status, payload) {
    super(payload?.message || payload?.detail || `请求失败（HTTP ${status}）`)
    this.status = status
    this.code = payload?.code || 'HTTP_ERROR'
    this.details = payload?.details ?? null
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function apiRequest(path, options = {}) {
  const token = getToken()
  const headers = { Accept: 'application/json', ...(options.headers || {}) }
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    body: options.body === undefined || options.body instanceof FormData
      ? options.body
      : JSON.stringify(options.body),
  })
  if (response.status === 204) return null
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(response.status, payload)
  return payload
}
