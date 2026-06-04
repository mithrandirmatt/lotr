import { useEffect, useState } from 'react'
import { adminGetCardStats, getStorePricing } from '../api/client'
import type { CardStats, StorePricingResponse } from '../api/types'

export default function DashboardPage() {
  const [stats, setStats] = useState<CardStats | null>(null)
  const [pricing, setPricing] = useState<StorePricingResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([adminGetCardStats(), getStorePricing()])
      .then(([s, p]) => {
        setStats(s)
        setPricing(p)
      })
      .catch(() => setError('Failed to load dashboard data.'))
  }, [])

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
      </div>
      <div className="page-body">
        {error && <div className="error-banner">{error}</div>}

        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Total Cards</div>
            <div className="stat-value">{stats?.total_cards ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Ownerships</div>
            <div className="stat-value">{stats?.total_ownerships ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Purchases</div>
            <div className="stat-value">{stats?.total_purchases ?? '—'}</div>
          </div>
        </div>

        {pricing && (
          <div className="card" style={{ maxWidth: 420 }}>
            <h2 style={{ marginBottom: 14 }}>Store Pricing</h2>
            <p style={{ color: 'var(--color-text-muted)', marginBottom: 12, fontSize: 13 }}>
              Currency: <strong style={{ color: 'var(--color-primary)' }}>{pricing.currency}</strong>
              &nbsp;·&nbsp; 1 USD = {pricing.usd_per_tolkien} Tolkien
            </p>
            <table style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Price (Tolkiens)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(pricing.products).map(([key, price]) => (
                  <tr key={key}>
                    <td style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</td>
                    <td><span className="badge badge-gold">{price}T</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
