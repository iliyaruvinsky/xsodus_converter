import { useState, useEffect } from 'react'
import { Info } from 'lucide-react'
import { getStatistics } from '../services/api'
import './ConfigForm.css'

const fieldHelpContent = {
  client: {
    tooltip:
      "⚠️ Rarely needed - only if your XML uses $$client$$ placeholders.\nPurpose: Replaces $$client$$ placeholders in the XML with your specified value.\nDefault: PROD (sufficient for most cases)\nWhen to change: Only if your XML has dynamic client filters (e.g., WHERE MANDT = '$$client$$').\nNote: Most XMLs use hardcoded client values, not placeholders.",
    content: (
      <div className="field-help">
        <strong>⚠️ Rarely Needed:</strong> Only change if your XML files actually contain <code>$$client$$</code> placeholders (which is uncommon).
        <br />
        <strong>Purpose:</strong> Replaces <code>$$client$$</code> placeholders in the XML with your specified value.
        <br />
        <strong>Default:</strong> PROD (works for 95%+ of cases)
        <br />
        <strong>When to change:</strong> Only if your XML has dynamic client logic like <code>WHERE MANDT = '$$client$$'</code>.
        <br />
        <strong>Note:</strong> Most SAP XMLs use hardcoded values (e.g., <code>WHERE MANDT = '100'</code>), not placeholders.
      </div>
    ),
  },
  language: {
    tooltip:
      "💡 Needed for multi-language deployments - only if your XML uses $$language$$ placeholders.\nPurpose: Replaces $$language$$ placeholders in the XML with your specified value.\nDefault: EN (sufficient for single-language deployments)\nWhen to change: For multi-language SAP systems or if your XML filters by language (e.g., WHERE SPRAS = '$$language$$').\nNote: Default 'EN' works fine for English-only deployments.",
    content: (
      <div className="field-help">
        <strong>💡 Multi-Language Feature:</strong> Only needed if your XML contains <code>$$language$$</code> placeholders or you have multi-language requirements.
        <br />
        <strong>Purpose:</strong> Replaces <code>$$language$$</code> placeholders in the XML with your specified value.
        <br />
        <strong>Default:</strong> EN (works for English/single-language deployments)
        <br />
        <strong>When to change:</strong> Multi-language SAP deployments with language-specific filters like <code>WHERE SPRAS = '$$language$$'</code>.
        <br />
        <strong>Example:</strong> Set to 'DE' for German, 'FR' for French, etc.
      </div>
    ),
  },
  schemaOverrides: {
    tooltip:
      'Purpose: Maps schema names from the XML to your Snowflake schema names.\nWhen to use: If your Snowflake schemas have different names than what appears in the XML.\nExample: If your XML references SAPK5D.MARA but your Snowflake schema is PRODUCTION_DATA, add an override SAPK5D → PRODUCTION_DATA. The generated SQL will use PRODUCTION_DATA.MARA.\nNote: Leave empty if your Snowflake schema names match the XML exactly.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Maps schema names from the XML to your Snowflake schema names.
        <br />
        <strong>When to use:</strong> If your Snowflake schemas have different names than what's in the XML.
        <br />
        <strong>Example:</strong> If your XML references <code>SAPK5D.MARA</code> but your Snowflake schema is <code>PRODUCTION_DATA</code>, add an override: <code>SAPK5D</code> → <code>PRODUCTION_DATA</code>. The generated SQL will use <code>PRODUCTION_DATA.MARA</code>.
        <br />
        <strong>Note:</strong> Leave empty if your Snowflake schema names match the XML exactly.
      </div>
    ),
  },
  currencyOverview: {
    tooltip:
      'Purpose: Specifies currency conversion UDF and table names if your XML uses currency conversion.\nWhen to use: Only if your calculation views perform currency conversion.\nNote: Leave empty if currency conversion is not part of the XML.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Specifies currency conversion UDF and table names if your XML uses currency conversion.
        <br />
        <strong>When to use:</strong> Only if your calculation views perform currency conversion. Leave empty if not applicable.
        <br />
        <strong>Note:</strong> These settings apply to both HANA and Snowflake modes. They tell the converter what names to use in the generated SQL for currency conversion functions and tables.
      </div>
    ),
  },
  currencyUdf: {
    tooltip:
      'Purpose: Name of your currency conversion function.\nExample: CONVERT_CURRENCY or MY_CURRENCY_CONVERT.\nNote: This should match the actual UDF name in your target database.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Name of your currency conversion function.
        <br />
        <strong>Example:</strong> <code>CONVERT_CURRENCY</code> or <code>MY_CURRENCY_CONVERT</code>
        <br />
        <strong>Note:</strong> This should match the actual UDF name in your target database environment.
      </div>
    ),
  },
  currencyTable: {
    tooltip:
      'Purpose: Name of your exchange rates table.\nExample: EXCHANGE_RATES or CURRENCY_RATES.\nNote: This table should contain currency exchange rate data used by the UDF.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Name of your exchange rates table.
        <br />
        <strong>Example:</strong> <code>EXCHANGE_RATES</code> or <code>CURRENCY_RATES</code>
        <br />
        <strong>Note:</strong> This table should contain currency exchange rate data used by the UDF.
      </div>
    ),
  },
  currencySchema: {
    tooltip:
      'Purpose: Schema where your currency conversion UDF and rates table are located.\nExample: UTILITY or FINANCE.\nNote: The generated SQL will reference currency artifacts as SCHEMA.UDF_NAME and SCHEMA.TABLE_NAME.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Schema where your currency conversion UDF and rates table are located.
        <br />
        <strong>Example:</strong> <code>UTILITY</code> or <code>FINANCE</code>
        <br />
        <strong>Note:</strong> The generated SQL will reference currency artifacts as <code>SCHEMA.UDF_NAME</code> and <code>SCHEMA.TABLE_NAME</code>.
      </div>
    ),
  },
  hanaVersion: {
    tooltip:
      'Purpose: Select the target HANA version for SQL generation.\nWhy Needed: Different HANA versions support different SQL syntax and functions.\nHANA 1.0: Legacy syntax (LEFTSTR, RIGHTSTR preserved)\nHANA 2.0+: Modern syntax (SUBSTRING, LEFT, RIGHT)\nDefault: HANA 2.0 (most common in production)',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Select the target HANA version for SQL generation.
        <br />
        <strong>Why Needed:</strong> Different HANA versions support different SQL syntax and functions.
        <br />
        <strong>HANA 1.0:</strong> Legacy syntax preserved (LEFTSTR, RIGHTSTR)
        <br />
        <strong>HANA 2.0+:</strong> Modern syntax used (SUBSTRING, LEFT, RIGHT)
        <br />
        <strong>Default:</strong> <code>HANA 2.0</code> (most common in production systems)
        <br />
        <strong>Note:</strong> If unsure, use HANA 2.0 - it works for most modern SAP systems.
      </div>
    ),
  },
  targetSchema: {
    tooltip:
      'Purpose: Target schema where tables reside on your HANA system.\nWhy Needed: When converting XMLs from one SAP system to another, the source schema (e.g., SAPK5D) must be mapped to the target schema (e.g., SAPABAP1).\nExample: If XML references SAPK5D.MARA but your target system uses SAPABAP1.MARA, enter SAPABAP1.\nDefault: SAPABAP1 (most common for SAP ECC/S4HANA systems)',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Target schema where tables reside on your HANA system.
        <br />
        <strong>Why Needed:</strong> When converting XMLs from one SAP system to another, the source schema in the XML must be mapped to the actual schema on your target system.
        <br />
        <strong>Example:</strong> If your XML references <code>SAPK5D.MARA</code> but your target HANA system uses <code>SAPABAP1.MARA</code>, enter <code>SAPABAP1</code>.
        <br />
        <strong>Default:</strong> <code>SAPABAP1</code> (most common for SAP ECC/S4HANA systems)
        <br />
        <strong>Note:</strong> This replaces ALL source schemas in the XML with the specified target schema.
      </div>
    ),
  },
  hanaPackage: {
    tooltip:
      'Purpose: HANA repository package path where the calculation view is stored.\nFormat: Use dot notation (.) for the package hierarchy, e.g., Macabi_BI.EYAL.EYAL_CDS\nAuto-Detection: Leave empty to auto-detect from uploaded package mappings (if available).\nExample: If your CV is in Macabi_BI → EYAL → EYAL_CDS folder, enter: Macabi_BI.EYAL.EYAL_CDS\nResult: Generated view will be "_SYS_BIC"."Macabi_BI.EYAL.EYAL_CDS/CV_NAME"',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> HANA repository package path where the calculation view is stored.
        <br />
        <strong>Format:</strong> Use dot notation (.) for the package hierarchy
        <br />
        <strong>Example:</strong> <code>Macabi_BI.EYAL.EYAL_CDS</code>
        <br />
        <strong>Auto-Detection:</strong> Leave empty to auto-detect from uploaded package mappings (if available in the Mappings tab).
        <br />
        <strong>Result:</strong> The generated view will be <code>"_SYS_BIC"."Macabi_BI.EYAL.EYAL_CDS/CV_NAME"</code>
        <br />
        <strong>Note:</strong> Only used when View Schema is set to <code>_SYS_BIC</code>.
      </div>
    ),
  },
  viewSchema: {
    tooltip:
      'Purpose: Schema where the generated HANA view should be created.\nDefault: _SYS_BIC (for catalog calculation views)\nWhen to change: If you want to create views in a different schema.\nNote: When using _SYS_BIC, the package path is required for proper view naming.',
    content: (
      <div className="field-help">
        <strong>Purpose:</strong> Schema where the generated HANA view should be created.
        <br />
        <strong>Default:</strong> <code>_SYS_BIC</code> (for catalog calculation views)
        <br />
        <strong>When to change:</strong> If you want to create views in a different schema.
        <br />
        <strong>Note:</strong> When using <code>_SYS_BIC</code>, the package path is required for proper view naming.
      </div>
    ),
  },
  autoCorrection: {
    tooltip:
      'What it does: Automatically fixes common SQL syntax and semantic issues in the generated SQL.\n\nWhen to apply: Enable this BEFORE converting your XML to SQL if you want the system to automatically correct issues during conversion. This setting affects the conversion process itself.\n\nWhy to apply: Saves time by resolving frequent SQL errors, making the generated SQL more production-ready. Particularly useful for migrating legacy HANA SQL patterns that may have compatibility issues.\n\nExamples of fixes:\n• Reserved keywords: ORDER becomes `ORDER` (quoted)\n• String concatenation: "text1" + "text2" becomes "text1" || "text2"\n• Function translation: IF(condition, val1, val2) becomes IFF(condition, val1, val2)\n\nConfidence levels: The system applies high-confidence fixes automatically. All corrections are shown in the SQL Preview after conversion.',
    content: (
      <div className="field-help">
        <strong>What it does:</strong> Automatically fixes common SQL syntax and semantic issues in the generated SQL.
        <br /><br />
        <strong>When to apply:</strong> Enable this <strong>BEFORE</strong> converting your XML to SQL if you want the system to automatically correct issues during conversion. This setting affects the conversion process itself, so it must be enabled before clicking "Convert to SQL".
        <br /><br />
        <strong>Why to apply:</strong> Saves time by resolving frequent SQL errors, making the generated SQL more production-ready. Particularly useful for migrating legacy HANA SQL patterns that may have compatibility issues.
        <br /><br />
        <strong>Examples of fixes:</strong>
        <ul style={{ marginTop: '0.5rem', marginBottom: '0.5rem', paddingLeft: '1.5rem' }}>
          <li><strong>Reserved keywords:</strong> <code>ORDER</code> becomes <code>`ORDER`</code> (quoted)</li>
          <li><strong>String concatenation:</strong> <code>"text1" + "text2"</code> becomes <code>"text1" || "text2"</code></li>
          <li><strong>Function translation:</strong> <code>IF(condition, val1, val2)</code> becomes <code>IFF(condition, val1, val2)</code></li>
        </ul>
        <strong>Note:</strong> Different validation and correction rules apply based on the selected database mode (HANA vs. Snowflake).
      </div>
    ),
  },
}

