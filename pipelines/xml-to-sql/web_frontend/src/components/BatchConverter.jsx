import { useDropzone } from 'react-dropzone'
import ConfigForm from './ConfigForm'
import { convertBatch } from '../services/api'
import './BatchConverter.css'

function BatchConverter({ files, onFilesChange, config, onConfigChange, onConversionComplete, loading, setLoading }) {

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => {
      onFilesChange([...files, ...acceptedFiles])
    },
    accept: {
      'application/xml': ['.xml', '.XML'],
      'text/xml': ['.xml', '.XML'],
    },
    multiple: true,
  })

  const removeFile = (index) => {
    const newFiles = files.filter((_, i) => i !== index)
    onFilesChange(newFiles)
  }

  const handleConvert = async () => {
    if (files.length === 0) return

    setLoading(true)
    if (onConversionComplete) {
      onConversionComplete(null)
    }
    try {
      const result = await convertBatch(files, config)
      if (onConversionComplete) {
        onConversionComplete(result)
      }
    } catch (error) {
      alert(`Batch conversion failed: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }


  return (
    <div className="batch-converter-container">
      <div className="card">
        <h2>Batch Conversion</h2>

        <div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? 'active' : ''}`}
        >
          <input {...getInputProps()} />
          {isDragActive ? (
            <p>Drop XML files here...</p>
          ) : (
            <div>
              <p>Drag & drop XML files here, or click to select</p>
              <p className="hint">Supports multiple .xml and .XML files</p>
            </div>
          )}
        </div>

        {files.length > 0 && (
          <>
            <button
              className="convert-btn convert-btn-top"
              onClick={handleConvert}
              disabled={files.length === 0 || loading}
            >
              {loading ? 'Converting...' : `Convert ${files.length} File${files.length !== 1 ? 's' : ''}`}
            </button>

            <div className="file-list">
              <h3>Selected Files ({files.length}):</h3>
              <div className="files-grid">
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
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default BatchConverter

