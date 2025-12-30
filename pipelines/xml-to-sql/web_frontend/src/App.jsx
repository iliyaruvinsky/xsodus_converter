import { useState } from 'react'
import Layout from './components/Layout'
import FileUpload from './components/FileUpload'
import ConfigForm from './components/ConfigForm'
import SqlPreview from './components/SqlPreview'
import HistoryPanel from './components/HistoryPanel'
import BatchConverter from './components/BatchConverter'
import BatchResults from './components/BatchResults'
import PackageMappingUpload from './components/PackageMappingUpload'
import XsodusLogo from './assets/xsodus-logo.png'
import './App.css'

function App() {
  const [mode, setMode] = useState('single') // 'single', 'batch', 'mappings', or 'history'
  const [singleFiles, setSingleFiles] = useState([])
  const [singleResult, setSingleResult] = useState(null)
  const [singleLoading, setSingleLoading] = useState(false)
  const [singleProgressStages, setSingleProgressStages] = useState([])
  const [batchFiles, setBatchFiles] = useState([])
  const [batchResult, setBatchResult] = useState(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [config, setConfig] = useState({
    database_mode: 'hana',
    hana_version: '2.0',
    hana_package: null,
    client: 'PROD',
    language: 'EN',
    schema_overrides: { 'ABAP': 'SAPABAP1' },
    view_schema: '_SYS_BIC',
    currency_udf_name: null,
    currency_rates_table: null,
    currency_schema: null,
    auto_fix: false,
  })

  const handleConfigChange = (newConfig) => {
    setConfig(newConfig)
  }

  return (
    <Layout>
      <div className="app-container">
        <div className="app-header">
          <div className="app-header-brand">
            <img src={XsodusLogo} alt="Xsodus" className="app-header-logo" />
            <h1>XML to SQL Converter</h1>
          </div>
          <div className="mode-selector">
            <button
              className={mode === 'single' ? 'active' : ''}
              onClick={() => setMode('single')}
            >
              Convert
            </button>
            <button
              className={mode === 'batch' ? 'active' : ''}
              onClick={() => setMode('batch')}
            >
              Batch
            </button>
            <button
              className={mode === 'mappings' ? 'active' : ''}
              onClick={() => setMode('mappings')}
            >
              Mappings
            </button>
            <button
              className={mode === 'history' ? 'active' : ''}
              onClick={() => setMode('history')}
            >
              History
            </button>
          </div>
        </div>

        {mode === 'history' ? (
          <HistoryPanel onClose={() => setMode('single')} />
        ) : mode === 'mappings' ? (
          <PackageMappingUpload />
        ) : (
          <>
            <div className="main-content">
              <div className="left-panel">
                {mode === 'single' ? (
                  <>
                    <FileUpload
                      multiple={false}
                      files={singleFiles}
                      onFilesChange={(newFiles) => {
                        setSingleFiles(newFiles)
                        setSingleResult(null)
                        setSingleProgressStages([])
                      }}
                      config={config}
                      onConfigChange={handleConfigChange}
                      onConversionComplete={(result) => {
                        setSingleResult(result)
                        setSingleProgressStages([])
                      }}
                      onProgressUpdate={setSingleProgressStages}
                      loading={singleLoading}
                      setLoading={setSingleLoading}
                    />
                    <ConfigForm
                      config={config}
                      onConfigChange={handleConfigChange}
                    />
                  </>
                ) : (
                  <>
                    <BatchConverter
                      files={batchFiles}
                      onFilesChange={(newFiles) => {
                        setBatchFiles(newFiles)
                        setBatchResult(null)
                      }}
                      config={config}
                      onConfigChange={handleConfigChange}
                      onConversionComplete={setBatchResult}
                      loading={batchLoading}
                      setLoading={setBatchLoading}
                    />
                    <ConfigForm
                      config={config}
                      onConfigChange={handleConfigChange}
                    />
                  </>
                )}
              </div>

              <div className="right-panel">
                {mode === 'single' && (
                  <SqlPreview
                    result={singleResult}
                    loading={singleLoading}
                    progressStages={singleProgressStages}
                    progressFilename={singleFiles[0]?.name}
                  />
                )}
                {mode === 'batch' && batchResult && (
                  <BatchResults batchResult={batchResult} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}

export default App

