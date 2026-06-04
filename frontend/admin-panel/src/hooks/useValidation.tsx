import { useState, useCallback, useEffect, type ReactNode } from 'react'

export interface FieldError {
  message: string
  type?: 'required' | 'email' | 'minLength' | 'maxLength' | 'pattern' | 'custom'
}

interface ValidationContextValue {
  errors: Record<string, FieldError>
  isFormValid: boolean
  setFieldError: (field: string, error: FieldError) => void
  clearFieldError: (field: string) => void
  clearAllErrors: () => void
  validateField: (field: string, value: string, validators: Record<string, (v: string) => boolean>) => void
}

export const ValidationContext = React.createContext<ValidationContextValue | null>(null)

export function useValidation(): ValidationContextValue {
  const context = React.useContext(ValidationContext)
  if (!context) {
    throw new Error('useValidation must be used within ValidationProvider')
  }
  return context
}

export function ValidationProvider({ children }: { children: ReactNode }) {
  const [errors, setErrors] = useState<Record<string, FieldError>>({})
  const isFormValid = Object.values(errors).every(e => e.message === '')

  const setFieldError = useCallback((field: string, error: FieldError) => {
    setErrors(prev => ({ ...prev, [field]: error }))
  }, [])

  const clearFieldError = useCallback((field: string) => {
    setErrors(prev => {
      const newErrors = { ...prev }
      delete newErrors[field]
      return newErrors
    })
  }, [])

  const clearAllErrors = useCallback(() => {
    setErrors({})
  }, [])

  const validateField = useCallback((
    field: string,
    value: string,
    validators: Record<string, (v: string) => boolean>
  ) => {
    let error: FieldError | undefined

    for (const [rule, validator] of Object.entries(validators)) {
      if (!validator(value)) {
        error = {
          message: `${field} ${rule}`,
          type: rule as any
        }
        break
      }
    }

    if (error) {
      setFieldError(field, error)
      return false
    }

    clearFieldError(field)
    return true
  }, [setFieldError, clearFieldError])

  const value = React.useMemo(() => ({
    errors,
    isFormValid,
    setFieldError,
    clearFieldError,
    clearAllErrors,
    validateField
  }), [errors, isFormValid, setFieldError, clearFieldError, clearAllErrors, validateField])

  return (
    <ValidationContext.Provider value={value}>
      {children}
    </ValidationContext.Provider>
  )
}

// Custom hook for email validation
export function useEmailValidation(email: string) {
  const { validateField, setFieldError, clearFieldError } = useValidation()

  useEffect(() => {
    if (!email) {
      clearFieldError('email')
      return
    }

    const validators: Record<string, (v: string) => boolean> = {
      required: (v) => v.length > 0,
      email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
      minLength: (v) => v.length >= 5,
      maxLength: (v) => v.length <= 255
    }

    validateField('email', email, validators)
  }, [email, validateField, setFieldError, clearFieldError])
}

// Custom hook for password validation
export function usePasswordValidation(password: string) {
  const { validateField, setFieldError, clearFieldError } = useValidation()

  useEffect(() => {
    if (!password) {
      clearFieldError('password')
      return
    }

    const validators: Record<string, (v: string) => boolean> = {
      required: (v) => v.length > 0,
      minLength: (v) => v.length >= 8,
      maxLength: (v) => v.length <= 128,
      hasUpperCase: (v) => /[A-Z]/.test(v),
      hasLowerCase: (v) => /[a-z]/.test(v),
      hasNumber: (v) => /\d/.test(v),
      hasSpecialChar: (v) => /[!@#$%^&*(),.?":{}|<>]/.test(v)
    }

    validateField('password', password, validators)
  }, [password, validateField, setFieldError, clearFieldError])
}

// Custom hook for username validation
export function useUsernameValidation(username: string) {
  const { validateField, setFieldError, clearFieldError } = useValidation()

  useEffect(() => {
    if (!username) {
      clearFieldError('username')
      return
    }

    const validators: Record<string, (v: string) => boolean> = {
      required: (v) => v.length > 0,
      minLength: (v) => v.length >= 3,
      maxLength: (v) => v.length <= 30,
      alphanumeric: (v) => /^[a-zA-Z0-9_]+$/.test(v)
    }

    validateField('username', username, validators)
  }, [username, validateField, setFieldError, clearFieldError])
}
