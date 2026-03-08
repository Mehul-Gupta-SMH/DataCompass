/**
 * apiFetch — drop-in replacement for fetch() that automatically injects
 * the JWT Bearer token and fires an 'auth:logout' custom event on 401
 * so AuthContext can react and redirect to the login page.
 */
export async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('data_compass_token') || ''
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('data_compass_token')
    window.dispatchEvent(new Event('auth:logout'))
  }
  return res
}