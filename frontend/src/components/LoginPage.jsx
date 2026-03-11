import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'

function CompassIcon() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#2563eb" strokeWidth="1.4">
      <circle cx="12" cy="12" r="10" />
      <polygon points="12,5 14.5,12 12,19 9.5,12" fill="#2563eb" stroke="none" opacity="0.25" />
      <polygon points="5,12 12,9.5 19,12 12,14.5" fill="#2563eb" stroke="none" />
      <circle cx="12" cy="12" r="1.2" fill="#fff" stroke="none" />
    </svg>
  )
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" style={{ flexShrink: 0 }}>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  )
}

export default function LoginPage() {
  const [mode, setMode]         = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [googleEnabled, setGoogleEnabled] = useState(false)
  const { login, ssoError } = useAuth()

  useEffect(() => {
    fetch('/auth/google/enabled')
      .then((r) => r.json())
      .then((d) => setGoogleEnabled(d.enabled ?? false))
      .catch(() => {})
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        const res = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        })
        const data = await res.json()
        if (!res.ok) { setError(data.detail ?? 'Registration failed.'); return }
      }
      await login(username, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const disabled = loading || !username.trim() || !password.trim()

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#f3f4f6',
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: '40px 44px', width: 360,
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
      }}>

        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 28 }}>
          <CompassIcon />
          <span style={{ fontSize: 20, fontWeight: 700, color: '#1e1e2e', letterSpacing: '-0.3px' }}>
            Poly-QL
          </span>
        </div>

        {/* Mode toggle */}
        <div style={{
          display: 'flex', marginBottom: 28, borderRadius: 8,
          overflow: 'hidden', border: '1px solid #e5e7eb',
        }}>
          {['login', 'register'].map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError('') }}
              style={{
                flex: 1, padding: '9px 0', fontSize: 13,
                fontWeight: mode === m ? 600 : 400,
                background: mode === m ? '#2563eb' : '#fff',
                color: mode === m ? '#fff' : '#6b7280',
                border: 'none', cursor: 'pointer',
              }}
            >
              {m === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit}>
          {/* Username */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
              style={{
                width: '100%', padding: '9px 12px', fontSize: 14,
                border: '1px solid #d1d5db', borderRadius: 7,
                boxSizing: 'border-box', outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Password */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Password{' '}
              {mode === 'register' && (
                <span style={{ fontWeight: 400, color: '#9ca3af' }}>(min 6 characters)</span>
              )}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              style={{
                width: '100%', padding: '9px 12px', fontSize: 14,
                border: '1px solid #d1d5db', borderRadius: 7,
                boxSizing: 'border-box', outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Errors */}
          {(error || ssoError) && (
            <div style={{
              background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 6,
              padding: '8px 12px', fontSize: 13, color: '#991b1b', marginBottom: 14,
            }}>
              {error || ssoError}
            </div>
          )}

          <button
            type="submit"
            disabled={disabled}
            style={{
              width: '100%', padding: '10px 0', fontSize: 14, fontWeight: 700,
              background: disabled ? '#e5e7eb' : '#2563eb',
              color: disabled ? '#9ca3af' : '#fff',
              border: 'none', borderRadius: 7, cursor: disabled ? 'default' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        {/* Google SSO */}
        {googleEnabled && (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              margin: '20px 0 0', color: '#9ca3af', fontSize: 12,
            }}>
              <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
              <span>or</span>
              <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
            </div>
            <a
              href="/auth/google"
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                gap: 10, width: '100%', marginTop: 14, padding: '10px 0',
                fontSize: 14, fontWeight: 600, color: '#374151',
                border: '1px solid #d1d5db', borderRadius: 7, background: '#fff',
                textDecoration: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            >
              <GoogleIcon />
              Sign in with Google
            </a>
          </>
        )}
      </div>
    </div>
  )
}
