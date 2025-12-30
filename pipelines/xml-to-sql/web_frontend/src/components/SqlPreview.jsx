import { useState } from 'react'
import { Check } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import { downloadSql, downloadAbap, generateAbap } from '../services/api'
import XmlViewer from './XmlViewer'
import ValidationResults from './ValidationResults'
import ConversionFlow from './ConversionFlow'
import ConversionProgress from './ConversionProgress'
import './SqlPreview.css'

function SqlPreview({ result, loading, progressStages, progressFilename }) {
  // Show progress if loading and we have stages
  if (loading && progressStages && progressStages.length > 0) {
    return (
      <div className="sql-preview-container">
        <div className="card">
          <ConversionProgress stages={progressStages} filename={progressFilename || 'file.xml'} />
        </div>
      </div>
    )
  }

  // Show nothing if no result yet
  if (!result) {
    return null
  }
  const [mainTab, setMainTab] = useState('sql') // 'sql', 'flow', 'validation', 'abap'
  const [viewMode, setViewMode] = useState('split') // 'split', 'tabs'
  const [activeTab, setActiveTab] = useState('xml') // 'xml' or 'sql' for tabs view
  const [abapContent, setAbapContent] = useState(result.abap_content || null)
  const [abapLoading, setAbapLoading] = useState(false)
  const [abapError, setAbapError] = useState(null)
  const [showLineNumbers, setShowLineNumbers] = useState(true) // Line numbers toggle
  const [abapMode, setAbapMode] = useState('pure') // 'pure' or 'exec_sql'

  const handleDownload = async () => {
    try {
      await downloadSql(result.id)
    } catch (error) {
      alert(`Download failed: ${error.message}`)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(result.sql_content)
    alert('SQL copied to clipboard!')
  }

  const handleDownloadAbap = async () => {
    try {
      await downloadAbap(result.id)
    } catch (error) {
      alert(`ABAP download failed: ${error.message}`)
    }
  }

  const handleCopyAbap = () => {
    navigator.clipboard.writeText(abapContent)
    alert('ABAP copied to clipboard!')
  }

  const handleGenerateAbap = async () => {
    setAbapLoading(true)
    setAbapError(null)
    try {
      const response = await generateAbap(result.id, abapMode)
      setAbapContent(response.abap_content)
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message
      setAbapError(errorMsg)
      alert(`ABAP generation failed: ${errorMsg}`)
    } finally {
      setAbapLoading(false)
    }
  }

  const hasXml = result.xml_content && result.xml_content.trim().length > 0
  const hasAbap = abapContent && abapContent.trim().length > 0

  return (
    <div className="sql-preview-container">
      <div className="card">
        <div className="sql-preview-header">
          <h2>Conversion Result</h2>
        </div>

        {/* Main Tab Navigation */}
        <div className="main-tabs-header">
          <button
            className={mainTab === 'sql' ? 'main-tab active' : 'main-tab'}
            onClick={() => setMainTab('sql')}
          >
            SQL{hasXml ? '/XML' : ''}
          </button>
          {/* Line Numbers Toggle */}
          <button
            className={`line-numbers-toggle ${showLineNumbers ? 'active' : ''}`}
            onClick={() => setShowLineNumbers(!showLineNumbers)}
            title={showLineNumbers ? 'Hide line numbers' : 'Show line numbers'}
            style={{ marginLeft: 'auto', fontSize: '0.8rem', padding: '4px 8px' }}
          >
            {showLineNumbers ? '# ON' : '# OFF'}
          </button>
          <button
            className={mainTab === 'abap' ? 'main-tab active' : 'main-tab'}
            onClick={() => setMainTab('abap')}
          >
            ABAP
            {hasAbap && <span className="tab-check"><Check size={14} /></span>}
          </button>
          {result.stages && result.stages.length > 0 && (
            <button
              className={mainTab === 'flow' ? 'main-tab active' : 'main-tab'}
              onClick={() => setMainTab('flow')}
            >
              Conversion Flow
            </button>
          )}
          <button
            className={mainTab === 'validation' ? 'main-tab active' : 'main-tab'}
            onClick={() => setMainTab('validation')}
          >
            Validation
            {result.validation && (
              <span className="tab-badge">
                {(result.validation.errors?.length || 0) + (result.validation.warnings?.length || 0) + (result.validation.info?.length || 0)}
              </span>
            )}
          </button>
        </div>

        {/* Tab Content */}
        <div className="main-tabs-content">
          {/* SQL/XML Tab */}
          {mainTab === 'sql' && (
            <div className="sql-tab-panel">
              {hasXml && (
                <div className="view-mode-selector">
                  <button
                    className={viewMode === 'split' ? 'active' : ''}
                    onClick={() => setViewMode('split')}
                    title="Side-by-side view"
                  >
                    Split
                  </button>
                  <button
                    className={viewMode === 'tabs' ? 'active' : ''}
                    onClick={() => setViewMode('tabs')}
                    title="Tabbed view"
                  >
                    Tabs
                  </button>
                </div>
              )}

              {result.metadata && (
                <div className="metadata">
                  <div className="metadata-item">
                    <span className="label">Scenario ID:</span>
                    <span className="value">{result.metadata.scenario_id || 'N/A'}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Nodes:</span>
                    <span className="value">{result.metadata.nodes_count}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Filters:</span>
                    <span className="value">{result.metadata.filters_count}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Calculated Attributes:</span>
                    <span className="value">{result.metadata.calculated_attributes_count}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Logical Model:</span>
                    <span className="value">{result.metadata.logical_model_present ? 'Yes' : 'No'}</span>
                  </div>
                </div>
              )}

              {result.corrections && result.corrections.corrections_applied && result.corrections.corrections_applied.length > 0 && (
                <div className="corrections">
                  <h3>Auto-Corrections Applied ({result.corrections.corrections_applied.length})</h3>
                  <div className="corrections-list">
                    {result.corrections.corrections_applied.map((correction, index) => (
                      <div key={index} className={`correction-item correction-${correction.confidence}`}>
                        <div className="correction-header">
                          <span className="correction-confidence">{correction.confidence.toUpperCase()}</span>
                          <span className="correction-code">{correction.issue_code}</span>
                          {correction.line_number && (
                            <span className="correction-line">Line {correction.line_number}</span>
                          )}
                        </div>
                        <div className="correction-description">{correction.description}</div>
                        <div className="correction-diff">
                          <span className="correction-original">- {correction.original_text}</span>
                          <span className="correction-corrected">+ {correction.corrected_text}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.warnings && result.warnings.length > 0 && !result.validation && (
                <div className="warnings">
                  <h3>Warnings</h3>
                  <ul>
                    {result.warnings.map((warning, index) => (
                      <li key={index}>{warning.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {hasXml && viewMode === 'split' && (
                <div className="split-view">
                  <div className="split-panel xml-panel">
                    <XmlViewer xmlContent={result.xml_content} filename={result.filename} embedded={true} />
                  </div>
                  <div className="split-panel sql-panel">
                    <div className="sql-panel-header">
                      <div className="sql-actions">
                        <button className="copy-btn" onClick={handleCopy}>
                          Copy SQL
                        </button>
                        <button className="download-btn" onClick={handleDownload}>
                          Download SQL
                        </button>
                      </div>
                    </div>
                    <div className="sql-content">
                      <SyntaxHighlighter
                        language="sql"
                        style={vscDarkPlus}
                        showLineNumbers={showLineNumbers}
                        customStyle={{
                          margin: 0,
                          borderRadius: '8px',
                          padding: '1rem',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          overflowWrap: 'break-word',
                        }}
                        wrapLines={true}
                        wrapLongLines={true}
                      >
                        {result.sql_content}
                      </SyntaxHighlighter>
                    </div>
                  </div>
                </div>
              )}

              {hasXml && viewMode === 'tabs' && (
                <div className="tabs-view">
                  <div className="tabs-header">
                    <button
                      className={activeTab === 'xml' ? 'tab active' : 'tab'}
                      onClick={() => setActiveTab('xml')}
                    >
                      XML
                    </button>
                    <button
                      className={activeTab === 'sql' ? 'tab active' : 'tab'}
                      onClick={() => setActiveTab('sql')}
                    >
                      SQL
                    </button>
                  </div>
                  <div className="tabs-content">
                    {activeTab === 'xml' && (
                      <XmlViewer xmlContent={result.xml_content} filename={result.filename} />
                    )}
                    {activeTab === 'sql' && (
                      <div className="sql-tab-content">
                        <div className="sql-tab-header">
                          <div className="sql-actions">
                            <button className="copy-btn" onClick={handleCopy}>
                              Copy SQL
                            </button>
                            <button className="download-btn" onClick={handleDownload}>
                              Download SQL
                            </button>
                          </div>
                        </div>
                        <div className="sql-content">
                          <SyntaxHighlighter
                            language="sql"
                            style={vscDarkPlus}
                            showLineNumbers={showLineNumbers}
                            customStyle={{
                              margin: 0,
                              borderRadius: '8px',
                              padding: '1rem',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              overflowWrap: 'break-word',
                            }}
                            wrapLines={true}
                            wrapLongLines={true}
                          >
                            {result.sql_content}
                          </SyntaxHighlighter>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!hasXml && (
                <div className="sql-only-view">
                  <div className="sql-panel-header">
                    <div className="sql-actions">
                      <button className="copy-btn" onClick={handleCopy}>
                        Copy SQL
                      </button>
                      <button className="download-btn" onClick={handleDownload}>
                        Download SQL
                      </button>
                    </div>
                  </div>
                  <div className="sql-content">
                    <SyntaxHighlighter
                      language="sql"
                      style={vscDarkPlus}
                      showLineNumbers={showLineNumbers}
                      customStyle={{
                        margin: 0,
                        borderRadius: '8px',
                        padding: '1rem',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                      }}
                      wrapLines={true}
                      wrapLongLines={true}
                    >
                      {result.sql_content}
                    </SyntaxHighlighter>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Conversion Flow Tab */}
          {mainTab === 'flow' && result.stages && result.stages.length > 0 && (
            <div className="flow-tab-panel">
              <ConversionFlow stages={result.stages} />
            </div>
          )}

          {/* Validation Tab */}
          {mainTab === 'validation' && (
            <div className="validation-tab-panel">
              <ValidationResults validation={result.validation} logs={result.validation_logs || []} />
            </div>
          )}

          {/* ABAP Tab */}
          {mainTab === 'abap' && (
            <div className="abap-tab-panel">
              {!hasAbap ? (
                // Show generate button when no ABAP content
                <div className="abap-generate-section">
                  <div className="abap-generate-info">
                    <h3>Generate ABAP Report</h3>
                    <p>
                      Create an ABAP Report program that can be run in SE38 transaction in SAP.
                      Select the appropriate mode based on your requirements:
                    </p>

                    {/* ABAP Mode Selection */}
                    <div className="abap-mode-selector" style={{ margin: '1rem 0', padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px' }}>
                      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>ABAP Generation Mode:</label>
                      <select
                        value={abapMode}
                        onChange={(e) => setAbapMode(e.target.value)}
                        style={{ padding: '0.5rem', borderRadius: '4px', width: '100%', maxWidth: '400px' }}
                      >
                        <option value="pure">Pure ABAP (Portable - Any SAP System)</option>
                        <option value="exec_sql">EXEC SQL (HANA Only)</option>
                      </select>
                    </div>

                    {/* Mode-specific instructions */}
                    {abapMode === 'pure' ? (
                      <div className="mode-instructions" style={{ backgroundColor: '#1a3a1a', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
                        <h4 style={{ color: '#4ade80', margin: '0 0 0.5rem 0' }}>Pure ABAP Mode (Recommended)</h4>
                        <ul className="abap-features" style={{ margin: '0.5rem 0' }}>
                          <li>Works on ANY SAP system (HANA, Oracle, SQL Server, MaxDB)</li>
                          <li>Uses native SELECT statements with FOR ALL ENTRIES</li>
                          <li>No EXEC SQL blocks - fully portable code</li>
                          <li>Exports to CSV via GUI_DOWNLOAD or Application Server</li>
                        </ul>
                        <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#2a1a1a', borderRadius: '4px', borderLeft: '3px solid #f87171' }}>
                          <strong style={{ color: '#f87171' }}>Limitation:</strong> Cannot process XMLs that reference other Calculation Views (_SYS_BIC.*). If your XML references CVs, use EXEC SQL mode instead.
                        </div>
                      </div>
                    ) : (
                      <div className="mode-instructions" style={{ backgroundColor: '#1a2a3a', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
                        <h4 style={{ color: '#60a5fa', margin: '0 0 0.5rem 0' }}>EXEC SQL Mode (HANA Only)</h4>
                        <ul className="abap-features" style={{ margin: '0.5rem 0' }}>
                          <li>Creates temporary view using the generated SQL</li>
                          <li>Uses EXEC SQL / ENDEXEC blocks</li>
                          <li>Can reference Calculation Views (_SYS_BIC.*)</li>
                          <li>Exports to CSV via GUI_DOWNLOAD or Application Server</li>
                        </ul>
                        <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#3a2a1a', borderRadius: '4px', borderLeft: '3px solid #fbbf24' }}>
                          <strong style={{ color: '#fbbf24' }}>Requirement:</strong> Only works on SAP systems with HANA database. Will NOT work on Oracle, SQL Server, or other databases.
                        </div>
                      </div>
                    )}
                  </div>
                  <button
                    className="generate-abap-btn"
                    onClick={handleGenerateAbap}
                    disabled={abapLoading}
                  >
                    {abapLoading ? 'Generating...' : `Generate ${abapMode === 'pure' ? 'Pure ABAP' : 'EXEC SQL ABAP'} Report`}
                  </button>
                  {abapError && (
                    <div className="abap-error">
                      Error: {abapError}
                    </div>
                  )}
                </div>
              ) : (
                // Show ABAP content when available
                <>
                  <div className="abap-panel-header">
                    <div className="abap-info">
                      <span className="abap-label">ABAP Report Program</span>
                      <span className="abap-program-name">Z_XDS_{result.scenario_id?.toUpperCase() || 'EXPORT'}</span>
                    </div>
                    <div className="abap-actions">
                      <button className="copy-btn" onClick={handleCopyAbap}>
                        Copy ABAP
                      </button>
                      <button className="download-btn" onClick={handleDownloadAbap}>
                        Download ABAP
                      </button>
                    </div>
                  </div>
                  <div className="abap-description">
                    <p>This ABAP Report can be copied to SE38 transaction in SAP. It creates a view, fetches data using native SQL cursor, and exports to CSV file.</p>
                  </div>
                  <div className="abap-content">
                    <SyntaxHighlighter
                      language="abap"
                      style={vscDarkPlus}
                      showLineNumbers={showLineNumbers}
                      customStyle={{
                        margin: 0,
                        borderRadius: '8px',
                        padding: '1rem',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                      }}
                      wrapLines={true}
                      wrapLongLines={true}
                    >
                      {abapContent}
                    </SyntaxHighlighter>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SqlPreview
