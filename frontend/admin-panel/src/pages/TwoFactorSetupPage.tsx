import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import * as api from '../api/client'

export default function TwoFactorSetupPage() {
  const { user, loading, refreshUser } = useAuth()
  const navigate = useNavigate()

  const [initializing, setInitializing] = useState(true)
  const [qrCode, setQrCode] = useState('')
  const [secret, setSecret] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)

  useEffect(() => {
    if (loading) return
    if (!user) {
      navigate('/login', { replace: true })
      return
    }
    if (user.is_2fa_enabled) {
      navigate('/', { replace: true })
      return
    }
    api.setup2fa()
      .then((data) => {
        setSecret(data.secret)
        setQrCode(data.qr_code_png_base64)
      })
      .catch(() => setError('Failed to start two-factor setup. Please try again.'))
      .finally(() => setInitializing(false))
  }, [loading, user, navigate])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const { recovery_codes } = await api.enable2fa(code)
      setRecoveryCodes(recovery_codes)
      await refreshUser()
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Invalid code. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || initializing) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <span style={{ color: 'var(--color-text-muted)' }}>Loading…</span>
      </div>
    )
  }

  if (recoveryCodes) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>⚔️ LotR TCG</h1>
          <p className="subtitle">Save your recovery codes</p>
          <p>
            Store these 10 single-use recovery codes somewhere safe. Each one can be used once to sign in
            if you lose access to your authenticator app. <strong>They will not be shown again.</strong>
          </p>
          <pre
            style={{
              background: 'var(--color-surface, #1e1e1e)',
              padding: '12px',
              borderRadius: '6px',
              overflowX: 'auto',
              lineHeight: 1.6,
            }}
          >
            {recoveryCodes.join('\n')}
          </pre>
          <button
            type="button"
            className="btn-primary"
            style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
            onClick={() => navigate('/', { replace: true })}
          >
            Continue to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>⚔️ LotR TCG</h1>
        <p className="subtitle">Set up two-factor authentication</p>
        <p>Scan this QR code with Google Authenticator, Authy, 1Password, or a similar app.</p>

        {error && <div className="error-banner">{error}</div>}

        {qrCode && (
          <img
            src={`data:image/png;base64,${qrCode}`}
            alt="Two-factor authentication QR code"
            style={{ display: 'block', margin: '0 auto 12px', width: 200, height: 200 }}
          />
        )}

        <p style={{ wordBreak: 'break-all', fontSize: '13px' }}>
          Can&apos;t scan? Enter this code manually: <code>{secret}</code>
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="code">6-digit code</label>
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
            disabled={submitting}
            style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
          >
            {submitting ? 'Verifying…' : 'Enable two-factor authentication'}
          </button>
        </form>
      </div>
    </div>
  )
}
