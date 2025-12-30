import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Package, Upload, FileText, CheckCircle, XCircle, BarChart3, FolderOpen } from 'lucide-react'
import {
  uploadPackageMapping,
  getInstances,
  getInstanceDetails,
  deleteInstance,
  getStatistics
} from '../services/api'
import './PackageMappingUpload.css'

function PackageMappingUpload() {
  const [file, setFile] = useState(null)
  const [instanceName, setInstanceName] = useState('')
  const [instanceType, setInstanceType] = useState('ECC')
  const [autoDetectName, setAutoDetectName] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [instances, setInstances] = useState([])
  const [statistics, setStatistics] = useState(null)
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [showDetailsModal, setShowDetailsModal] = useState(false)

  // Load instances and statistics on mount
  useEffect(() => {
    loadInstances()
    loadStatistics()
  }, [])

  const loadInstances = async () => {
    try {
      const response = await getInstances()
      setInstances(response.instances || [])
    } catch (error) {
      console.error('Failed to load instances:', error)
    }
  }

  const loadStatistics = async () => {
    try {
      const stats = await getStatistics()
      setStatistics(stats)
    } catch (error) {
      console.error('Failed to load statistics:', error)
    }
  }

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const uploadedFile = acceptedFiles[0]
      setFile(uploadedFile)
      setUploadResult(null)

      // Auto-detect instance name from filename
      const match = uploadedFile.name.match(/HANA_CV_(\w+)\.xlsx?/i)
      if (match) {
        const detected = `${match[1]} (${instanceType})`
        setAutoDetectName(detected)
        setInstanceName('') // Clear manual input to show auto-detection
      } else {
        setAutoDetectName('')
      }
    }
  }, [instanceType])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    multiple: false,
  })

  const handleUpload = async () => {
    if (!file) return

    setLoading(true)
    setUploadResult(null)

    try {
      const result = await uploadPackageMapping(
        file,
        instanceName || autoDetectName,
        instanceType
      )

      setUploadResult({
        success: true,
        message: result.message,
        data: result
      })

      // Refresh instances list
      await loadInstances()
      await loadStatistics()

      // Clear form
      setFile(null)
      setInstanceName('')
      setAutoDetectName('')
    } catch (error) {
      setUploadResult({
        success: false,
        message: error.response?.data?.detail || error.message || 'Upload failed'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleViewDetails = async (instance) => {
    try {
      const details = await getInstanceDetails(instance.instance_id)
      setSelectedInstance(details)
      setShowDetailsModal(true)
    } catch (error) {
      alert(`Failed to load details: ${error.message}`)
    }
  }

  const handleDeleteInstance = async (instance) => {
    if (!confirm(`Delete instance "${instance.instance_name}" and all its ${instance.cv_count || 0} mappings?`)) {
      return
    }

    try {
      await deleteInstance(instance.instance_id)
      alert('Instance deleted successfully')
      await loadInstances()
      await loadStatistics()
    } catch (error) {
      alert(`Failed to delete instance: ${error.message}`)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="package-mapping-upload">
      <div className="upload-section card">
        <h2><Package size={24} style={{verticalAlign: 'middle', marginRight: '8px'}} />Package Mappings Management</h2>

        <div className="upload-form">
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'active' : ''}`}
          >
            <input {...getInputProps()} />
            {isDragActive ? (
              <p>Drop the Excel file here...</p>
            ) : (
              <div>
                <p><Upload size={16} style={{verticalAlign: 'middle', marginRight: '6px'}} />Drag & drop HANA package mapping Excel file here, or click to select</p>
                <p className="hint">
                  Expected format: HANA_CV_MBD.xlsx → Auto-detects as "MBD (ECC)"
                  <br />
                  Required columns: PACKAGE_ID, OBJECT_NAME
                </p>
              </div>
            )}
          </div>

          {file && (
            <div className="file-selected">
              <div className="file-info">
                <span className="file-name"><FileText size={16} style={{verticalAlign: 'middle', marginRight: '6px'}} />{file.name}</span>
                <span className="file-size">{(file.size / 1024).toFixed(2)} KB</span>
              </div>
              {autoDetectName && (
                <div className="auto-detect-info">
                  <CheckCircle size={16} style={{verticalAlign: 'middle', marginRight: '6px', color: 'var(--color-success)'}} />Auto-detected instance: <strong>{autoDetectName}</strong>
                </div>
              )}
            </div>
          )}

          <div className="form-fields">
            <div className="form-group">
              <label>Instance Name (optional):</label>
              <input
                type="text"
                value={instanceName}
                onChange={(e) => setInstanceName(e.target.value)}
                placeholder={autoDetectName || "e.g., MBD (ECC)"}
                disabled={loading}
              />
              <span className="hint">Leave empty to use auto-detected name</span>
            </div>

            <div className="form-group">
              <label>Instance Type:</label>
              <select
                value={instanceType}
                onChange={(e) => setInstanceType(e.target.value)}
                disabled={loading}
              >
                <option value="ECC">ECC</option>
                <option value="BW">BW</option>
                <option value="S4HANA">S/4HANA</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <button
            className="upload-btn"
            onClick={handleUpload}
            disabled={!file || loading}
          >
            {loading ? 'Uploading & Importing...' : 'Upload & Import'}
          </button>

          {uploadResult && (
            <div className={`upload-result ${uploadResult.success ? 'success' : 'error'}`}>
              <div className="result-icon">{uploadResult.success ? <CheckCircle size={20} /> : <XCircle size={20} />}</div>
              <div className="result-message">{uploadResult.message}</div>
              {uploadResult.success && uploadResult.data && (
                <div className="result-details">
                  <p>Instance: {uploadResult.data.instance_name}</p>
                  <p>CVs Imported: {uploadResult.data.cv_count}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="statistics-section card">
        <h2><BarChart3 size={24} style={{verticalAlign: 'middle', marginRight: '8px'}} />Overall Statistics</h2>
        {statistics ? (
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-value">{statistics.total_instances || 0}</div>
              <div className="stat-label">Instances</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{statistics.total_cvs || 0}</div>
              <div className="stat-label">Total CVs</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{statistics.unique_packages || 0}</div>
              <div className="stat-label">Unique Packages</div>
            </div>
          </div>
        ) : (
          <p>Loading statistics...</p>
        )}
      </div>

      <div className="instances-section card">
        <h2><FolderOpen size={24} style={{verticalAlign: 'middle', marginRight: '8px'}} />Current Instances</h2>
        {instances.length > 0 ? (
          <div className="instances-list">
            {instances.map((instance) => (
              <div key={instance.instance_id} className="instance-card">
                <div className="instance-header">
                  <h3>{instance.instance_name}</h3>
                  <span className="instance-type">{instance.instance_type || 'N/A'}</span>
                </div>
                <div className="instance-info">
                  <p>CVs: <strong>{instance.cv_count || 0}</strong></p>
                  <p>Last Updated: {formatDate(instance.updated_at)}</p>
                </div>
                <div className="instance-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => handleViewDetails(instance)}
                  >
                    View Details
                  </button>
                  <button
                    className="btn-danger"
                    onClick={() => handleDeleteInstance(instance)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-message">No instances yet. Upload an Excel file to get started.</p>
        )}
      </div>

      {showDetailsModal && selectedInstance && (
        <div className="modal-overlay" onClick={() => setShowDetailsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedInstance.instance_name} - Details</h2>
              <button className="modal-close" onClick={() => setShowDetailsModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="detail-section">
                <h3>Overview</h3>
                <p>Total CVs: <strong>{selectedInstance.cv_count}</strong></p>
                <p>Unique Packages: <strong>{selectedInstance.package_count}</strong></p>
                <p>Last Import: {formatDate(selectedInstance.updated_at)}</p>
              </div>

              {selectedInstance.top_packages && selectedInstance.top_packages.length > 0 && (
                <div className="detail-section">
                  <h3>Top Packages</h3>
                  <ul className="package-list">
                    {selectedInstance.top_packages.map((pkg, idx) => (
                      <li key={idx}>
                        <span className="package-name">{pkg.package}</span>
                        <span className="package-count">({pkg.cv_count} CVs)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedInstance.recent_cvs && selectedInstance.recent_cvs.length > 0 && (
                <div className="detail-section">
                  <h3>Recent CVs</h3>
                  <ul className="cv-list">
                    {selectedInstance.recent_cvs.slice(0, 10).map((cv, idx) => (
                      <li key={idx}>
                        <span className="cv-name">{cv.cv_name}</span>
                        <span className="cv-package">→ {cv.package_path}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn-primary" onClick={() => setShowDetailsModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PackageMappingUpload
