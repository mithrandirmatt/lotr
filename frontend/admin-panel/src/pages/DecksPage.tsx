import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  adminListDecks,
  adminUpdateDeck,
  adminDeleteDeck,
} from '../api/client'
import type { AdminDeckSummary, AdminDeckUpdate } from '../api/types'

// ── Add deck form ─────────────────────────────────────────────────────────────

interface AddDeckFormProps {
  onCreated: (deck: AdminDeckSummary) => void
}

function AddDeckForm({ onCreated }: AddDeckFormProps) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<AdminDeckUpdate>({
    user_id: '',
    name: '',
    description: '',
    is_featured: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set<K extends keyof AdminDeckUpdate>(key: K, value: AdminDeckUpdate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const deck = await adminUpdateDeck(form)
      onCreated(deck)
      setForm({
        user_id: '',
        name: '',
        description: '',
        is_featured: false,
      })
      setOpen(false)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create deck.')
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button className="btn-primary btn-sm" onClick={() => setOpen(true)}>
        + Add Deck
      </button>
    )
  }

  return (
    <div className="card" style={{ marginBottom: 20, maxWidth: 580 }}>
      <h3 style={{ marginBottom: 14 }}>New Deck</h3>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>User ID *</label>
          <input
            value={form.user_id}
            onChange={(e) => set('user_id', e.target.value)}
            required
            placeholder="Enter user ID"
          />
        </div>
        <div className="form-group">
          <label>Name *</label>
          <input
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
            placeholder="Deck name"
          />
        </div>
        <div className="form-group">
          <label>Description</label>
          <textarea
            value={form.description ?? ''}
            onChange={(e) => set('description', e.target.value || undefined)}
            rows={3}
            placeholder="Deck description"
          />
        </div>
        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={form.is_featured}
              onChange={(e) => set('is_featured', e.target.checked)}
            />
            {' '}Feature this deck
          </label>
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

// ── Delete deck modal ────────────────────────────────────────────────────────

interface DeleteModalProps {
  deck: AdminDeckSummary
  onConfirm: () => Promise<void>
  onCancel: () => void
}

function DeleteModal({ deck, onConfirm, onCancel }: DeleteModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setLoading(true)
    setError('')
    try {
      await onConfirm()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2 style={{ color: 'var(--color-danger)' }}>⚠ Delete Deck</h2>
        <p>
          This permanently deletes the deck <strong>{deck.name}</strong> and all its cards.
          This cannot be undone.
        </p>
        {error && <div className="error-banner">{error}</div>}
        <div className="modal-actions">
          <button className="btn-ghost" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button className="btn-danger" disabled={loading} onClick={handleDelete}>
            {loading ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────────

export default function DecksPage() {
  const [decks, setDecks] = useState<AdminDeckSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [deletingDeck, setDeletingDeck] = useState<AdminDeckSummary | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await adminListDecks(search || undefined, page, pageSize)
      setDecks(result.items)
      setTotal(result.total)
    } catch {
      setError('Failed to load decks.')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { load() }, [load])

  function handleSearch() {
    setSearch(searchInput)
    setPage(1)
  }

  function updateDeck(updated: AdminDeckSummary) {
    setDecks((prev) => prev.map((d) => (d.id === updated.id ? updated : d)))
    setSuccess(`Updated ${updated.name}.`)
    setTimeout(() => setSuccess(''), 3000)
  }

  async function handleDeleteConfirmed(deck: AdminDeckSummary) {
    await adminDeleteDeck(deck.id)
    setDeletingDeck(null)
    setSuccess(`Deck ${deck.name} deleted.`)
    setTimeout(() => setSuccess(''), 3000)
    load()
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <div className="page-header">
        <h1>Decks <span style={{ color: 'var(--color-text-muted)', fontWeight: 400, fontSize: 14 }}>({total})</span></h1>
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
            placeholder="Search by name or user…"
          />
          <button className="btn-primary btn-sm" onClick={handleSearch}>Search</button>
          {search && (
            <button className="btn-ghost btn-sm" onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}>
              Clear
            </button>
          )}
          <AddDeckForm onCreated={updateDeck} />
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>User</th>
                <th>Featured</th>
                <th>Card Count</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>Loading…</td></tr>
              )}
              {!loading && decks.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>No decks found.</td></tr>
              )}
              {decks.map((deck) => (
                <tr key={deck.id}>
                  <td>
                    <strong>{deck.name}</strong>
                    {deck.is_featured && (
                      <span className="badge badge-gold" style={{ marginLeft: 8, fontSize: 10 }}>Featured</span>
                    )}
                  </td>
                  <td>
                    <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                      {deck.user_id}
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${deck.is_featured ? 'badge-gold' : 'badge-gray'}`}>
                      {deck.is_featured ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {deck.card_count ?? '-'}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {new Date(deck.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="actions-cell">
                      <button
                        className="btn-danger btn-sm"
                        onClick={() => setDeletingDeck(deck)}
                      >
                        Delete
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

      {deletingDeck && (
        <DeleteModal
          deck={deletingDeck}
          onConfirm={() => handleDeleteConfirmed(deletingDeck)}
          onCancel={() => setDeletingDeck(null)}
        />
      )}
    </>
  )
}
