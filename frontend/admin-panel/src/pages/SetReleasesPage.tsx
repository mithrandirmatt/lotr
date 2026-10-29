import { useCallback, useEffect, useState } from 'react'
import {
  adminListSetReleases,
  adminActivateSetRelease,
  adminDeactivateSetRelease,
} from '../api/client'
import type { SetReleaseSummary } from '../api/types'

export default function SetReleasesPage() {
  const [sets, setSets] = useState<SetReleaseSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [togglingSetNumber, setTogglingSetNumber] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await adminListSetReleases()
      setSets(result.items)
    } catch {
      setError('Failed to load set releases.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleToggle(set: SetReleaseSummary) {
    if (set.is_locked_active) return
    setTogglingSetNumber(set.set_number)
    setError('')
    try {
      const updated = set.is_active
        ? await adminDeactivateSetRelease(set.set_number)
        : await adminActivateSetRelease(set.set_number)
      setSets((prev) => prev.map((s) => (s.set_number === updated.set_number ? updated : s)))
      setSuccess(`${updated.name} is now ${updated.is_active ? 'active' : 'inactive'}.`)
      setTimeout(() => setSuccess(''), 3000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update set release.')
    } finally {
      setTogglingSetNumber(null)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Set Releases</h1>
      </div>
      <div className="page-body">
        {error && <div className="error-banner">{error}</div>}
        {success && <div className="success-banner">{success}</div>}

        <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 12 }}>
          Toggle which sets are available in the storefront and deck builder. Fellowship
          (Set 1) is always active and cannot be disabled.
        </p>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Set</th>
                <th>Name</th>
                <th>Status</th>
                <th>Activated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>Loading…</td></tr>
              )}
              {!loading && sets.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 24 }}>No sets found.</td></tr>
              )}
              {sets.map((set) => (
                <tr key={set.set_number}>
                  <td>{set.set_number}</td>
                  <td><strong>{set.name}</strong></td>
                  <td>
                    <span className={`badge ${set.is_active ? 'badge-green' : 'badge-gray'}`}>
                      {set.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {set.is_locked_active && (
                      <span className="badge badge-gold" style={{ marginLeft: 6 }}>Locked</span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {set.activated_at ? new Date(set.activated_at).toLocaleDateString() : '—'}
                  </td>
                  <td>
                    <label className="checkbox-label" title={set.is_locked_active ? 'Fellowship cannot be deactivated' : undefined}>
                      <input
                        type="checkbox"
                        checked={set.is_active}
                        disabled={set.is_locked_active || togglingSetNumber === set.set_number}
                        onChange={() => handleToggle(set)}
                      />
                      {togglingSetNumber === set.set_number ? '…' : set.is_active ? 'Enabled' : 'Disabled'}
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
