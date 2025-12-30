import { useState, useEffect } from 'react'
import {
  getHistory,
  getHistoryDetail,
  deleteHistory,
  deleteHistoryBulk,
  downloadSql,
} from '../services/api'
import SqlPreview from './SqlPreview'
import './HistoryPanel.css'

function HistoryPanel({ onClose }) {
  const [history, setHistory] = useState([])
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedIds, setSelectedIds] = useState([])
  const [errorModal, setErrorModal] = useState(null) // { id, message }
  const pageSize = 20

  useEffect(() => {
    loadHistory()
  }, [page])

  const loadHistory = async () => {
    setLoading(true)
    try {
      const data = await getHistory(page, pageSize)
      setHistory(data.entries)
      setTotal(data.total)
      const currentIds = new Set(data.entries.map((entry) => entry.id))
      setSelectedIds((prev) => prev.filter((id) => currentIds.has(id)))
    } catch (error) {
      alert(`Failed to load history: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleViewDetails = async (id) => {
    try {
      const detail = await getHistoryDetail(id)
      setSelectedEntry(detail)
    } catch (error) {
      alert(`Failed to load details: ${error.message}`)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this conversion?')) return

    try {
      await deleteHistory(id)
      if (selectedEntry && selectedEntry.id === id) {
        setSelectedEntry(null)
      }
      loadHistory()
    } catch (error) {
      alert(`Failed to delete: ${error.message}`)
    }
  }

  const toggleSelection = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleSelectAll = (checked) => {
    if (checked) {
      const ids = history.map((entry) => entry.id)
      setSelectedIds(ids)
    } else {
      setSelectedIds([])
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) return
    if (
      !confirm(
        `Delete ${selectedIds.length} selected ${
          selectedIds.length === 1 ? 'entry' : 'entries'
        }? This action cannot be undone.`
      )
    ) {
      return
    }

    try {
      await deleteHistoryBulk(selectedIds)
      setSelectedIds([])
      // Reload current page; adjust if page becomes empty
      if (history.length === selectedIds.length && page > 1) {
        setPage(page - 1)
      } else {
        loadHistory()
      }
    } catch (error) {
      alert(`Failed to delete selected entries: ${error.message}`)
    }
  }

  const handleDeleteAll = async () => {
    if (
      !confirm(
        'Delete all conversion history? This will permanently remove all records.'
      )
    ) {
      return
    }

    try {
      await deleteHistoryBulk()
      setSelectedIds([])
      setPage(1)
      loadHistory()
    } catch (error) {
      alert(`Failed to delete history: ${error.message}`)
    }
  }

  const handleDownload = async (id) => {
    try {
      await downloadSql(id)
    } catch (error) {
      alert(`Download failed: ${error.message}`)
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  if (selectedEntry) {
    return (
      <div className="history-panel-container">
        <div className="card">
          <div className="history-header">
            <button className="back-btn" onClick={() => setSelectedEntry(null)}>
              ← Back to List
            </button>
            <h2>Conversion Details</h2>
          </div>
          <SqlPreview result={selectedEntry} />
        </div>
      </div>
    )
  }

  return (
    <div className="history-panel-container">
      <div className="card">
        <div className="history-header">
          <h2>Conversion History</h2>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        {loading ? (
          <div className="loading">Loading...</div>
        ) : history.length === 0 ? (
          <div className="empty-state">No conversion history found.</div>
        ) : (
          <>
            <div className="history-toolbar">
              <label className="select-all-toggle">
                <input
                  type="checkbox"
                  checked={
                    history.length > 0 && selectedIds.length === history.length
                  }
                  onChange={(e) => handleSelectAll(e.target.checked)}
                />
                <span>Select All</span>
              </label>
              <div className="history-toolbar-actions">
                <button
                  className="toolbar-btn danger"
                  disabled={selectedIds.length === 0}
                  onClick={handleDeleteSelected}
                >
                  Delete Selected ({selectedIds.length})
                </button>
                <button
                  className="toolbar-btn"
                  disabled={total === 0}
                  onClick={handleDeleteAll}
                >
                  Delete All ({total})
                </button>
              </div>
            </div>

            <div className="history-list">
              {history.map((entry) => (
                <div
                  key={entry.id}
                  className={`history-item ${
                    selectedIds.includes(entry.id) ? 'selected' : ''
                  }`}
                >
                  <div className="history-item-select">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(entry.id)}
                      onChange={() => toggleSelection(entry.id)}
                    />
                  </div>
                  <div className="history-item-info">
                    <div className="history-item-name">{entry.filename}</div>
                    <div className="history-item-meta">
                      {entry.scenario_id && (
                        <span className="scenario-id">{entry.scenario_id}</span>
                      )}
                      <span className="date">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                      {entry.file_size && (
                        <span className="size">
                          {(entry.file_size / 1024).toFixed(2)} KB
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="history-item-status">
                    <span className={`status-badge ${entry.status}`}>
                      {entry.status}
                    </span>
                  </div>
                  <div className="history-item-actions">
                    {/* Slot 1: View or Error Log */}
                    {entry.status === 'success' ? (
                      <button
                        className="action-btn view"
                        onClick={() => handleViewDetails(entry.id)}
                      >
                        View
                      </button>
                    ) : entry.error_message ? (
                      <button
                        className="action-btn error-log"
                        onClick={() => setErrorModal({ id: entry.id, message: entry.error_message })}
                        title="View error details"
                      >
                        Error Log
                      </button>
                    ) : (
                      <div className="action-btn-placeholder"></div>
                    )}
                    
                    {/* Slot 2: Download or placeholder */}
                    {entry.status === 'success' ? (
                      <button
                        className="action-btn download"
                        onClick={() => handleDownload(entry.id)}
                      >
                        Download
                      </button>
                    ) : (
                      <div className="action-btn-placeholder"></div>
                    )}
                    
                    {/* Slot 3: Delete (always present) */}
                    <button
                      className="action-btn delete"
                      onClick={() => handleDelete(entry.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="page-btn"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                >
                  Previous
                </button>
                <span className="page-info">
                  Page {page} of {totalPages} ({total} total)
                </span>
                <button
                  className="page-btn"
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Error Modal */}
      {errorModal && (
        <div className="error-modal-overlay" onClick={() => setErrorModal(null)}>
          <div className="error-modal" onClick={(e) => e.stopPropagation()}>
            <div className="error-modal-header">
              <h3>Error Details</h3>
              <button className="error-modal-close" onClick={() => setErrorModal(null)}>
                ×
              </button>
            </div>
            <div className="error-modal-content">
              <pre className="error-message">{errorModal.message}</pre>
            </div>
            <div className="error-modal-footer">
              <button className="error-modal-btn" onClick={() => setErrorModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default HistoryPanel

