/** TypeScript interfaces matching the backend Pydantic schemas. */

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserResponse {
  id: string
  email: string
  username: string
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  tolkien_balance: number
  created_at: string
  updated_at: string
}

export interface AdminUserSummary {
  id: string
  email: string
  username: string
  is_active: boolean
  is_admin: boolean
  is_moderator: boolean
  tolkien_balance: number
  created_at: string
}

export interface AdminUserListResponse {
  items: AdminUserSummary[]
  total: number
}

export interface AdminTolkienAdjustRequest {
  amount: number
  reason?: string
}

export interface AdminUserDeleteRequest {
  confirm_user_id: string
  confirm_username: string
  confirm_email: string
}

export type Rarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary'

export interface CardResponse {
  id: string
  name: string
  cost: number
  rarity: Rarity
  description?: string
  stats?: Record<string, unknown>
  image_url?: string
  is_active?: boolean
  created_at: string
  updated_at: string
}

export interface CardListResponse {
  items: CardResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CardCreate {
  name: string
  cost: number
  rarity: Rarity
  description?: string
  stats?: Record<string, unknown>
  image_url?: string
}

export interface CardStats {
  total_cards: number
  total_ownerships: number
  total_purchases: number
}

export interface StorePricingResponse {
  currency: string
  usd_per_tolkien: number
  products: Record<string, number>
}

// ── Analytics ─────────────────────────────────────────────────────────────────────

export interface AdminAnalyticsData {
  // Revenue metrics
  total_revenue: number
  revenue_change_30d: number
  revenue_by_month: { month: string; revenue: number }[]

  // User metrics
  active_users: number
  user_growth_30d: number
  users_by_month: { month: string; users: number }[]

  // Deck metrics
  total_decks: number
  deck_growth_30d: number
  avg_cards_per_deck: number
  avg_cards_change_30d: number

  // Top performers
  top_decks: { name: string; value: number; change?: number }[]
  top_categories: { name: string; value: number; change?: number }[]
  top_countries: { name: string; value: number; change?: number }[]

  // Platform health
  api_response_time_ms: number
  error_rate: number
  uptime_percentage: number
}
