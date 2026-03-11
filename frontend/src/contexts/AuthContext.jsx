import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

/** Decode the JWT payload without verifying the signature (backend verifies). */
function decodeToken(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.exp && payload.exp * 1000 < Date.now()) return null
    return { id: payload.uid, username: payload.sub }
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('poly_ql_token') || '')
  const [ssoError, setSsoError] = useState('')

  const user = token ? decodeToken(token) : null

  // Handle Google SSO redirect: backend appends #sso_token=... or #sso_error=... to the URL
  useEffect(() => {
    const hash = window.location.hash
      if (hash.startsWith('#sso_token=')) {
        const t = hash.slice('#sso_token='.length)
        localStorage.setItem('poly_ql_token', t)
        setToken(t)
        window.history.replaceState(null, '', window.location.pathname)
    } else if (hash.startsWith('#sso_error=')) {
      const msg = decodeURIComponent(hash.slice('#sso_error='.length))
      setSsoError(msg)
      window.history.replaceState(null, '', window.location.pathname)
    }
  }, [])

  // Listen for 401 signals fired by apiFetch (token expired / invalid)
  useEffect(() => {
    const handler = () => setToken('')
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  async function login(username, password) {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail ?? 'Login failed.')
    localStorage.setItem('poly_ql_token', data.access_token)
    setToken(data.access_token)
  }

  function logout() {
    localStorage.removeItem('poly_ql_token')
    setToken('')
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, ssoError }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
