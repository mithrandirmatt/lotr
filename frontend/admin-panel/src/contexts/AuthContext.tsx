import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from '../api/client'
import type { UserResponse } from '../api/types'

interface AuthState {
  user: UserResponse | null
  loading: boolean
}

type SignInResult = { requires2fa: false } | { requires2fa: true; mfaToken: string }

interface AuthContextValue extends AuthState {
  signIn: (email: string, password: string) => Promise<SignInResult>
  completeMfaLogin: (mfaToken: string, code: string) => Promise<void>
  recoverWithBackupCode: (mfaToken: string, recoveryCode: string) => Promise<void>
  register: (data: {
    email: string
    uniqueName: string
    password: string
    confirmPassword: string
  }) => Promise<{ message: string }>
  refreshUser: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true })

  // Rehydrate from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setState({ user: null, loading: false })
      return
    }
    api.getMe()
      .then((user) => setState({ user, loading: false }))
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        setState({ user: null, loading: false })
      })
  }, [])

  async function signIn(email: string, password: string): Promise<SignInResult> {
    const result = await api.login(email, password)
    if (api.isTwoFactorChallenge(result)) {
      return { requires2fa: true, mfaToken: result.mfa_token }
    }
    localStorage.setItem('access_token', result.access_token)
    localStorage.setItem('refresh_token', result.refresh_token)
    const user = await api.getMe()
    // Only allow panel admins to proceed
    if (!user.is_admin) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      throw new Error('Access denied: this account does not have admin panel privileges.')
    }
    setState({ user, loading: false })
    return { requires2fa: false }
  }

  async function completeMfaLogin(mfaToken: string, code: string) {
    const tokens = await api.verify2faLogin(mfaToken, code)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const user = await api.getMe()
    if (!user.is_admin) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      throw new Error('Access denied: this account does not have admin panel privileges.')
    }
    setState({ user, loading: false })
  }

  async function recoverWithBackupCode(mfaToken: string, recoveryCode: string) {
    const tokens = await api.recover2fa(mfaToken, recoveryCode)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const user = await api.getMe()
    if (!user.is_admin) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      throw new Error('Access denied: this account does not have admin panel privileges.')
    }
    // is_2fa_enabled is now false server-side; ProtectedRoute will redirect
    // the user to /2fa-setup so they can scan a fresh QR code.
    setState({ user, loading: false })
  }

  async function register(data: {
    email: string
    uniqueName: string
    password: string
    confirmPassword: string
  }) {
    return await api.register(data)
  }

  async function refreshUser() {
    const user = await api.getMe()
    setState({ user, loading: false })
  }

  async function signOut() {
    try { await api.logout() } catch { /* ignore */ }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setState({ user: null, loading: false })
  }

  return (
    <AuthContext.Provider
      value={{ ...state, signIn, completeMfaLogin, recoverWithBackupCode, register, refreshUser, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
