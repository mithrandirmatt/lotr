import { type CSSProperties } from 'react'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  color?: string
  fullScreen?: boolean
  children?: React.ReactNode
}

export function LoadingSpinner({
  size = 'md',
  color = '#3b82f6',
  fullScreen = false,
  children
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16'
  }

  const containerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    ...(fullScreen ? { position: 'fixed', inset: 0, backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 9999 } : {})
  }

  return (
    <div style={containerStyle}>
      <div className={`spinner ${sizeClasses[size]}`} style={{ color }}>
        {children}
      </div>
    </div>
  )
}

interface InputLoadingProps {
  size?: 'sm' | 'md' | 'lg'
  color?: string
}

export function InputLoading({ size = 'md', color = '#9ca3af' }: InputLoadingProps) {
  const sizeClasses = {
    sm: 'w-24 h-2',
    md: 'w-48 h-2',
    lg: 'w-64 h-2'
  }

  return (
    <div className="flex items-center gap-1">
      <div className={`animate-pulse ${sizeClasses[size]}`} style={{ backgroundColor: color }} />
      <div className={`animate-pulse delay-75 ${sizeClasses[size]}`} style={{ backgroundColor: color }} />
      <div className={`animate-pulse delay-150 ${sizeClasses[size]}`} style={{ backgroundColor: color }} />
    </div>
  )
}

interface ButtonLoadingProps {
  size?: 'sm' | 'md' | 'lg'
  color?: string
}

export function ButtonLoading({ size = 'md', color = '#3b82f6' }: ButtonLoadingProps) {
  const sizeClasses = {
    sm: 'w-20 h-8',
    md: 'w-32 h-10',
    lg: 'w-48 h-12'
  }

  return (
    <div className="relative overflow-hidden rounded-lg" style={{ width: 1, height: 1 }}>
      <div className={`absolute inset-0 ${sizeClasses[size]}`} style={{ backgroundColor: color }} />
      <div 
        className="absolute inset-0 animate-loading-bar" 
        style={{ backgroundColor: 'rgba(255, 255, 255, 0.3)' }} 
      />
    </div>
  )
}

interface FieldLoadingProps {
  size?: 'sm' | 'md' | 'lg'
}

export function FieldLoading({ size = 'md' }: FieldLoadingProps) {
  const sizeClasses = {
    sm: 'w-32',
    md: 'w-48',
    lg: 'w-64'
  }

  return (
    <div className="space-y-2">
      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      <div className={`h-10 ${sizeClasses[size]} bg-gray-200 dark:bg-gray-700 rounded animate-pulse`} />
    </div>
  )
}

interface PageLoadingProps {
  fullScreen?: boolean
}

export function PageLoading({ fullScreen = false }: PageLoadingProps) {
  return (
    <div className={`min-h-screen flex items-center justify-center ${fullScreen ? 'fixed inset-0 bg-gray-50 dark:bg-gray-900' : ''}`}>
      <LoadingSpinner fullScreen={fullScreen}>
        <span className="ml-2 text-gray-600 dark:text-gray-400">Loading...</span>
      </LoadingSpinner>
    </div>
  )
}

// CSS for loading animations
export const loadingStyles = `
  @keyframes spinner {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .spinner {
    animation: spinner 1s linear infinite;
  }
  
  @keyframes loading-bar {
    0% { left: -100%; }
    100% { left: 100%; }
  }
  
  .animate-loading-bar {
    animation: loading-bar 1.5s ease-in-out infinite;
  }
`
