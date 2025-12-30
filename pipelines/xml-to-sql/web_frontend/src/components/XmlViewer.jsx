import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import './XmlViewer.css'

function XmlViewer({ xmlContent, filename, embedded = false }) {
  if (!xmlContent) {
    return (
      <div className={`xml-viewer-container ${embedded ? 'embedded' : ''}`}>
        {!embedded && (
          <div className="card">
            <div className="xml-empty">
              <p>No XML content available</p>
            </div>
          </div>
        )}
        {embedded && (
          <div className="xml-empty">
            <p>No XML content available</p>
          </div>
        )}
      </div>
    )
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(xmlContent)
    alert('XML copied to clipboard!')
  }

  const handleDownload = () => {
    const blob = new Blob([xmlContent], { type: 'application/xml' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename || 'conversion.xml'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  const content = (
    <>
      {!embedded && (
        <div className="xml-viewer-header">
          <div className="xml-actions">
            <button className="copy-btn" onClick={handleCopy}>
              Copy XML
            </button>
            <button className="download-btn" onClick={handleDownload}>
              Download XML
            </button>
          </div>
        </div>
      )}
      {embedded && (
        <div className="xml-viewer-header-embedded">
          <div className="xml-actions">
            <button className="copy-btn" onClick={handleCopy}>
              Copy XML
            </button>
            <button className="download-btn" onClick={handleDownload}>
              Download XML
            </button>
          </div>
        </div>
      )}

      <div className="xml-content">
        <SyntaxHighlighter
          language="xml"
          style={vscDarkPlus}
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
          {xmlContent}
        </SyntaxHighlighter>
      </div>
    </>
  )

  if (embedded) {
    return (
      <div className={`xml-viewer-container embedded`}>
        {content}
      </div>
    )
  }

  return (
    <div className="xml-viewer-container">
      <div className="card">
        {content}
      </div>
    </div>
  )
}

export default XmlViewer

