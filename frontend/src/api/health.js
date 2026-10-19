export async function fetchReadiness() {
  const response = await fetch('/api/v1/health/ready', {
    headers: { Accept: 'application/json' },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || `服务返回 HTTP ${response.status}`)
  }
  return payload
}
