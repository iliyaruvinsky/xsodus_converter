import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'
import { convertSingleWithProgress } from '../services/api'
import './FileUpload.css'

function FileUpload({
  multiple = false,
  files,
  onFilesChange,
  config,
  onConfigChange,
  onConversionComplete,
  onProgressUpdate,
  loading,
  setLoading,
}) {
  const onDrop = useCallback((acceptedFiles) => {
    if (multiple) {
      onFilesChange([...files, ...acceptedFiles])
    } else {
      onFilesChange(acceptedFiles.slice(0, 1))
    }
  }, [files, multiple, onFilesChange])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/xml': ['.xml', '.XML'],
      'text/xml': ['.xml', '.XML'],
    },
    multiple,
  })

  const removeFile = (index) => {
    const newFiles = files.filter((_, i) => i !== index)
    onFilesChange(newFiles)
  }

  const handleConvert = async () => {
    if (files.length === 0) return

    setLoading(true)

    // Use regular API (SSE disabled for now due to async blocking issues)
    try {
      const { convertSingle } = await import('../services/api')
      const result = await convertSingle(files[0], config)
      onConversionComplete(result)
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message
      alert(`Conversion failed: ${errorDetail || 'Unknown error occurred'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="file-upload-container">
      <div className="card">
        <h2>Upload XML File</h2>
        
        <div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? 'active' : ''}`}
        >
          <input {...getInputProps()} />
          {isDragActive ? (
            <p>Drop the XML file here...</p>
          ) : (
            <div>
              <p><Upload size={16} style={{verticalAlign: 'middle', marginRight: '6px'}} />Drag & drop a SAP HANA calculation view XML file here, or click to select</p>
              <p className="hint">Supports .xml and .XML files (SAP HANA calculation views only)</p>
            </div>
          )}
        </div>

        {files.length > 0 && (
          <div className="file-list">
            <h3>Selected File:</h3>
            {files.map((file, index) => (
              <div key={index} className="file-item">
                <span className="file-name">{file.name}</span>
                <span className="file-size">
                  {(file.size / 1024).toFixed(2)} KB
                </span>
                <button
                  className="remove-btn"
                  onClick={() => removeFile(index)}
                  disabled={loading}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          className="convert-btn"
          onClick={handleConvert}
          disabled={files.length === 0 || loading}
        >
          {loading ? 'Converting...' : 'Convert to SQL'}
        </button>
      </div>
    </div>
  )
}

export default FileUpload

