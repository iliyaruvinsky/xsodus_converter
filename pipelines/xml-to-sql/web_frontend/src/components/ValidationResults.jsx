import { useState, useMemo } from 'react'
import { XCircle, AlertTriangle, Info, Check, X } from 'lucide-react'
import './ValidationResults.css'

function ValidationResults({ validation, logs = [] }) {
  const [filter, setFilter] = useState('all') // 'all', 'error', 'warning', 'info'
  const [sortBy, setSortBy] = useState('severity') // 'severity', 'code', 'message'
  const [showLogs, setShowLogs] = useState(false)

  if (!validation) {
    return null
  }

  const { errors = [], warnings = [], info = [] } = validation

  // Combine all issues with their severity
  const allIssues = [
    ...errors.map(issue => ({ ...issue, severity: 'error' })),
    ...warnings.map(issue => ({ ...issue, severity: 'warning' })),
    ...info.map(issue => ({ ...issue, severity: 'info' })),
  ]

  // Filter issues
  const filteredIssues = useMemo(() => {
    let filtered = allIssues
    if (filter !== 'all') {
      filtered = filtered.filter(issue => issue.severity === filter)
    }
    return filtered
  }, [allIssues, filter])

  // Sort issues
  const sortedIssues = useMemo(() => {
    const sorted = [...filteredIssues]
    if (sortBy === 'severity') {
      const severityOrder = { error: 0, warning: 1, info: 2 }
      sorted.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
    } else if (sortBy === 'code') {
      sorted.sort((a, b) => (a.code || '').localeCompare(b.code || ''))
    } else if (sortBy === 'message') {
      sorted.sort((a, b) => (a.message || '').localeCompare(b.message || ''))
    }
    return sorted
  }, [filteredIssues, sortBy])

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'error':
        return <XCircle size={16} />
      case 'warning':
        return <AlertTriangle size={16} />
      case 'info':
        return <Info size={16} />
      default:
        return '•'
    }
  }

  const getSeverityClass = (severity) => {
    return `validation-issue validation-issue-${severity}`
  }

  if (allIssues.length === 0) {
    return (
      <div className="validation-results">
        <div className="validation-header">
          <h3>Validation Results</h3>
          <div className="validation-summary">
            <span className="validation-status validation-status-success">
              <Check size={16} style={{verticalAlign: 'middle', marginRight: '4px'}} />All checks passed
            </span>
            {logs.length > 0 && (
              <button
                className="validation-log-btn"
                onClick={() => setShowLogs(true)}
              >
                Validation Logs
              </button>
            )}
          </div>
        </div>
        {showLogs && logs.length > 0 && (
          <div className="validation-log-overlay" onClick={() => setShowLogs(false)}>
            <div
              className="validation-log-popover"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="validation-log-header">
                <h4>Validation Logs</h4>
                <button
                  className="validation-log-close"
                  onClick={() => setShowLogs(false)}
                >
                  ×
                </button>
              </div>
              <div className="validation-log-body">
                {logs.map((entry, index) => (
                  <div key={index} className="validation-log-entry">
                    {entry}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="validation-results">
      <div className="validation-header">
        <h3>Validation Results</h3>
        <div className="validation-summary">
          {validation.is_valid ? (
            <span className="validation-status validation-status-success">
              <Check size={16} style={{verticalAlign: 'middle', marginRight: '4px'}} />Valid ({allIssues.length} {allIssues.length === 1 ? 'issue' : 'issues'})
            </span>
          ) : (
            <span className="validation-status validation-status-error">
              <X size={16} style={{verticalAlign: 'middle', marginRight: '4px'}} />Invalid ({errors.length} {errors.length === 1 ? 'error' : 'errors'})
            </span>
          )}
          {logs.length > 0 && (
            <button
              className="validation-log-btn"
              onClick={() => setShowLogs(true)}
            >
              Validation Logs
            </button>
          )}
        </div>
      </div>

      <div className="validation-controls">
        <div className="validation-filters">
          <label>Filter:</label>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All ({allIssues.length})</option>
            <option value="error">Errors ({errors.length})</option>
            <option value="warning">Warnings ({warnings.length})</option>
            <option value="info">Info ({info.length})</option>
          </select>
        </div>

        <div className="validation-sort">
          <label>Sort by:</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="severity">Severity</option>
            <option value="code">Code</option>
            <option value="message">Message</option>
          </select>
        </div>
      </div>

      <div className="validation-issues-list">
        {sortedIssues.length === 0 ? (
          <div className="validation-empty">
            No issues match the current filter.
          </div>
        ) : (
          sortedIssues.map((issue, index) => (
            <div key={index} className={getSeverityClass(issue.severity)}>
              <div className="validation-issue-header">
                <span className="validation-issue-icon">
                  {getSeverityIcon(issue.severity)}
                </span>
                <span className="validation-issue-code">{issue.code}</span>
                {issue.line_number && (
                  <span className="validation-issue-line">
                    Line {issue.line_number}
                  </span>
                )}
              </div>
              <div className="validation-issue-message">{issue.message}</div>
            </div>
          ))
        )}
      </div>

      {showLogs && (
        <div className="validation-log-overlay" onClick={() => setShowLogs(false)}>
          <div
            className="validation-log-popover"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="validation-log-header">
              <h4>Validation Logs</h4>
              <button
                className="validation-log-close"
                onClick={() => setShowLogs(false)}
              >
                ×
              </button>
            </div>
            <div className="validation-log-body">
              {logs.map((entry, index) => (
                <div key={index} className="validation-log-entry">
                  {entry}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ValidationResults

