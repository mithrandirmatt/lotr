/**
 * Debounced API check utility for real-time validation
 * Checks if a user exists and is valid for login/registration
 */

export interface ApiCheckResult {
  exists: boolean
  isValid: boolean | null
  error: string | null
  cached?: boolean
}

export interface ApiCheckOptions {
  delay?: number
  cacheDuration?: number
  enabled?: boolean
}

const DEFAULT_OPTIONS: ApiCheckOptions = {
  delay: 300,
  cacheDuration: 5000,
  enabled: true
}

class ApiCheckService {
  private cache = new Map<string, { result: ApiCheckResult; timestamp: number }>()
  private timers = new Map<string, NodeJS.Timeout>()
  private options: ApiCheckOptions

  constructor(options: ApiCheckOptions = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options }
  }

  /**
   * Check if API checks are enabled
   */
  isEnabled(): boolean {
    return this.options.enabled !== false
  }

  /**
   * Perform an API check with debouncing
   */
  async check<T>(
    identifier: string,
    checkFn: (identifier: string) => Promise<T>
  ): Promise<ApiCheckResult & { data?: T }> {
    // Skip if disabled
    if (!this.isEnabled()) {
      return { exists: false, isValid: null, error: null, cached: true }
    }

    const cacheKey = identifier.toLowerCase().trim()

    // Check cache first
    const cachedEntry = this.cache.get(cacheKey)
    if (cachedEntry && Date.now() - cachedEntry.timestamp < this.options.cacheDuration) {
      return {
        exists: cachedEntry.result.exists,
        isValid: cachedEntry.result.isValid,
        error: cachedEntry.result.error,
        cached: true
      }
    }

    // Clear existing timer for this identifier
    if (this.timers.has(cacheKey)) {
      clearTimeout(this.timers.get(cacheKey))
    }

    // Set up debounced check
    const timer = setTimeout(async () => {
      try {
        const data = await checkFn(cacheKey)
        
        const result: ApiCheckResult = {
          exists: data !== null,
          isValid: data?.isValid ?? null,
          error: data?.error ?? null
        }

        // Update cache
        this.cache.set(cacheKey, { result, timestamp: Date.now() })

        return { ...result, data }
      } catch (error) {
        const result: ApiCheckResult = {
          exists: false,
          isValid: null,
          error: error instanceof Error ? error.message : 'API check failed'
        }

        this.cache.set(cacheKey, { result, timestamp: Date.now() })
        return result
      } finally {
        // Clean up timer
        this.timers.delete(cacheKey)
      }
    }, this.options.delay)

    this.timers.set(cacheKey, timer)

    // Return placeholder - actual result will be available after delay
    return {
      exists: false,
      isValid: null,
      error: null,
      cached: true
    }
  }

  /**
   * Clear cache for a specific identifier
   */
  clearCache(identifier: string): void {
    const cacheKey = identifier.toLowerCase().trim()
    this.cache.delete(cacheKey)
    if (this.timers.has(cacheKey)) {
      clearTimeout(this.timers.get(cacheKey))
      this.timers.delete(cacheKey)
    }
  }

  /**
   * Clear all cache
   */
  clearAllCache(): void {
    this.cache.clear()
    this.timers.clear()
  }

  /**
   * Get cache statistics
   */
  getStats(): { entries: number, activeTimers: number } {
    return {
      entries: this.cache.size,
      activeTimers: this.timers.size
    }
  }
}

// Singleton instance
export const apiCheckService = new ApiCheckService()

/**
 * Hook for real-time API validation
 */
export function useApiCheck<T>(
  identifier: string,
  checkFn: (identifier: string) => Promise<T | null>,
  options: ApiCheckOptions = {}
): ApiCheckResult & { data?: T } {
  const [result, setResult] = useState<ApiCheckResult & { data?: T }>({
    exists: false,
    isValid: null,
    error: null
  })

  useEffect(() => {
    if (!options.enabled) {
      setResult({ exists: false, isValid: null, error: null })
      return
    }

    const check = async () => {
      const finalResult = await apiCheckService.check<T>(identifier, checkFn)
      setResult(finalResult)
    }

    check()

    return () => {
      apiCheckService.clearCache(identifier)
    }
  }, [identifier, options.enabled, checkFn])

  return result
}

/**
 * Hook for real-time user existence check
 */
export function useUserExistsCheck(
  emailOrUsername: string,
  options: ApiCheckOptions = {}
): ApiCheckResult {
  const check = async (identifier: string): Promise<{ isValid?: boolean; error?: string } | null> => {
    try {
      // Check if user exists via API
      const response = await fetch(`/api/users/check/${encodeURIComponent(identifier)}`)
      const data = await response.json()
      
      if (!response.ok) {
        return { error: data.error || 'User not found' }
      }
      
      return { isValid: data.is_valid }
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Check failed' }
    }
  }

  return useApiCheck(emailOrUsername, check, options)
}

/**
 * Hook for real-time password strength check
 */
export function usePasswordStrength(password: string): ApiCheckResult {
  const check = async (identifier: string): Promise<{ isValid?: boolean; error?: string } | null> => {
    // Client-side validation
    const validators = {
      minLength: identifier.length >= 8,
      hasUpperCase: /[A-Z]/.test(identifier),
      hasLowerCase: /[a-z]/.test(identifier),
      hasNumber: /\d/.test(identifier),
      hasSpecialChar: /[!@#$%^&*(),.?":{}|<>]/.test(identifier)
    }

    const validCount = Object.values(validators).filter(v => v).length
    const isValid = validCount >= 3

    return { isValid }
  }

  return useApiCheck(password, check, { delay: 100 })
}
