import { Check, X, Loader, Circle } from 'lucide-react'
import './ConversionProgress.css'

function ConversionProgress({ stages, filename }) {
  // Calculate progress percentage
  const totalStages = 5 // Parse XML, Build IR, Generate SQL, Validate SQL, Auto-Correct SQL
  const completedStages = stages.filter(s => s.status === 'completed').length
  const progressPercent = Math.round((completedStages / totalStages) * 100)

  // Find current stage
  const currentStage = stages.find(s => s.status === 'in_progress')

  return (
    <div className="conversion-progress">
      <div className="progress-header">
        <h3>Converting {filename}...</h3>
        <span className="progress-percentage">{progressPercent}%</span>
      </div>

      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="stages-list">
        {stages.map((stage, index) => (
          <div key={index} className={`stage-item stage-${stage.status}`}>
            <span className="stage-icon">
              {stage.status === 'completed' && <Check size={16} />}
              {stage.status === 'in_progress' && <Loader size={16} className="spinning" />}
              {stage.status === 'pending' && <Circle size={16} />}
              {stage.status === 'failed' && <X size={16} />}
            </span>
            <span className="stage-name">{stage.stage_name}</span>
            {stage.duration_ms && (
              <span className="stage-duration">({stage.duration_ms}ms)</span>
            )}
            {stage.status === 'in_progress' && (
              <span className="stage-status">in progress...</span>
            )}
            {stage.error && (
              <div className="stage-error">Error: {stage.error}</div>
            )}
            {stage.details && Object.keys(stage.details).length > 0 && (
              <div className="stage-details">
                {Object.entries(stage.details).map(([key, value]) => (
                  <div key={key} className="detail-item">
                    <span className="detail-key">{key}:</span>{' '}
                    <span className="detail-value">{JSON.stringify(value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {currentStage && (
        <div className="current-stage-highlight">
          Currently processing: <strong>{currentStage.stage_name}</strong>
        </div>
      )}
    </div>
  )
}

export default ConversionProgress
