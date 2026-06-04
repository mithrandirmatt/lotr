import { useCallback, useEffect, useRef, useState } from 'react'
import {
  adminListUsers,
  adminAdjustTolkiens,
  adminToggleModerator,
  adminDeleteUser,
} from '../api/client'
import type { AdminUserSummary } from '../api/types'

// ── Delete confirmation modal ─────────────────────────────────────────────────

interface DeleteModalProps {
  user: AdminUserSummary
  onConfirm: () => Promise<void>
  onCancel: () => void
}

function DeleteModal({ user, onConfirm, onCancel }: DeleteModalProps) {
  const [confirmId, setConfirmId] = useState('')
  const [confirmUsername, setConfirmUsername] = useState('')
  const [confirmEmail, setConfirmEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const isValid =
    confirmId === user.id &&
    confirmUsername === user.username &&
    confirmEmail.toLowerCase() === user.email.toLowerCase()

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
        <h2 style={{ color: 'var(--color-danger)' }}>⚠ Delete User</h2>
        <p>
          This permanently deletes <strong>{user.username}</strong> and all their decks,
          collections, and purchases. This cannot be undone.
        </p>
        <p>Type the following to confirm:</p>

        {error && <div className="error-banner">{error}</div>}

        <div className="form-group">
          <label>User ID: <code style={{ color: 'var(--color-primary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{user.id}</code></label>
          <input value={confirmId} onChange={(e) => setConfirmId(e.target.value)} placeholder="Paste user ID" />
        </div>
        <div className="form-group">
          <label>Username: <code style={{ color: 'var(--color-primary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{user.username}</code></label>
          <input value={confirmUsername} onChange={(e) => setConfirmUsername(e.target.value)} placeholder="Type username" />
        </div>
        <div className="form-group">
          <label>Email: <code style={{ color: 'var(--color-primary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{user.email}</code></label>
          <input value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} placeholder="Type email" />
        </div>

        <div className="modal-actions">
          <button className="btn-ghost" onClick={onCancel} disabled={loading}>Cancel</button>
          <button
            className="btn-danger"
            disabled={!isValid || loading}
            onClick={handleDelete}
          >
            {loading ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tolkien adjustment inline form ────────────────────────────────────────────

interface TolkienAdjustProps {
  user: AdminUserSummary
  onDone: (updated: AdminUserSummary) => void
}

function TolkienAdjustInline({ user, onDone }: TolkienAdjustProps) {
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  async function handleSubmit() {
    const n = parseInt(amount, 10)
    if (!n || n === 0) { setError('Amount must be non-zero.'); return }
    setLoading(true)
    setError('')
    try {
      const updated = await adminAdjustTolkiens(user.id, { amount: n, reason: reason || undefined })
      onDone(updated)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220 }}>
      {error && <div className="error-banner" style={{ padding: '6px 10px', fontSize: 12 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          ref={inputRef}
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="+10 or -5"
          style={{ width: 90 }}
        />
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (optional)"
          style={{ width: 140 }}
        />
        <button className="btn-primary btn-sm" disabled={loading} onClick={handleSubmit}>
          {loading ? '…' : 'Apply'}
        </button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function UsersPage() {
  const [users, setUsers] = useState<AdminUserSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [adjustingId, setAdjustingId] = useState<string | null>(null)
  const [deletingUser, setDeletingUser] = useState<AdminUserSummary | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await adminListUsers(search || undefined, page, pageSize)
      setUsers(result.items)
      setTotal(result.total)
    } catch {
      setError('Failed to load users.')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { load() }, [load])

  function handleSearch() {
    setSearch(searchInput)
    setPage(1)
  }

  function updateUser(updated: AdminUserSummary) {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
    setAdjustingId(null)
    setSuccess(`Updated ${updated.username}.`)
    setTimeout(() => setSuccess(''), 3000)
  }

  async function handleToggleModerator(user: AdminUserSummary) {
    try {
      const updated = await adminToggleModerator(user.id)
      updateUser(updated)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to toggle moderator.')
    }
  }

  async function handleDeleteConfirmed(user: AdminUserSummary) {
    await adminDeleteUser(user.id, {
      confirm_user_id: user.id,
      confirm_username: user.username,
      confirm_email: user.email,
    })
    setDeletingUser(null)
    setSuccess(`User ${user.username} deleted.`)
    setTimeout(() => setSuccess(''), 3000)
    load()
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <div className="page-header">
        <h1>Users <span style={{ color: 'var(--color-text-muted)', fontWeight: 400, fontSize: 14 }}>({total})</span></h1>
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
            placeholder="Search by username or email…"
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
                <th>Username</th>
                <th>Email</th>
                <th>Status</th>
                <th>Role</th>
                <th>Tolkiens</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>Loading…</td></tr>
              )}
              {!loading && users.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>No users found.</td></tr>
              )}
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.username}</strong>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{user.id.slice(0, 8)}…</div>
                  </td>
                  <td>{user.email}</td>
                  <td>
                    <span className={`badge ${user.is_active ? 'badge-green' : 'badge-red'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    {user.is_admin
                      ? <span className="badge badge-gold">Admin</span>
                      : user.is_moderator
                        ? <span className="badge badge-yellow">Moderator</span>
                        : <span className="badge badge-gray">User</span>}
                  </td>
                  <td>
                    {adjustingId === user.id ? (
                      <TolkienAdjustInline
                        user={user}
                        onDone={updateUser}
                      />
                    ) : (
                      <span
                        className="badge badge-gold"
                        style={{ cursor: 'pointer' }}
                        title="Click to adjust"
                        onClick={() => setAdjustingId(user.id)}
                      >
                        {user.tolkien_balance}T
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="actions-cell">
                      {adjustingId !== user.id && (
                        <button
                          className="btn-ghost btn-sm"
                          onClick={() => setAdjustingId(user.id)}
                          title="Adjust Tolkien balance"
                        >
                          Tolkiens
                        </button>
                      )}
                      {adjustingId === user.id && (
                        <button
                          className="btn-ghost btn-sm"
                          onClick={() => setAdjustingId(null)}
                        >
                          Cancel
                        </button>
                      )}
                      {!user.is_admin && (
                        <button
                          className="btn-moderator btn-sm"
                          onClick={() => handleToggleModerator(user)}
                          title={user.is_moderator ? 'Revoke moderator' : 'Grant moderator'}
                        >
                          {user.is_moderator ? 'Revoke Mod' : 'Grant Mod'}
                        </button>
                      )}
                      <button
                        className="btn-danger btn-sm"
                        onClick={() => setDeletingUser(user)}
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

      {deletingUser && (
        <DeleteModal
          user={deletingUser}
          onConfirm={() => handleDeleteConfirmed(deletingUser)}
          onCancel={() => setDeletingUser(null)}
        />
      )}
    </>
  )
}
