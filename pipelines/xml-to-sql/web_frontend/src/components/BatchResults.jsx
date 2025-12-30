import { Check, X } from 'lucide-react'
import { downloadBatchZip } from '../services/api'
import './BatchResults.css'

function BatchResults({ batchResult }) {
  if (!batchResult) {
    return (
      <div className="batch-results-container">
        <div className="card">
          <h2>Batch Conversion Results</h2>
          <p className="empty-state">No conversion results yet. Select files and click "Convert" to start.</p>
        </div>
      </div>
    )
  }

  const handleDownloadZip = async () => {
    if (!batchResult) return
    try {
      await downloadBatchZip(batchResult.batch_id)
    } catch (error) {
      alert(`Download failed: ${error.message}`)
    }
  }

  return (
    <div className="batch-results-container">
      <div className="card">
        <h2>Batch Conversion Results</h2>

        <div className="results-header">
          <div className="results-stats">
            <span className="stat success">
              <span className="stat-icon"><Check size={16} /></span>
              {batchResult.successful} successful
            </span>
            {batchResult.failed > 0 && (
              <span className="stat error">
                <span className="stat-icon"><X size={16} /></span>
                {batchResult.failed} failed
              </span>
            )}
          </div>

          {batchResult.successful > 0 && (
            <button className="download-zip-btn" onClick={handleDownloadZip}>
              Download All as ZIP
            </button>
          )}
        </div>

        <div className="results-list">
          {batchResult.results.map((result, index) => (
            <div
              key={index}
              className={`result-item ${result.status}`}
            >
              <div className="result-item-header">
                <span className={`result-status ${result.status}`}>
                  {result.status === 'success' ? <Check size={14} /> : <X size={14} />}
                </span>
                <span className="result-filename">{result.filename}</span>
              </div>
              {result.error_message && (
                <div className="result-error">{result.error_message}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default BatchResults

