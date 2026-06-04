import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

interface ValidationState {
  email: {
    value: string
    isValid: boolean
    error?: string
    success?: string
    isRegistered?: boolean
  }
  uniqueName: {
    value: string
    isValid: boolean
    error?: string
    success?: string
    isTaken?: boolean
  }
  password: {
    value: string
    isValid: boolean
    error?: string
    success?: string
  }
  confirmPassword: {
    value: string
    isValid: boolean
    error?: string
    success?: string
  }
}

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    email: '',
    uniqueName: '',
    password: '',
    confirmPassword: ''
  })

  const [validation, setValidation] = useState<ValidationState>({
    email: { value: '', isValid: false },
    uniqueName: { value: '', isValid: false },
    password: { value: '', isValid: false },
    confirmPassword: { value: '', isValid: false }
  })

  const [errors, setErrors] = useState<Partial<Record<keyof typeof formData, string>>>({})
  const [loading, setLoading] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  // Debounce timers
  const [emailDebounce, setEmailDebounce] = useState<NodeJS.Timeout | null>(null)
  const [uniqueNameDebounce, setUniqueNameDebounce] = useState<NodeJS.Timeout | null>(null)

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  // Email validation
  useEffect(() => {
    const email = formData.email.trim()
    const isValidFormat = emailRegex.test(email)

    setValidation(prev => ({
      ...prev,
      email: {
        value: email,
        isValid: isValidFormat && !errors.email
      }
    }))

    // Debounced check if email is registered
    if (emailDebounce) clearTimeout(emailDebounce)

    if (email && isValidFormat) {
      const timer = setTimeout(async () => {
        try {
          const response = await fetch(`/api/v1/auth/check-email?email=${encodeURIComponent(email)}`)
          const data = await response.json()

          if (data.exists) {
            setValidation(prev => ({
              ...prev,
              email: {
                ...prev.email,
                isRegistered: true,
                error: 'This email is already registered.'
              }
            }))
            setErrors(prev => ({ ...prev, email: 'This email is already registered.' }))
          } else {
            setValidation(prev => ({
              ...prev,
              email: {
                ...prev.email,
                isRegistered: false,
                success: 'Email is available!'
              }
            }))
          }
        } catch {
          // Ignore network errors
        }
      }, 500)
      setEmailDebounce(timer)
    } else {
      setValidation(prev => ({
        ...prev,
        email: {
          ...prev.email,
          isRegistered: false,
          error: undefined,
          success: undefined
        }
      }))
    }
  }, [formData.email])

  // Unique name validation
  useEffect(() => {
    const uniqueName = formData.uniqueName.trim()
    const isValidFormat = uniqueName.length > 0 && !uniqueName.includes(' ')

    setValidation(prev => ({
      ...prev,
      uniqueName: {
        value: uniqueName,
        isValid: isValidFormat && !errors.uniqueName
      }
    }))

    // Debounced check if unique name is taken
    if (uniqueNameDebounce) clearTimeout(uniqueNameDebounce)

    if (uniqueName && isValidFormat) {
      const timer = setTimeout(async () => {
        try {
          const response = await fetch(`/api/v1/auth/check-unique-name?unique_name=${encodeURIComponent(uniqueName)}`)
          const data = await response.json()

          if (data.exists) {
            setValidation(prev => ({
              ...prev,
              uniqueName: {
                ...prev.uniqueName,
                isTaken: true,
                error: 'This unique name is already taken.'
              }
            }))
            setErrors(prev => ({ ...prev, uniqueName: 'This unique name is already taken.' }))
          } else {
            setValidation(prev => ({
              ...prev,
              uniqueName: {
                ...prev.uniqueName,
                isTaken: false,
                success: 'Unique name is available!'
              }
            }))
          }
        } catch {
          // Ignore network errors
        }
      }, 500)
      setUniqueNameDebounce(timer)
    } else {
      setValidation(prev => ({
        ...prev,
        uniqueName: {
          ...prev.uniqueName,
          isTaken: false,
          error: undefined,
          success: undefined
        }
      }))
    }
  }, [formData.uniqueName])

  // Form submission validation
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrors({})
    setSuccessMessage('')

    // Validate password length
    if (formData.password.length < 8) {
      setErrors(prev => ({ ...prev, password: 'Password must be at least 8 characters long.' }))
      return
    }

    // Validate confirm password matches
    if (formData.password !== formData.confirmPassword) {
      setErrors(prev => ({ ...prev, confirmPassword: 'Passwords do not match.' }))
      return
    }

    setLoading(true)
    try {
      await register({
        email: formData.email.trim(),
        uniqueName: formData.uniqueName.trim(),
        password: formData.password
      })

      setSuccessMessage('Registration successful! Redirecting to login...')

      // Redirect to login after 2 seconds
      setTimeout(() => {
        navigate('/login')
      }, 2000)
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrors(prev => ({ ...prev, general: err.message }))
      } else {
        setErrors(prev => ({ ...prev, general: 'Registration failed. Please try again.' }))
      }
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field: keyof typeof formData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }))
  }

  return (
    <div className="register-page">
      <div className="register-card">
        <h1>⚔️ LotR TCG</h1>
        <p className="subtitle">Admin Panel — create your account</p>

        {errors.general && <div className="error-banner">{errors.general}</div>}
        {successMessage && <div className="success-banner">{successMessage}</div>}

        <form onSubmit={handleSubmit}>
          {/* Email */}
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={formData.email}
              onChange={handleChange('email')}
              placeholder="admin@example.com"
              required
              autoComplete="email"
            />
            {validation.email.isValid && !validation.email.isRegistered && (
              <div className="validation-success">Looks good!</div>
            )}
            {validation.email.isRegistered && (
              <div className="validation-error">{validation.email.error}</div>
            )}
            {errors.email && <div className="validation-error">{errors.email}</div>}
          </div>

          {/* Unique Name */}
          <div className="form-group">
            <label htmlFor="uniqueName">Unique Name</label>
            <input
              id="uniqueName"
              type="text"
              value={formData.uniqueName}
              onChange={handleChange('uniqueName')}
              placeholder="Enter your unique name"
              required
              autoComplete="username"
            />
            {validation.uniqueName.isValid && !validation.uniqueName.isTaken && (
              <div className="validation-success">Looks good!</div>
            )}
            {validation.uniqueName.isTaken && (
              <div className="validation-error">{validation.uniqueName.error}</div>
            )}
            {errors.uniqueName && <div className="validation-error">{errors.uniqueName}</div>}
          </div>

          {/* Password */}
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={formData.password}
              onChange={handleChange('password')}
              placeholder="••••••••"
              required
              minLength={8}
            />
            {errors.password && <div className="validation-error">{errors.password}</div>}
          </div>

          {/* Confirm Password */}
          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange('confirmPassword')}
              placeholder="••••••••"
              required
            />
            {errors.confirmPassword && <div className="validation-error">{errors.confirmPassword}</div>}
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '8px' }}
          >
            {loading ? 'Registering...' : 'Create account'}
          </button>
        </form>

        <p className="login-link">
          Already have an account?{' '}
          <a href="/login" style={{ color: 'var(--color-primary)' }}>Sign in</a>
        </p>
      </div>
    </div>
  )
}
