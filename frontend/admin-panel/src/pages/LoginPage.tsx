import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { signIn, completeMfaLogin, recoverWithBackupCode } = useAuth()
  const navigate = useNavigate()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [step, setStep] = useState<'password' | 'mfa'>('password')
  const [mfaToken, setMfaToken] = useState('')
  const [code, setCode] = useState('')
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)
  const [recoveryCode, setRecoveryCode] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await signIn(identifier, password)
      if (result.requires2fa) {
        setMfaToken(result.mfaToken)
        setStep('mfa')
      } else {
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Login failed. Check your credentials and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleMfaSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await completeMfaLogin(mfaToken, code)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Invalid code. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleRecoverySubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await recoverWithBackupCode(mfaToken, recoveryCode)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Invalid or already-used recovery code. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (step === 'mfa') {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>⚔️ LotR TCG</h1>
          <p className="subtitle">
            {useRecoveryCode ? 'Enter one of your backup recovery codes' : 'Enter your 6-digit authentication code'}
          </p>

          {error && <div className="error-banner">{error}</div>}

          {useRecoveryCode ? (
            <form onSubmit={handleRecoverySubmit}>
              <div className="form-group">
                <label htmlFor="recoveryCode">Recovery code</label>
                <input
                  id="recoveryCode"
                  type="text"
                  autoCapitalize="none"
                  autoCorrect="off"
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value.trim())}
                  placeholder="a1b2c3d4-e5f6a7b8"
                  required
                  autoFocus
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={loading}
                style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
              >
                {loading ? 'Recovering…' : 'Recover account'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleMfaSubmit}>
              <div className="form-group">
                <label htmlFor="code">Authentication code</label>
                <input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  required
                  autoFocus
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={loading}
                style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
              >
                {loading ? 'Verifying…' : 'Verify'}
              </button>
            </form>
          )}

          <button
            type="button"
            className="btn-link"
            onClick={() => {
              setError('')
              setUseRecoveryCode((prev) => !prev)
            }}
            style={{
              width: '100%',
              marginTop: '12px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-primary)',
              fontSize: '13px',
              textDecoration: 'underline',
            }}
          >
            {useRecoveryCode
              ? 'Have your authenticator app? Enter a code instead'
              : 'Lost access to your authenticator app? Recover with a backup code'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>⚔️ LotR TCG</h1>
        <p className="subtitle">Admin Panel — restricted access</p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="identifier">Email or username</label>
            <input
              id="identifier"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="admin@example.com or username"
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
