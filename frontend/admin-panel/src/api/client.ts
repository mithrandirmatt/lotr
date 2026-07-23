import axios, { type AxiosInstance } from 'axios'
import type {
  Token,
  UserResponse,
  AdminUserListResponse,
  AdminUserSummary,
  AdminTolkienAdjustRequest,
  AdminUserDeleteRequest,
  CardListResponse,
  CardResponse,
  CardCreate,
  CardStats,
  StorePricingResponse,
  AdminAnalyticsData,
  TwoFactorChallenge,
  TwoFactorSetupResponse,
  TwoFactorEnableResponse,
} from './types'

const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach stored access token to every request
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<Token | TwoFactorChallenge> {
  // OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
  const params = new URLSearchParams()
  params.append('username', email)
  params.append('password', password)
  const { data } = await http.post<Token | TwoFactorChallenge>('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export function isTwoFactorChallenge(result: Token | TwoFactorChallenge): result is TwoFactorChallenge {
  return (result as TwoFactorChallenge).requires_2fa === true
}

export async function register(data: {
  email: string
  uniqueName: string
  password: string
  confirmPassword: string
}): Promise<{ message: string }> {
  const { data: response } = await http.post<{ message: string }>('/auth/register', {
    email: data.email,
    unique_name: data.uniqueName,
    password: data.password,
    confirm_password: data.confirmPassword,
  })
  return response
}

export async function setup2fa(): Promise<TwoFactorSetupResponse> {
  const { data } = await http.post<TwoFactorSetupResponse>('/auth/2fa/setup')
  return data
}

export async function enable2fa(code: string): Promise<TwoFactorEnableResponse> {
  const { data } = await http.post<TwoFactorEnableResponse>('/auth/2fa/enable', { code })
  return data
}

export async function disable2fa(password: string, code: string): Promise<{ message: string }> {
  const { data } = await http.post<{ message: string }>('/auth/2fa/disable', { password, code })
  return data
}

export async function verify2faLogin(mfaToken: string, code: string): Promise<Token> {
  const { data } = await http.post<Token>('/auth/2fa/verify-login', { mfa_token: mfaToken, code })
  return data
}

export async function recover2fa(mfaToken: string, recoveryCode: string): Promise<Token> {
  const { data } = await http.post<Token>('/auth/2fa/recover', {
    mfa_token: mfaToken,
    recovery_code: recoveryCode,
  })
  return data
}

export async function getMe(): Promise<UserResponse> {
  const { data } = await http.get<UserResponse>('/users/me')
  return data
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout')
}

// ── Admin: Users ──────────────────────────────────────────────────────────────

export async function adminListUsers(
  search?: string,
  page = 1,
  pageSize = 20,
): Promise<AdminUserListResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (search) params['search'] = search
  const { data } = await http.get<AdminUserListResponse>('/admin/users', { params })
  return data
}

export async function adminAdjustTolkiens(
  userId: string,
  payload: AdminTolkienAdjustRequest,
): Promise<AdminUserSummary> {
  const { data } = await http.post<AdminUserSummary>(
    `/admin/users/${userId}/tolkiens`,
    payload,
  )
  return data
}

export async function adminToggleModerator(userId: string): Promise<AdminUserSummary> {
  const { data } = await http.put<AdminUserSummary>(`/admin/users/${userId}/moderator`)
  return data
}

export async function adminDeleteUser(
  userId: string,
  payload: AdminUserDeleteRequest,
): Promise<{ message: string }> {
  const { data } = await http.delete<{ message: string }>(
    `/admin/users/${userId}`,
    { data: payload },
  )
  return data
}

// ── Admin: Cards ──────────────────────────────────────────────────────────────

export async function adminGetCardStats(): Promise<CardStats> {
  const { data } = await http.get<CardStats>('/admin/cards/stats')
  return data
}

export async function listCards(
  page = 1,
  pageSize = 20,
  search?: string,
): Promise<CardListResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize }
  if (search) params['search'] = search
  const { data } = await http.get<CardListResponse>('/cards', { params })
  return data
}

export async function createCard(payload: CardCreate): Promise<CardResponse> {
  const { data } = await http.post<CardResponse>('/cards', payload)
  return data
}

export async function adminRemoveCard(cardId: string): Promise<CardResponse> {
  const { data } = await http.delete<CardResponse>(`/admin/cards/${cardId}`)
  return data
}

// ── Store ──────────────────────────────────────────────────────────────────────

export async function getStorePricing(): Promise<StorePricingResponse> {
  const { data } = await http.get<StorePricingResponse>('/store/pricing')
  return data
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export async function adminGetAnalytics(
  period: '7d' | '30d' | '90d' | '1y' = '30d',
): Promise<AdminAnalyticsData> {
  const { data } = await http.get<AdminAnalyticsData>(`/admin/analytics`, {
    params: { period },
  })
  return data
}
