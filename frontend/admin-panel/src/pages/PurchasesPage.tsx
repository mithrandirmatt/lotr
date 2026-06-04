import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  adminListPurchases,
  adminGetPurchaseDetails,
} from '../api/client'
import type { AdminPurchaseSummary, AdminPurchaseDetails } from '../api/types'

// ── Purchase details modal ────────────────────────────────────────────────────────

interface PurchaseDetailsModalProps {
  purchase: AdminPurchaseDetails
  onClose: () => void
}

function PurchaseDetailsModal({ purchase, onClose }: PurchaseDetailsModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadDetails() {
    setLoading(true)
    setError('')
    try {
      const details = await adminGetPurchaseDetails(purchase.id)
      // Update the parent purchase with full details
      window.__ADMIN_PURCHASE_DETAILS__ = details
    } catch {
      setError('Failed to load purchase details.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDetails() }, [])

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 720 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2>Purchase Details</h2>
          <button className="btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="purchase-details">
          <div className="purchase-header">
            <div>
              <div style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>Order ID</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{purchase.order_id}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>Total</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-success)' }}>
                ${purchase.total_amount.toFixed(2)}
              </div>
            </div>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Status:</span>
            <span className={`badge ${purchase.status === 'completed' ? 'badge-success' : 'badge-warning'}`}>
              {purchase.status}
            </span>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Customer:</span>
            <span>{purchase.customer_name}</span>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Email:</span>
            <span>{purchase.customer_email}</span>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Date:</span>
            <span>{new Date(purchase.created_at).toLocaleString()}</span>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Payment Method:</span>
            <span>{purchase.payment_method}</span>
          </div>

          <div className="purchase-row">
            <span style={{ width: 100, color: 'var(--color-text-muted)' }}>Items:</span>
            <span>{purchase.items?.length ?? 0} item(s)</span>
          </div>

          {purchase.items && purchase.items.length > 0 && (
            <div className="purchase-items">
              {purchase.items.map((item, idx) => (
                <div key={idx} className="purchase-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>
                      <strong>{item.name}</strong>
                      {item.quantity > 1 && (
                        <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>
                          {' × '}{item.quantity}
                        </span>
                      )}
                    </span>
                    <span style={{ fontWeight: 600 }}>${item.unit_price.toFixed(2)}</span>
                  </div>
                  {item.description && (
                    <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>
                      {item.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {purchase.notes && (
            <div className="purchase-notes">
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>
                <strong>Notes:</strong>
              </div>
              <div style={{ fontSize: 13, padding: 12, backgroundColor: 'var(--color-background-secondary)', borderRadius: 8 }}>
                {purchase.notes}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────────

export default function PurchasesPage() {
  const [purchases, setPurchases] = useState<AdminPurchaseSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [viewingPurchase, setViewingPurchase] = useState<AdminPurchaseDetails | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await adminListPurchases(search || undefined, statusFilter, page, pageSize)
      setPurchases(result.items)
      setTotal(result.total)
    } catch {
      setError('Failed to load purchases.')
    } finally {
      setLoading(false)
    }
  }, [search, statusFilter, page])

  useEffect(() => { load() }, [load])

  function handleSearch() {
    setSearch(searchInput)
    setPage(1)
  }

  function handleStatusChange(newStatus: string) {
    setStatusFilter(newStatus)
    setPage(1)
  }

  function openPurchase(purchase: AdminPurchaseSummary) {
    setViewingPurchase(purchase)
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <div className="page-header">
        <h1>Purchases <span style={{ color: 'var(--color-text-muted)', fontWeight: 400, fontSize: 14 }}>({total})</span></h1>
      </div>
      <div className="page-body">
        {error && <div className="error-banner">{error}</div>}
        {success && <div className="success-banner">{success}</div>}

        <div className="toolbar">
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search by order ID, email, or customer…"
          />
          <button className="btn-primary btn-sm" onClick={handleSearch}>Search</button>
          {search && (
            <button className="btn-ghost btn-sm" onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}>
              Clear
            </button>
          )}
        </div>

        <div className="filters">
          <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Filter by status:</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className={`btn-sm ${!statusFilter ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleStatusChange('')}
            >
              All
            </button>
            <button
              className={`btn-sm ${statusFilter === 'completed' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleStatusChange('completed')}
            >
              Completed
            </button>
            <button
              className={`btn-sm ${statusFilter === 'pending' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleStatusChange('pending')}
            >
              Pending
            </button>
            <button
              className={`btn-sm ${statusFilter === 'failed' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleStatusChange('failed')}
            >
              Failed
            </button>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date</th>
                <th>Items</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>Loading…</td></tr>
              )}
              {!loading && purchases.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>No purchases found.</td></tr>
              )}
              {purchases.map((purchase) => (
                <tr key={purchase.id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    <button
                      className="btn-link"
                      onClick={() => openPurchase(purchase)}
                      style={{ padding: 0, background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      {purchase.order_id}
                    </button>
                  </td>
                  <td>
                    <div style={{ fontSize: 13 }}>
                      <strong>{purchase.customer_name}</strong>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                      {purchase.customer_email}
                    </div>
                  </td>
                  <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    ${purchase.total_amount.toFixed(2)}
                  </td>
                  <td>
                    <span className={`badge ${
                      purchase.status === 'completed' ? 'badge-success' :
                      purchase.status === 'pending' ? 'badge-warning' :
                      'badge-danger'
                    }`}>
                      {purchase.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {new Date(purchase.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {purchase.items?.length ?? 0}
                  </td>
                  <td>
                    <div className="actions-cell">
                      <button
                        className="btn-primary btn-sm"
                        onClick={() => openPurchase(purchase)}
                      >
                        View Details
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button
            className="btn-ghost btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Prev
          </button>
          <span>Page {page} of {totalPages}</span>
          <button
            className="btn-ghost btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      </div>

      {viewingPurchase && (
        <PurchaseDetailsModal
          purchase={viewingPurchase}
          onClose={() => setViewingPurchase(null)}
        />
      )}
    </>
  )
}
