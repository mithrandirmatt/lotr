import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { listCards, createCard, adminRemoveCard } from '../api/client'
import type { CardResponse, CardCreate, Rarity } from '../api/types'

const RARITIES: Rarity[] = ['common', 'uncommon', 'rare', 'epic', 'legendary']

const RARITY_BADGE: Record<Rarity, string> = {
  common: 'badge-gray',
  uncommon: 'badge-green',
  rare: 'badge-gold',
  epic: 'badge-yellow',
  legendary: 'badge-red',
}

// ── Add card form ─────────────────────────────────────────────────────────────

interface AddCardFormProps {
  onCreated: (card: CardResponse) => void
}

function AddCardForm({ onCreated }: AddCardFormProps) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<CardCreate>({ name: '', cost: 0, rarity: 'common' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set<K extends keyof CardCreate>(key: K, value: CardCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const card = await createCard(form)
      onCreated(card)
      setForm({ name: '', cost: 0, rarity: 'common' })
      setOpen(false)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create card.')
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button className="btn-primary btn-sm" onClick={() => setOpen(true)}>
        + Add Card
      </button>
    )
  }

  return (
    <div className="card" style={{ marginBottom: 20, maxWidth: 580 }}>
      <h3 style={{ marginBottom: 14 }}>New Card</h3>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label>Name *</label>
            <input
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>Cost</label>
            <input
              type="number"
              min={0}
              value={form.cost}
              onChange={(e) => set('cost', parseInt(e.target.value) || 0)}
            />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Rarity</label>
            <select value={form.rarity} onChange={(e) => set('rarity', e.target.value as Rarity)}>
              {RARITIES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Image URL</label>
            <input
              value={form.image_url ?? ''}
              onChange={(e) => set('image_url', e.target.value || undefined)}
              placeholder="https://…"
            />
          </div>
        </div>
        <div className="form-group">
          <label>Description</label>
          <textarea
            value={form.description ?? ''}
            onChange={(e) => set('description', e.target.value || undefined)}
            rows={2}
            style={{ resize: 'vertical' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="submit" className="btn-primary btn-sm" disabled={loading}>
            {loading ? 'Creating…' : 'Create'}
          </button>
          <button type="button" className="btn-ghost btn-sm" onClick={() => setOpen(false)}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CardsPage() {
  const [cards, setCards] = useState<CardResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await listCards(page, pageSize, search || undefined)
      setCards(result.items)
      setTotal(result.total)
    } catch {
      setError('Failed to load cards.')
    } finally {
      setLoading(false)
    }
  }, [page, search])

  useEffect(() => { load() }, [load])

  function handleSearch() {
    setSearch(searchInput)
    setPage(1)
  }

  function handleCreated(card: CardResponse) {
    setSuccess(`Card "${card.name}" created.`)
    setTimeout(() => setSuccess(''), 3000)
    load()
  }

  async function handleRemove(card: CardResponse) {
    if (!window.confirm(`Soft-delete "${card.name}"? It will no longer be available in the store.`)) return
    try {
      await adminRemoveCard(card.id)
      setSuccess(`"${card.name}" removed from store.`)
      setTimeout(() => setSuccess(''), 3000)
      load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to remove card.')
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <div className="page-header">
        <h1>Cards <span style={{ color: 'var(--color-text-muted)', fontWeight: 400, fontSize: 14 }}>({total})</span></h1>
      </div>
      <div className="page-body">
        {error && <div className="error-banner">{error}</div>}
        {success && <div className="success-banner">{success}</div>}

        <AddCardForm onCreated={handleCreated} />

        <div className="toolbar">
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search cards…"
          />
          <button className="btn-primary btn-sm" onClick={handleSearch}>Search</button>
          {search && (
            <button className="btn-ghost btn-sm" onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}>
              Clear
            </button>
          )}
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Rarity</th>
                <th>Cost</th>
                <th>Status</th>
                <th>Description</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>Loading…</td></tr>
              )}
              {!loading && cards.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>No cards found.</td></tr>
              )}
              {cards.map((card) => (
                <tr key={card.id} style={{ opacity: card.is_active === false ? 0.5 : 1 }}>
                  <td>
                    <strong>{card.name}</strong>
                    {card.image_url && (
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Has image</div>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${RARITY_BADGE[card.rarity]}`}>
                      {card.rarity}
                    </span>
                  </td>
                  <td>{card.cost}</td>
                  <td>
                    {card.is_active === false
                      ? <span className="badge badge-red">Removed</span>
                      : <span className="badge badge-green">Active</span>}
                  </td>
                  <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    {card.description ?? '—'}
                  </td>
                  <td>
                    {card.is_active !== false && (
                      <button
                        className="btn-danger btn-sm"
                        onClick={() => handleRemove(card)}
                        title="Soft-delete this card"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button className="btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </button>
          <span>Page {page} of {totalPages}</span>
          <button className="btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next →
          </button>
        </div>
      </div>
    </>
  )
}
