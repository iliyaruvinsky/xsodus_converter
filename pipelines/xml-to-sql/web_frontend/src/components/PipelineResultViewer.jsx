import { useState, useMemo } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism'
import './PipelineResultViewer.css'

// Map output types to syntax highlighter languages
const LANGUAGE_MAP = {
  sql: 'sql',
  abap: 'abap',
  cds: 'sql',  // CDS is similar to SQL
  json: 'json',
  ir: 'json',
  config: 'json',
}

// Map output types to file extensions
const EXTENSION_MAP = {
  sql: '.sql',
  abap: '.abap',
  cds: '.cds',
  json: '.json',
  ir: '.json',
  config: '.json',
}

function PipelineResultViewer({ results, filename }) {
  const [activeTab, setActiveTab] = useState(null)
  const [copied, setCopied] = useState(false)

  // Get displayable stages (exclude config stages)
  const displayStages = useMemo(() => {
    if (!results?.stages) return []
    return results.stages.filter(stage =>
      stage.output_type !== 'config' && stage.content
    )
  }, [results])

  // Set default active tab when results change
  useMemo(() => {
    if (displayStages.length > 0 && !activeTab) {
      setActiveTab(displayStages[0].block_id)
    }
  }, [displayStages])

  // Get active stage
  const activeStage = useMemo(() => {
    return displayStages.find(s => s.block_id === activeTab)
  }, [displayStages, activeTab])

  // Copy to clipboard
  const handleCopy = async () => {
    if (activeStage?.content) {
      try {
        await navigator.clipboard.writeText(activeStage.content)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error('Failed to copy:', err)
      }
    }
  }

  // Download content
  const handleDownload = () => {
    if (activeStage?.content) {
      const extension = EXTENSION_MAP[activeStage.output_type] || '.txt'
      const basename = filename?.replace(/\.[^/.]+$/, '') || 'output'
      const downloadName = `${basename}_${activeStage.block_name.replace(/\s+/g, '_')}${extension}`

      const blob = new Blob([activeStage.content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = downloadName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  }

  if (!results) {
    return (
      <div className="result-viewer-empty">
        <div className="empty-icon">[?]</div>
        <p>Execute a pipeline to see results</p>
      </div>
    )
  }

  return (
    <div className="result-viewer">
      {/* Summary Header */}
      <div className={`result-summary ${results.success ? 'success' : 'error'}`}>
        <div className="summary-status">
          <span className="status-icon">{results.success ? '[OK]' : '[!]'}</span>
          <span className="status-text">
            {results.success ? 'Pipeline Completed' : 'Pipeline Failed'}
          </span>
        </div>
        <div className="summary-stats">
          <span className="stat">
            <strong>{displayStages.length}</strong> outputs
          </span>
          <span className="stat">
            <strong>{results.total_time_ms || 0}</strong>ms total
          </span>
        </div>
      </div>

      {/* Error Display */}
      {!results.success && results.stages && (
        <div className="result-errors">
          {results.stages.filter(s => !s.success).map((stage, i) => (
            <div key={i} className="error-item">
              <strong>{stage.block_name}:</strong>
              <ul>
                {stage.errors?.map((err, j) => (
                  <li key={j}>{err}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      {displayStages.length > 0 && (
        <>
          <div className="result-tabs">
            {displayStages.map(stage => (
              <button
                key={stage.block_id}
                className={`tab ${activeTab === stage.block_id ? 'active' : ''} ${stage.success ? '' : 'error'}`}
                onClick={() => setActiveTab(stage.block_id)}
              >
                <span className="tab-name">{stage.block_name}</span>
                <span className="tab-type">{stage.output_type.toUpperCase()}</span>
                <span className="tab-time">{stage.execution_time_ms}ms</span>
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeStage && (
            <div className="result-content">
              {/* Toolbar */}
              <div className="content-toolbar">
                <div className="toolbar-info">
                  <span className="info-label">Output Type:</span>
                  <span className="info-value">{activeStage.output_type.toUpperCase()}</span>
                  <span className="info-label">Size:</span>
                  <span className="info-value">{(activeStage.content?.length || 0).toLocaleString()} chars</span>
                </div>
                <div className="toolbar-actions">
                  <button
                    className={`action-btn ${copied ? 'copied' : ''}`}
                    onClick={handleCopy}
                  >
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                  <button className="action-btn" onClick={handleDownload}>
                    Download
                  </button>
                </div>
              </div>

              {/* Warnings */}
              {activeStage.warnings?.length > 0 && (
                <div className="content-warnings">
                  <strong>Warnings:</strong>
                  <ul>
                    {activeStage.warnings.map((warn, i) => (
                      <li key={i}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Code Display */}
              <div className="content-code">
                <SyntaxHighlighter
                  language={LANGUAGE_MAP[activeStage.output_type] || 'text'}
                  style={tomorrow}
                  showLineNumbers={true}
                  wrapLines={true}
                  customStyle={{
                    margin: 0,
                    borderRadius: 0,
                    fontSize: '13px',
                    maxHeight: '500px',
                  }}
                >
                  {activeStage.content || ''}
                </SyntaxHighlighter>
              </div>
            </div>
          )}
        </>
      )}

      {/* All Stages Overview */}
      <div className="result-overview">
        <h4>Execution Timeline</h4>
        <div className="timeline">
          {results.stages?.map((stage, i) => (
            <div
              key={i}
              className={`timeline-item ${stage.success ? 'success' : 'error'}`}
            >
              <div className="timeline-marker">
                {stage.success ? '[OK]' : '[!]'}
              </div>
              <div className="timeline-content">
                <div className="timeline-header">
                  <span className="timeline-name">{stage.block_name}</span>
                  <span className="timeline-time">{stage.execution_time_ms}ms</span>
                </div>
                <div className="timeline-type">
                  Output: {stage.output_type}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default PipelineResultViewer