function ConfigForm({ config, onConfigChange }) {
  const [schemaOverrides, setSchemaOverrides] = useState(
    Object.entries(config.schema_overrides || {}).map(([key, value]) => ({ key, value }))
  )
  const [showHelp, setShowHelp] = useState(false)

  // Collapsible section states - all collapsed by default
  const [generalExpanded, setGeneralExpanded] = useState(false)
  const [hanaExpanded, setHanaExpanded] = useState(false)
  const [snowflakeExpanded, setSnowflakeExpanded] = useState(false)

  // Package mappings state
  const [mappingsCount, setMappingsCount] = useState(0)
  const [overridePackagePath, setOverridePackagePath] = useState(false)

  // Fetch mappings statistics on mount
  useEffect(() => {
    const fetchMappings = async () => {
      try {
        const stats = await getStatistics()
        setMappingsCount(stats.total_cvs || 0)
      } catch (error) {
        console.error('Failed to fetch mappings statistics:', error)
        setMappingsCount(0)
      }
    }
    fetchMappings()
  }, [])

  // Auto-expand mode-specific section when database mode changes
  useEffect(() => {
    if (config.database_mode === 'hana') {
      setHanaExpanded(true)
      setSnowflakeExpanded(false)
    } else if (config.database_mode === 'snowflake') {
      setSnowflakeExpanded(true)
      setHanaExpanded(false)
    }
  }, [config.database_mode])

  const updateConfig = (updates) => {
    onConfigChange({ ...config, ...updates })
  }

  const addSchemaOverride = () => {
    const newOverrides = [...schemaOverrides, { key: '', value: '' }]
    setSchemaOverrides(newOverrides)
    updateSchemaOverrides(newOverrides)
  }

  const removeSchemaOverride = (index) => {
    const newOverrides = schemaOverrides.filter((_, i) => i !== index)
    setSchemaOverrides(newOverrides)
    updateSchemaOverrides(newOverrides)
  }

  const updateSchemaOverride = (index, field, value) => {
    const newOverrides = [...schemaOverrides]
    newOverrides[index][field] = value
    setSchemaOverrides(newOverrides)
    updateSchemaOverrides(newOverrides)
  }

  const updateSchemaOverrides = (overrides) => {
    const overridesObj = {}
    overrides.forEach(({ key, value }) => {
      if (key && value) {
        overridesObj[key] = value
      }
    })
    updateConfig({ schema_overrides: overridesObj })
  }

  return (
    <div className="config-form-container">
      <div className="card">
        <div className="config-header">
          <h2>Configuration</h2>
          <button
            className="help-toggle-btn"
            onClick={() => setShowHelp(!showHelp)}
            title="Toggle help"
          >
            {showHelp ? '−' : '?'}
          </button>
        </div>

        {showHelp && (
          <div className="config-help-overview">
            <h3>About Configuration</h3>
            <p>
              This tool generates SQL files that you execute in your target database (HANA or Snowflake).
              The configuration below controls how the SQL is generated to match your database environment.
              You don't need to connect to the database here—just configure the settings, generate SQL,
              then execute it using your preferred tool.
            </p>
            <p>
              <strong>Note:</strong> Most fields have default values and can be left unchanged unless
              your XML files use specific placeholders or your database schemas differ from the XML.
            </p>
          </div>
        )}

        {/* Target Database Section */}
        <div className="form-section form-section-primary">
          <h3>Target Database</h3>

          <div className="form-group">
            <label htmlFor="database_mode">
              Database Mode
            </label>
            <select
              id="database_mode"
              value={config.database_mode || 'hana'}
              onChange={(e) => updateConfig({ database_mode: e.target.value })}
            >
              <option value="hana">SAP HANA</option>
              <option value="snowflake">Snowflake</option>
            </select>
          </div>
        </div>

        {/* General Settings Section - Collapsible */}
        <div className="form-section collapsible-section general-section">
          <div
            className="collapsible-header"
            onClick={() => setGeneralExpanded(!generalExpanded)}
          >
            <h3>
              <span className="collapse-icon">{generalExpanded ? '▼' : '▶'}</span>
              General
            </h3>
          </div>

          {generalExpanded && (
            <div className="collapsible-content">
              <div className="form-group">
                <label htmlFor="client">
                  Client
                  <span className="help-icon" title={fieldHelpContent.client.tooltip}><Info size={14} /></span>
                </label>
                {showHelp && fieldHelpContent.client.content}
                <input
                  id="client"
                  type="text"
                  value={config.client || 'PROD'}
                  onChange={(e) => updateConfig({ client: e.target.value })}
                  placeholder="PROD"
                />
              </div>

              <div className="form-group">
                <label htmlFor="language">
                  Language
                  <span className="help-icon" title={fieldHelpContent.language.tooltip}><Info size={14} /></span>
                </label>
                {showHelp && fieldHelpContent.language.content}
                <input
                  id="language"
                  type="text"
                  value={config.language || 'EN'}
                  onChange={(e) => updateConfig({ language: e.target.value })}
                  placeholder="EN"
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    id="auto_fix"
                    type="checkbox"
                    checked={config.auto_fix || false}
                    onChange={(e) => updateConfig({ auto_fix: e.target.checked })}
                  />
                  <span>Auto-correct SQL issues</span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* HANA-Specific Settings - Collapsible */}
        {config.database_mode === 'hana' && (
          <div className="form-section collapsible-section mode-specific-section hana-section">
            <div
              className="collapsible-header"
              onClick={() => setHanaExpanded(!hanaExpanded)}
            >
              <h3>
                <span className="collapse-icon">{hanaExpanded ? '▼' : '▶'}</span>
                HANA
              </h3>
            </div>

            {hanaExpanded && (
              <div className="collapsible-content">
                <div className="form-group">
                  <label htmlFor="target_schema">
                    Table Schema
                    <span className="help-icon" title={fieldHelpContent.targetSchema.tooltip}><Info size={14} /></span>
                  </label>
                  {showHelp && fieldHelpContent.targetSchema.content}
                  <input
                    id="target_schema"
                    type="text"
                    value={config.target_schema || 'SAPABAP1'}
                    onChange={(e) => updateConfig({ target_schema: e.target.value || 'SAPABAP1' })}
                    placeholder="SAPABAP1"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="hana_package">
                    Package Path
                    <span className="help-icon" title={fieldHelpContent.hanaPackage.tooltip}><Info size={14} /></span>
                  </label>
                  {showHelp && fieldHelpContent.hanaPackage.content}
                  {mappingsCount > 0 && !overridePackagePath ? (
                    <div className="auto-detect-field">
                      <span className="auto-detect-text">Auto detected</span>
                      <button
                        type="button"
                        className="override-link"
                        onClick={() => setOverridePackagePath(true)}
                      >
                        Manual override
                      </button>
                    </div>
                  ) : (
                    <>
                      <input
                        id="hana_package"
                        type="text"
                        value={config.hana_package || ''}
                        onChange={(e) => updateConfig({ hana_package: e.target.value || null })}
                        placeholder="Macabi_BI.EYAL.EYAL_CDS"
                      />
                      {mappingsCount > 0 && (
                        <button
                          type="button"
                          className="use-auto-detect-link"
                          onClick={() => {
                            setOverridePackagePath(false)
                            updateConfig({ hana_package: null })
                          }}
                        >
                          Use auto-detect ({mappingsCount} CVs)
                        </button>
                      )}
                    </>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="view_schema">
                    View Schema
                    <span className="help-icon" title={fieldHelpContent.viewSchema.tooltip}><Info size={14} /></span>
                  </label>
                  {showHelp && fieldHelpContent.viewSchema.content}
                  <input
                    id="view_schema"
                    type="text"
                    value={config.view_schema || '_SYS_BIC'}
                    onChange={(e) => updateConfig({ view_schema: e.target.value || '_SYS_BIC' })}
                    placeholder="_SYS_BIC"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="hana_version">
                    Version
                    <span className="help-icon" title={fieldHelpContent.hanaVersion.tooltip}><Info size={14} /></span>
                  </label>
                  {showHelp && fieldHelpContent.hanaVersion.content}
                  <select
                    id="hana_version"
                    value={config.hana_version || '2.0'}
                    onChange={(e) => updateConfig({ hana_version: e.target.value })}
                  >
                    <option value="1.0">HANA 1.0</option>
                    <option value="2.0">HANA 2.0</option>
                    <option value="2.0_SPS01">HANA 2.0 SPS01</option>
                    <option value="2.0_SPS03">HANA 2.0 SPS03</option>
                    <option value="2.0_SPS04">HANA 2.0 SPS04</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Snowflake-Specific Settings - Collapsible */}
        {config.database_mode === 'snowflake' && (
          <div className="form-section collapsible-section mode-specific-section snowflake-section">
            <div
              className="collapsible-header"
              onClick={() => setSnowflakeExpanded(!snowflakeExpanded)}
            >
              <h3>
                <span className="collapse-icon">{snowflakeExpanded ? '▼' : '▶'}</span>
                Snowflake
              </h3>
            </div>

            {snowflakeExpanded && (
              <div className="collapsible-content">
                <div className="form-group">
                  <label>
                    Schema Overrides
                    <span className="help-icon" title={fieldHelpContent.schemaOverrides.tooltip}><Info size={14} /></span>
                  </label>
                  {showHelp && fieldHelpContent.schemaOverrides.content}
                  {schemaOverrides.map((override, index) => (
                    <div key={index} className="schema-override-row">
                      <input
                        type="text"
                        placeholder="Source schema"
                        value={override.key}
                        onChange={(e) => updateSchemaOverride(index, 'key', e.target.value)}
                      />
                      <span>→</span>
                      <input
                        type="text"
                        placeholder="Target schema"
                        value={override.value}
                        onChange={(e) => updateSchemaOverride(index, 'value', e.target.value)}
                      />
                      <button
                        className="remove-override-btn"
                        onClick={() => removeSchemaOverride(index)}
                        title="Remove"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button className="add-override-btn" onClick={addSchemaOverride}>
                    + Add Override
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}

export default ConfigForm
