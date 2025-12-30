import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Single file conversion
export const convertSingle = async (file, config) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('config_json', JSON.stringify(config))

  const response = await api.post('/convert/single', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

// Single file conversion with SSE progress streaming
export const convertSingleWithProgress = (file, config, onProgress, onComplete, onError) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('config_json', JSON.stringify(config))

  // Use fetch API for SSE (EventSource doesn't support POST with body)
  const baseUrl = import.meta.env.VITE_API_URL || ''
  fetch(`${baseUrl}/api/convert/single/stream`, {
    method: 'POST',
    body: formData,
  })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // Read the stream
      const readStream = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            return
          }

          // Decode the chunk
          buffer += decoder.decode(value, { stream: true })

          // Process complete SSE messages
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || '' // Keep the incomplete message in buffer

          lines.forEach(line => {
            if (line.trim()) {
              try {
                // Parse SSE message
                const eventMatch = line.match(/^event: (.+)/)
                const dataMatch = line.match(/^data: (.+)/)

                if (eventMatch && dataMatch) {
                  const event = eventMatch[1]
                  const data = JSON.parse(dataMatch[1])

                  // Handle different event types
                  switch (event) {
                    case 'start':
                      console.log('Conversion started:', data.filename)
                      break
                    case 'stage_update':
                      if (onProgress) {
                        onProgress(data)
                      }
                      break
                    case 'complete':
                      if (onComplete) {
                        onComplete(data)
                      }
                      return
                    case 'error':
                      if (onError) {
                        onError(data.error)
                      }
                      return
                  }
                }
              } catch (e) {
                console.error('Failed to parse SSE message:', e, line)
              }
            }
          })

          // Continue reading
          readStream()
        }).catch(error => {
          if (onError) {
            onError(error.message)
          }
        })
      }

      readStream()
    })
    .catch(error => {
      if (onError) {
        onError(error.message)
      }
    })
}

// Batch conversion
export const convertBatch = async (files, config) => {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  formData.append('config_json', JSON.stringify(config))

  const response = await api.post('/convert/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

// Download SQL file
export const downloadSql = async (conversionId) => {
  const response = await api.get(`/download/${conversionId}`, {
    responseType: 'blob',
  })

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url

  // Extract filename from Content-Disposition header
  const contentDisposition = response.headers['content-disposition']
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="(.+)"/)
    if (filenameMatch) {
      link.setAttribute('download', filenameMatch[1])
    }
  } else {
    link.setAttribute('download', `conversion_${conversionId}.sql`)
  }

  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Generate ABAP Report on demand
// mode: 'pure' (default) or 'exec_sql'
export const generateAbap = async (conversionId, mode = 'pure') => {
  const response = await api.post(`/generate-abap/${conversionId}`, null, {
    params: { mode }
  })
  return response.data
}

// Download ABAP Report file
export const downloadAbap = async (conversionId) => {
  const response = await api.get(`/download/${conversionId}/abap`, {
    responseType: 'blob',
  })

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url

  // Extract filename from Content-Disposition header
  const contentDisposition = response.headers['content-disposition']
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="(.+)"/)
    if (filenameMatch) {
      link.setAttribute('download', filenameMatch[1])
    }
  } else {
    link.setAttribute('download', `Z_XDS_${conversionId}.abap`)
  }

  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Download batch ZIP
export const downloadBatchZip = async (batchId) => {
  const response = await api.get(`/download/batch/${batchId}`, {
    responseType: 'blob',
  })
  
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `batch_${batchId}.zip`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Get history
export const getHistory = async (page = 1, pageSize = 50) => {
  const response = await api.get('/history', {
    params: { page, page_size: pageSize },
  })
  return response.data
}

// Get history detail
export const getHistoryDetail = async (conversionId) => {
  const response = await api.get(`/history/${conversionId}`)
  return response.data
}

// Delete history entry
export const deleteHistory = async (conversionId) => {
  await api.delete(`/history/${conversionId}`)
}

// Delete multiple history entries or all
export const deleteHistoryBulk = async (ids = []) => {
  if (ids.length > 0) {
    await api.delete('/history', {
      params: { ids: ids.join(',') },
    })
  } else {
    await api.delete('/history')
  }
}

// Get default config
export const getDefaultConfig = async () => {
  const response = await api.get('/config/defaults')
  return response.data
}

// Package Mapping APIs

// Upload package mapping Excel file
export const uploadPackageMapping = async (file, instanceName, instanceType) => {
  const formData = new FormData()
  formData.append('file', file)
  if (instanceName) formData.append('instance_name', instanceName)
  if (instanceType) formData.append('instance_type', instanceType)

  const response = await api.post('/package-mappings/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

// Get all HANA instances
export const getInstances = async () => {
  const response = await api.get('/package-mappings/instances')
  return response.data
}

// Get instance details
export const getInstanceDetails = async (instanceId) => {
  const response = await api.get(`/package-mappings/instance/${instanceId}`)
  return response.data
}

// Delete instance
export const deleteInstance = async (instanceId) => {
  const response = await api.delete(`/package-mappings/instance/${instanceId}`)
  return response.data
}

// Search package mappings
export const searchMappings = async (query, instanceName = null) => {
  const params = { q: query }
  if (instanceName) params.instance_name = instanceName

  const response = await api.get('/package-mappings/search', { params })
  return response.data
}

// Get statistics
export const getStatistics = async () => {
  const response = await api.get('/package-mappings/statistics')
  return response.data
}

// Get import history
export const getImportHistory = async (limit = 10) => {
  const response = await api.get('/package-mappings/history', {
    params: { limit },
  })
  return response.data
}

