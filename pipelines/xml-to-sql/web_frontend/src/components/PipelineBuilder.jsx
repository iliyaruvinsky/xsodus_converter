import { useState, useEffect, useRef, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { getPipelineBlocks, getPipelineTemplates, executePipeline, validatePipeline } from '../services/api'
import PipelineResultViewer from './PipelineResultViewer'
import './PipelineBuilder.css'

// Icons for different block types (using simple text symbols)
const BLOCK_ICONS = {
  'xml-calcview': '[XML]',
  'xml-cds': '[CDS]',
  'sql-input': '[SQL]',
  'ir-to-sql': '>>',
  'ir-to-abap': '[AB]',  // Pure ABAP (no SQL)
  'sql-to-cds': '>>',
  'sql-to-abap': '>>',
  'sql-to-json': '>>',
  'target-hana': '[H]',
  'target-ecc-hana': '[EH]',
  'target-ecc-sql': '[ES]',
  'target-s4hana': '[S4]',
  'target-bw-hana': '[BH]',
  'target-bw-sql': '[BS]',
  'target-snowflake': '[SF]',
}

// Color mapping for block types
const BLOCK_COLORS = {
  source: { bg: '#e8f5e9', border: '#4caf50', header: '#2e7d32' },
  transform: { bg: '#e3f2fd', border: '#2196f3', header: '#1565c0' },
  target: { bg: '#fff3e0', border: '#ff9800', header: '#e65100' },
}

function PipelineBuilder() {
  // State
  const [blocks, setBlocks] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Pipeline state
  const [pipelineBlocks, setPipelineBlocks] = useState([])
  const [connections, setConnections] = useState([])
  const [selectedBlock, setSelectedBlock] = useState(null)
  const [connectingFrom, setConnectingFrom] = useState(null)

  // Source file state
  const [sourceFile, setSourceFile] = useState(null)
  const [sourceContent, setSourceContent] = useState('')

  // Execution state
  const [executing, setExecuting] = useState(false)
  const [results, setResults] = useState(null)
  const [validationErrors, setValidationErrors] = useState([])

  // Canvas ref for positioning
  const canvasRef = useRef(null)
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 })

  // Drag state
  const [dragging, setDragging] = useState(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })

  // Load blocks and templates on mount
  useEffect(() => {
    loadData()
  }, [])

  // Update canvas offset when ref changes
  useEffect(() => {
    if (canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect()
      setCanvasOffset({ x: rect.left, y: rect.top })
    }
  }, [canvasRef.current])

  const loadData = async () => {
    try {
      setLoading(true)
      const [blocksData, templatesData] = await Promise.all([
        getPipelineBlocks(),
        getPipelineTemplates()
      ])
      setBlocks(blocksData.blocks || [])
      setTemplates(templatesData || [])
      setError(null)
    } catch (err) {
      setError('Failed to load pipeline data: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  // File drop handler
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0]
      setSourceFile(file)

      const reader = new FileReader()
      reader.onload = (e) => {
        setSourceContent(e.target.result)
      }
      reader.readAsText(file)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/xml': ['.xml'] },
    multiple: false
  })

  // Add block to canvas
  const addBlock = (blockDef) => {
    const newBlock = {
      id: `block-${Date.now()}`,
      block_id: blockDef.id,
      type: blockDef.type,
      name: blockDef.name,
      config: {},
      position: { x: 100 + pipelineBlocks.length * 50, y: 100 + pipelineBlocks.length * 30 }
    }
    setPipelineBlocks([...pipelineBlocks, newBlock])
    setSelectedBlock(newBlock.id)
  }

  // Remove block from canvas
  const removeBlock = (blockId) => {
    setPipelineBlocks(pipelineBlocks.filter(b => b.id !== blockId))
    setConnections(connections.filter(c => c.from_block !== blockId && c.to_block !== blockId))
    if (selectedBlock === blockId) {
      setSelectedBlock(null)
    }
  }

  // Start connection from a block
  const startConnection = (blockId) => {
    setConnectingFrom(blockId)
  }

  // Complete connection to a block
  const completeConnection = (toBlockId) => {
    if (connectingFrom && connectingFrom !== toBlockId) {
      // Check if connection already exists
      const exists = connections.some(
        c => c.from_block === connectingFrom && c.to_block === toBlockId
      )
      if (!exists) {
        setConnections([...connections, { from_block: connectingFrom, to_block: toBlockId }])
      }
    }
    setConnectingFrom(null)
  }

  // Remove connection
  const removeConnection = (fromBlock, toBlock) => {
    setConnections(connections.filter(
      c => !(c.from_block === fromBlock && c.to_block === toBlock)
    ))
  }

  // Load template
  const loadTemplate = (template) => {
    setPipelineBlocks(template.blocks.map(b => ({
      ...b,
      type: blocks.find(bl => bl.id === b.block_id)?.type || 'transform',
      name: blocks.find(bl => bl.id === b.block_id)?.name || b.block_id
    })))
    setConnections(template.connections || [])
    setResults(null)
    setValidationErrors([])
  }

  // Clear pipeline
  const clearPipeline = () => {
    setPipelineBlocks([])
    setConnections([])
    setResults(null)
    setValidationErrors([])
    setSelectedBlock(null)
  }

  // Validate pipeline
  const handleValidate = async () => {
    const pipeline = {
      id: 'pipeline-1',
      name: 'Custom Pipeline',
      blocks: pipelineBlocks,
      connections
    }

    try {
      const result = await validatePipeline(pipeline)
      setValidationErrors(result.errors || [])
      return result.valid
    } catch (err) {
      setValidationErrors([err.message])
      return false
    }
  }

  // Execute pipeline
  const handleExecute = async () => {
    if (!sourceContent) {
      setValidationErrors(['Please upload an XML file first'])
      return
    }

    const isValid = await handleValidate()
    if (!isValid) {
      return
    }

    setExecuting(true)
    setResults(null)

    const pipeline = {
      id: 'pipeline-1',
      name: 'Custom Pipeline',
      blocks: pipelineBlocks,
      connections
    }

    try {
      const result = await executePipeline(pipeline, sourceContent)
      setResults(result)
    } catch (err) {
      setValidationErrors([err.message || 'Execution failed'])
    } finally {
      setExecuting(false)
    }
  }

  // Block drag handlers
  const handleBlockMouseDown = (e, block) => {
    if (e.target.classList.contains('block-connect-btn') ||
        e.target.classList.contains('block-remove-btn')) {
      return
    }

    const rect = e.currentTarget.getBoundingClientRect()
    setDragging(block.id)
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    })
    setSelectedBlock(block.id)
    e.preventDefault()
  }

  const handleMouseMove = (e) => {
    if (dragging && canvasRef.current) {
      const canvasRect = canvasRef.current.getBoundingClientRect()
      const newX = e.clientX - canvasRect.left - dragOffset.x
      const newY = e.clientY - canvasRect.top - dragOffset.y

      setPipelineBlocks(pipelineBlocks.map(b =>
        b.id === dragging
          ? { ...b, position: { x: Math.max(0, newX), y: Math.max(0, newY) } }
          : b
      ))
    }
  }

  const handleMouseUp = () => {
    setDragging(null)
  }

  // Get block position for connection drawing
  const getBlockCenter = (blockId) => {
    const block = pipelineBlocks.find(b => b.id === blockId)
    if (!block) return { x: 0, y: 0 }
    return {
      x: block.position.x + 100, // Half of block width (200px)
      y: block.position.y + 40   // Half of block height (80px)
    }
  }

  // Render connection lines
  const renderConnections = () => {
    return connections.map((conn, index) => {
      const from = getBlockCenter(conn.from_block)
      const to = getBlockCenter(conn.to_block)

      // Calculate control points for curved line
      const midX = (from.x + to.x) / 2

      return (
        <g key={index} className="connection-line">
          <path
            d={`M ${from.x} ${from.y} Q ${midX} ${from.y}, ${midX} ${(from.y + to.y) / 2} T ${to.x} ${to.y}`}
            fill="none"
            stroke="#666"
            strokeWidth="2"
            markerEnd="url(#arrowhead)"
          />
          <circle
            cx={midX}
            cy={(from.y + to.y) / 2}
            r="8"
            fill="#fff"
            stroke="#666"
            className="connection-delete"
            onClick={() => removeConnection(conn.from_block, conn.to_block)}
          />
          <text
            x={midX}
            y={(from.y + to.y) / 2 + 4}
            textAnchor="middle"
            fontSize="12"
            fill="#666"
            className="connection-delete-text"
            onClick={() => removeConnection(conn.from_block, conn.to_block)}
          >
            x
          </text>
        </g>
      )
    })
  }

  if (loading) {
    return <div className="pipeline-loading">Loading pipeline builder...</div>
  }

  if (error) {
    return <div className="pipeline-error">{error}</div>
  }

  return (
    <div className="pipeline-builder">
      {/* Header */}
      <div className="pipeline-header">
        <h2>Visual Pipeline Builder</h2>
        <div className="pipeline-actions">
          <button onClick={clearPipeline} disabled={executing}>
            Clear
          </button>
          <button onClick={handleValidate} disabled={executing}>
            Validate
          </button>
          <button
            onClick={handleExecute}
            disabled={executing || pipelineBlocks.length === 0}
            className="execute-btn"
          >
            {executing ? 'Executing...' : 'Execute Pipeline'}
          </button>
        </div>
      </div>

      <div className="pipeline-content">
        {/* Left Sidebar - Block Palette */}
        <div className="block-palette">
          <h3>Blocks</h3>

          <div className="block-category">
            <h4>Sources</h4>
            {blocks.filter(b => b.type === 'source').map(block => (
              <div
                key={block.id}
                className="palette-block source"
                onClick={() => addBlock(block)}
              >
                <span className="block-icon">{BLOCK_ICONS[block.id] || '[?]'}</span>
                <span className="block-name">{block.name}</span>
              </div>
            ))}
          </div>

          <div className="block-category">
            <h4>Transforms</h4>
            {blocks.filter(b => b.type === 'transform').map(block => (
              <div
                key={block.id}
                className="palette-block transform"
                onClick={() => addBlock(block)}
              >
                <span className="block-icon">{BLOCK_ICONS[block.id] || '>>'}</span>
                <span className="block-name">{block.name}</span>
              </div>
            ))}
          </div>

          <div className="block-category">
            <h4>Targets</h4>
            {blocks.filter(b => b.type === 'target').map(block => (
              <div
                key={block.id}
                className="palette-block target"
                onClick={() => addBlock(block)}
              >
                <span className="block-icon">{BLOCK_ICONS[block.id] || '[T]'}</span>
                <span className="block-name">{block.name}</span>
              </div>
            ))}
          </div>

          <div className="block-category">
            <h4>Templates</h4>
            {templates.map(template => (
              <div
                key={template.id}
                className="palette-template"
                onClick={() => loadTemplate(template)}
              >
                <span className="template-name">{template.name}</span>
                <span className="template-desc">{template.description}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Main Canvas */}
        <div className="pipeline-main">
          {/* File Upload */}
          <div {...getRootProps()} className={`file-dropzone ${isDragActive ? 'active' : ''} ${sourceFile ? 'has-file' : ''}`}>
            <input {...getInputProps()} />
            {sourceFile ? (
              <div className="file-info">
                <span className="file-icon">[FILE]</span>
                <span className="file-name">{sourceFile.name}</span>
                <button className="file-clear" onClick={(e) => {
                  e.stopPropagation()
                  setSourceFile(null)
                  setSourceContent('')
                }}>x</button>
              </div>
            ) : (
              <p>Drop XML file here or click to select</p>
            )}
          </div>

          {/* Canvas */}
          <div
            className="pipeline-canvas"
            ref={canvasRef}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onClick={() => {
              if (connectingFrom) {
                setConnectingFrom(null)
              }
            }}
          >
            {/* Connection SVG Layer */}
            <svg className="connections-layer">
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="7"
                  refX="9"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3.5, 0 7" fill="#666" />
                </marker>
              </defs>
              {renderConnections()}
            </svg>

            {/* Blocks */}
            {pipelineBlocks.map(block => {
              const colors = BLOCK_COLORS[block.type] || BLOCK_COLORS.transform
              return (
                <div
                  key={block.id}
                  className={`canvas-block ${selectedBlock === block.id ? 'selected' : ''} ${connectingFrom === block.id ? 'connecting' : ''}`}
                  style={{
                    left: block.position.x,
                    top: block.position.y,
                    backgroundColor: colors.bg,
                    borderColor: colors.border
                  }}
                  onMouseDown={(e) => handleBlockMouseDown(e, block)}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (connectingFrom && connectingFrom !== block.id) {
                      completeConnection(block.id)
                    } else {
                      setSelectedBlock(block.id)
                    }
                  }}
                >
                  <div className="block-header" style={{ backgroundColor: colors.header }}>
                    <span className="block-icon">{BLOCK_ICONS[block.block_id] || '[?]'}</span>
                    <span className="block-title">{block.name}</span>
                    <button
                      className="block-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeBlock(block.id)
                      }}
                    >x</button>
                  </div>
                  <div className="block-body">
                    <span className="block-type">{block.type}</span>
                  </div>
                  <div className="block-footer">
                    <button
                      className="block-connect-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        startConnection(block.id)
                      }}
                    >
                      Connect &rarr;
                    </button>
                  </div>
                </div>
              )
            })}

            {pipelineBlocks.length === 0 && (
              <div className="canvas-empty">
                <p>Drag blocks from the palette or select a template</p>
              </div>
            )}
          </div>

          {/* Validation Errors */}
          {validationErrors.length > 0 && (
            <div className="validation-errors">
              <h4>Errors:</h4>
              <ul>
                {validationErrors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Sidebar - Results */}
        <div className="pipeline-results">
          <PipelineResultViewer
            results={results}
            filename={sourceFile?.name}
          />
        </div>
      </div>
    </div>
  )
}

export default PipelineBuilder
