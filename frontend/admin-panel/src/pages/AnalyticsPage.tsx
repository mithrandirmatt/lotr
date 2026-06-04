import { useCallback, useEffect, useState } from 'react'
import { adminGetAnalytics } from '../api/client'
import type { AdminAnalyticsData } from '../api/types'

// ── Stat Card ────────────────────────────────────────────────────────

interface StatCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon: string
  color: string
}

function StatCard({ title, value, change, changeLabel, icon, color }: StatCardProps) {
  const isPositive = change && change >= 0
  const changeColor = isPositive ? 'var(--color-success)' : 'var(--color-danger)'

  return (
    <div className="stat-card" style={{ borderLeft: `4px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{title}</span>
        <span style={{ fontSize: 18, opacity: 0.8 }}>{icon}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>{value}</div>
      {change !== undefined && changeLabel && (
        <div style={{ fontSize: 12, color: changeColor }}>
          {changeLabel}
        </div>
      )}
    </div>
  )
}

// ── Revenue Chart (Simple Bar) ───────────────────────────────────────────────

interface RevenueChartProps {
  data: { month: string; revenue: number }[]
}

function RevenueChart({ data }: RevenueChartProps) {
  const maxValue = Math.max(...data.map((d) => d.revenue), 1)
  const barHeight = 200
  const maxBarHeight = (barHeight / maxValue) * 100

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, height: barHeight, padding: '12px 0' }}>
      {data.map((d, idx) => {
        const heightPct = (d.revenue / maxValue) * 100
        return (
          <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div
              style={{
                width: '100%',
                height: `${Math.max(heightPct, 4)}%`,
                backgroundColor: 'var(--color-primary)',
                borderRadius: 4,
                transition: 'opacity 0.2s',
                opacity: 0.8,
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'linear-gradient(to top, rgba(255,255,255,0.2), transparent)',
                }}
              />
            </div>
            <span style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 6 }}>
              {d.month}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── User Growth Chart (Simple Line) ──────────────────────────────────────────

interface UserGrowthChartProps {
  data: { month: string; users: number }[]
}

function UserGrowthChart({ data }: UserGrowthChartProps) {
  const maxValue = Math.max(...data.map((d) => d.users), 1)
  const points = data.map((d, idx) => {
    const x = (idx / (data.length - 1 || 1)) * 100
    const y = 100 - (d.users / maxValue) * 100
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width="100%" height="180" style={{ overflow: 'visible' }}>
      {/* Grid lines */}
      {[0, 25, 50, 75, 100].map((tick) => (
        <line
          key={tick}
          x1="0"
          y1={tick}
          x2="100%"
          y2={tick}
          stroke="var(--color-background-secondary)"
          strokeDasharray="4,4"
        />
      ))}
      {/* Line */}
      <polyline
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="2"
        points={points}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Data points */}
      {data.map((d, idx) => {
        const x = (idx / (data.length - 1 || 1)) * 100
        const y = 100 - (d.users / maxValue) * 100
        return (
          <circle
            key={idx}
            cx={x}
            cy={y}
            r="4"
            fill="var(--color-primary)"
            stroke="white"
            strokeWidth="2"
            style={{ cursor: 'pointer' }}
          />
        )
      })}
    </svg>
  )
}

// ── Top Cards ────────────────────────────────────────────────────────

interface TopCardsProps {
  title: string
  items: { name: string; value: number; change?: number }[]
}

function TopCards({ title, items }: TopCardsProps) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 16, marginBottom: 16 }}>{title}</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
        {items.map((item, idx) => (
          <div key={idx} className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
              {item.name}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
              {item.value.toLocaleString()}
            </div>
            {item.change !== undefined && (
              <div style={{ fontSize: 12, color: item.change >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                {item.change >= 0 ? '↑' : '↓'} {Math.abs(item.change)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData] = useState<AdminAnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [period, setPeriod] = useState<'7d' | '30d' | '90d' | '1y'>('30d')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await adminGetAnalytics(period)
      setData(result)
    } catch {
      setError('Failed to load analytics data.')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { load() }, [load])

  const periodLabels: Record<string, string> = {
    '7d': 'Last 7 days',
    '30d': 'Last 30 days',
    '90d': 'Last 90 days',
    '1y': 'Last year',
  }

  if (!data) {
    return (
      <div className="page-body">
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)' }}>
            Loading analytics…
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <h2>Analytics</h2>
            <p style={{ color: 'var(--color-text-muted)' }}>{error}</p>
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <span style={{ color: 'var(--color-text-muted)', fontWeight: 400, fontSize: 14 }}>
            {periodLabels[period]}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['7d', '30d', '90d', '1y'] as const).map((p) => (
            <button
              key={p}
              className={`btn-sm ${period === p ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setPeriod(p)}
            >
              {periodLabels[p]}
            </button>
          ))}
        </div>
      </div>

      <div className="page-body">
        {error && <div className="error-banner">{error}</div>}

        {/* Key Metrics */}
        <div className="stats-grid">
          <StatCard
            title="Total Revenue"
            value={`$${data.total_revenue.toLocaleString()}`}
            change={data.revenue_change_30d}
            changeLabel={data.revenue_change_30d >= 0 ? '↑ vs last 30 days' : '↓ vs last 30 days'}
            icon="💰"
            color="var(--color-success)"
          />
          <StatCard
            title="Active Users"
            value={data.active_users.toLocaleString()}
            change={data.user_growth_30d}
            changeLabel={data.user_growth_30d >= 0 ? '↑ vs last 30 days' : '↓ vs last 30 days'}
            icon="👥"
            color="var(--color-primary)"
          />
          <StatCard
            title="Total Decks"
            value={data.total_decks.toLocaleString()}
            change={data.deck_growth_30d}
            changeLabel={data.deck_growth_30d >= 0 ? '↑ vs last 30 days' : '↓ vs last 30 days'}
            icon="🎴"
            color="var(--color-warning)"
          />
          <StatCard
            title="Avg. Cards/Deck"
            value={data.avg_cards_per_deck?.toFixed(1) ?? '-'}
            change={data.avg_cards_change_30d}
            changeLabel={data.avg_cards_change_30d >= 0 ? '↑ vs last 30 days' : '↓ vs last 30 days'}
            icon="🃏"
            color="var(--color-info)"
          />
        </div>

        {/* Top Cards */}
        <TopCards
          title="Top Performing Decks"
          items={data.top_decks || []}
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
          {/* Revenue Chart */}
          <div className="card">
            <h3 style={{ fontSize: 16, marginBottom: 16 }}>Revenue Trend</h3>
            <RevenueChart data={data.revenue_by_month || []} />
          </div>

          {/* User Growth Chart */}
          <div className="card">
            <h3 style={{ fontSize: 16, marginBottom: 16 }}>User Growth</h3>
            <UserGrowthChart data={data.users_by_month || []} />
          </div>
        </div>

        {/* Additional Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
          <TopCards
            title="Most Popular Categories"
            items={data.top_categories || []}
          />
          <TopCards
            title="Top Countries"
            items={data.top_countries || []}
          />
        </div>

        {/* Platform Health */}
        <div className="card" style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: 16, marginBottom: 16 }}>Platform Health</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>
                API Response Time (avg)
              </div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.api_response_time_ms?.toFixed(0)}ms
              </div>
              <div style={{ fontSize: 12, color: data.api_response_time_ms && data.api_response_time_ms < 200 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                {data.api_response_time_ms && data.api_response_time_ms < 200 ? '✓ Healthy' : '⚠ Elevated'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>
                Error Rate
              </div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.error_rate?.toFixed(2)}%
              </div>
              <div style={{ fontSize: 12, color: data.error_rate && data.error_rate < 1 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                {data.error_rate && data.error_rate < 1 ? '✓ Excellent' : '⚠ Monitor'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>
                Uptime (last 30d)
              </div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.uptime_percentage?.toFixed(1)}%
              </div>
              <div style={{ fontSize: 12, color: data.uptime_percentage && data.uptime_percentage > 99.9 ? 'var(--color-success)' : 'var(--color-warning)' }}>
                {data.uptime_percentage && data.uptime_percentage > 99.9 ? '✓ Excellent' : '⚠ Below target'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
