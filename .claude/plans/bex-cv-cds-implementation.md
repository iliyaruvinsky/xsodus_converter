# Implementation Plan: BEx-to-CV and CV-to-CDS Pipelines

**Plan Version**: 3.0 (Corrected & Enhanced)
**Created**: 2026-02-01
**Last Updated**: 2026-02-01
**Status**: Phase 1 & 2 Complete, Phase 3-7 Pending

---

## Table of Contents
1. [Critical Decisions (ANSWER FIRST)](#critical-decisions-answer-first)
2. [Scope & Assumptions](#scope--assumptions)
3. [Project Context](#project-context)
4. [SAP Ecosystem Background](#sap-ecosystem-background)
5. [Support Matrices](#support-matrices)
6. [Pipeline 1: BEx XML → HANA Calculation View](#pipeline-1-bex-xml--hana-calculation-view)
7. [Pipeline 2: HANA CV → CDS View](#pipeline-2-hana-cv--cds-view)
8. [BEx Cross-Linking Specification](#bex-cross-linking-specification)
9. [Stage Gates](#stage-gates)
10. [Conversion Report Specification](#conversion-report-specification)
11. [Verification Strategy (Tiered)](#verification-strategy-tiered)
12. [Implementation Phases](#implementation-phases)
13. [Known Risks & Mitigations](#known-risks--mitigations)

---

## Critical Decisions (ANSWER FIRST)

**These 10 decisions MUST be answered and baked into the implementation before proceeding:**

### Decision 1: Target Parity Level
**Question**: What level of functional parity with the original BEx query is required?

| Option | Description | Implications |
|--------|-------------|--------------|
| **A) Structural** | Same columns, filters, parameters visible | No result comparison required |
| **B) Semantic** | Results must match for identical inputs | Requires runtime validation environment |
| **C) Full** | Identical behavior including edge cases | Requires extensive test suite |

**CURRENT ANSWER**: `A) Structural` (MVP - verify structure, not runtime results)

### Decision 2: BW vs ECC Data Sources
**Question**: Are data sources BW-on-HANA objects (`/BIC/*`, `/BI0/*`) or ECC transactional tables?

| Option | Description | Table Naming |
|--------|-------------|--------------|
| **A) BW-on-HANA** | InfoCubes migrated to HANA | `/BIC/FZSAPLOM`, `/BI0/DPLANT` |
| **B) ECC Tables** | Classic ECC tables | `MARA`, `T001W`, `VBAK` |
| **C) Hybrid** | Mix of both | Requires catalog per InfoCube |

**CURRENT ANSWER**: `C) Hybrid` - InfoCube catalog specifies source type per cube

### Decision 3: Required CV Dialect/Version
**Question**: Which HANA Calculation View XML schema to target?

| Version | Namespace | Key Features |
|---------|-----------|--------------|
| **2.3** | `Calculation:scenario` | Current HANA 2.0 SPS03+ |
| **3.0** | `Calculation:scenario` | HANA Cloud |

**CURRENT ANSWER**: `schemaVersion="2.3"` (matches existing validated CVs in repo)

**IMPORTANT**: The repo uses `Calculation:scenario` namespace with `schemaVersion="2.3"`, NOT `View:ColumnView`. See reference: `Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview`

### Decision 4: Variable Types to Support (MVP)
**Question**: Which BEx variable types are in MVP scope?

| Variable Type | VARTYP | MVP Support |
|---------------|--------|-------------|
| Characteristic Value | 1 | **YES** |
| Hierarchy Node | 2 | NO |
| Text | 3 | NO |
| Formula | 4 | NO |
| Hierarchy | 5 | NO |
| Authorization | 6 | NO |

**CURRENT ANSWER**: MVP supports VARTYP=1 (Characteristic Value Variables) only

### Decision 5: Filter Operators to Support (MVP)
**Question**: Which range operators (G_T_RANGE.OPT) are in MVP scope?

| Operator | Meaning | MVP Support |
|----------|---------|-------------|
| EQ | Equal | **YES** |
| NE | Not Equal | **YES** |
| BT | Between | **YES** |
| NB | Not Between | NO |
| CP | Contains Pattern | Phase 2 |
| NP | Not Contains Pattern | NO |
| GE | Greater or Equal | **YES** |
| GT | Greater Than | **YES** |
| LE | Less or Equal | **YES** |
| LT | Less Than | **YES** |

**CURRENT ANSWER**: MVP supports EQ, NE, BT, GE, GT, LE, LT

### Decision 6: Key Figure Complexity (MVP)
**Question**: What key figure types are in MVP scope?

| Type | DEFTP | Description | MVP Support |
|------|-------|-------------|-------------|
| KYF | Basic Key Figure | Direct InfoObject reference | **YES** |
| CKF | Calculated Key Figure | Formula-based | NO |
| RKF | Restricted Key Figure | Filtered aggregation | NO |

**CURRENT ANSWER**: MVP supports KYF only; CKF/RKF emit STUB with warning

### Decision 7: CV-to-CDS Strategy
**Question**: Should CDS output wrap an activated CV or rebuild from scratch?

| Strategy | Description | Pros | Cons |
|----------|-------------|------|------|
| **A) Wrapper** | CDS consumes existing CV | Simple, CV handles logic | Requires deployed CV |
| **B) Rebuild** | CDS regenerates full logic | Standalone, no CV dependency | Complex expression translation |

**CURRENT ANSWER**: `A) Wrapper` for MVP - CDS views consume deployed Calculation Views

```abap
-- Wrapper approach example
define view ZI_WRAPPER as select from "CV_ZSAPLOM"
{
  PLANT,
  MATERIAL,
  QUANTITY
}
```

### Decision 8: ABAP CDS Constraints
**Question**: What ABAP-specific constraints apply?

| Constraint | Decision |
|------------|----------|
| Extra DDIC objects allowed? | NO - CDS only, no SE11 domains/elements |
| View naming convention | `ZI_` prefix for interface views |
| Max view name length | 30 characters |
| Access Control | `@AccessControl.authorizationCheck: #NOT_REQUIRED` (MVP) |

**CURRENT ANSWER**: Pure CDS, no DDIC dependencies, ZI_ prefix

### Decision 9: CAP CDS Runtime Expectation
**Question**: What CAP CDS runtime is targeted?

| Runtime | Description |
|---------|-------------|
| **Node.js** | Default CAP runtime |
| **Java** | CAP Java SDK |
| **None** | Schema definition only |

**CURRENT ANSWER**: Schema definition only (no runtime-specific code)

### Decision 10: Available Validation Environments
**Question**: What environments are available for validation?

| Environment | Available | Used For |
|-------------|-----------|----------|
| HANA Studio | **YES** | CV activation, SQL execution |
| ADT (ABAP Development Tools) | **YES** | ABAP CDS syntax check |
| CAP CLI (`cds compile`) | **YES** | CAP CDS validation |
| HANA Cloud | NO | Not available |
| S/4HANA Sandbox | LIMITED | Manual ABAP CDS deployment |

**CURRENT ANSWER**: HANA Studio (primary), ADT (ABAP CDS), `cds compile` (CAP)

---

## Scope & Assumptions

### MVP Scope (What IS Included)

| Category | Included Features |
|----------|-------------------|
| **BEx Elements** | Variables (VARTYP=1), Selections (CHA), Basic Key Figures (KYF) |
| **Operators** | EQ, NE, BT, GE, GT, LE, LT |
| **CV Nodes** | Projection, Aggregation (single source) |
| **CV Features** | Input Parameters, Filter Expressions, Basic Calculated Columns |
| **CDS Outputs** | Wrapper views consuming activated CVs |
| **Validation** | HANA Studio activation, `cds compile` for CAP |

### Non-Goals (Explicitly OUT of Scope for MVP)

| Category | Excluded Features | Future Phase |
|----------|-------------------|--------------|
| **BEx Elements** | Hierarchies, Hierarchy Variables, Authorization Variables | Phase 3 |
| **Key Figures** | Calculated KF (CKF), Restricted KF (RKF), Formulas | Phase 3 |
| **Operators** | CP (pattern), NP, NB | Phase 2 |
| **CV Nodes** | Join, Union, Rank, Graph | Phase 3 |
| **CV Features** | Star Joins, Currency Conversion, Unit Conversion | Phase 3 |
| **CDS** | Full rebuild from IR (non-wrapper) | Phase 4 |
| **Runtime** | OData exposure, Fiori integration | Out of scope |

### Fail vs Warn vs Stub Policy

**CRITICAL**: Every unsupported element MUST produce explicit output. No silent behavior.

| Condition | Behavior | Report Category |
|-----------|----------|-----------------|
| **Unknown BEx element type** | **FAIL** with error | `UNSUPPORTED_FATAL` |
| **Unsupported VARTYP (2-6)** | **STUB** parameter with warning | `UNSUPPORTED_STUB` |
| **Unsupported operator (CP, NP)** | **WARN** + generate placeholder | `UNSUPPORTED_WARN` |
| **CKF/RKF key figure** | **STUB** with `0 as MEASURE_NAME` | `UNSUPPORTED_STUB` |
| **Missing InfoObject mapping** | **WARN** + use raw name | `MAPPING_DEFAULT` |
| **Missing table mapping** | **WARN** + use InfoCube name | `MAPPING_DEFAULT` |

**Stub Generation Example**:
```xml
<!-- CKF stub: Original formula: QUANTITY * PRICE -->
<viewAttribute id="CALC_AMOUNT">
  <calculatedViewAttribute>
    <!-- STUB: Calculated Key Figure not supported in MVP -->
    <formula>0</formula>
  </calculatedViewAttribute>
</viewAttribute>
```

---

## Project Context

### What is xsodus_converter?

A **multi-pipeline SAP data conversion system** that converts various SAP artifacts to different targets:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      xsodus_converter Monorepo                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │  xml-to-sql  │    │  bex-to-cv   │    │  cv-to-cds   │           │
│  │   (MATURE)   │    │   (NEW)      │    │   (NEW)      │           │
│  │              │    │              │    │              │           │
│  │ CV XML → SQL │    │ BEx XML → CV │    │ CV XML → CDS │           │
│  │              │    │     XML      │    │     DDL      │           │
│  │ 15 XMLs      │    │              │    │              │           │
│  └──────────────┘    └──────────────┘    └──────────────┘           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### CV XML Dialect (CORRECTED)

**The repository uses `Calculation:scenario` with `schemaVersion="2.3"`**, not `View:ColumnView`.

Reference implementation: `Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Calculation:scenario
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:AccessControl="http://www.sap.com/ndb/SQLCoreModelAccessControl.ecore"
    xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"
    schemaVersion="2.3"
    id="DATA_SOURCES"
    applyPrivilegeType="NONE"
    checkAnalyticPrivileges="false"
    defaultClient="400"
    defaultLanguage="$$language$$"
    dataCategory="DIMENSION"
    enforceSqlExecution="false"
    outputViewType="Projection">
```

**Key attributes for generated CVs**:
- `schemaVersion="2.3"` (not 3.0)
- `xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"`
- `xmlns:AccessControl="http://www.sap.com/ndb/SQLCoreModelAccessControl.ecore"` (for filters)
- `dataCategory` = `CUBE` (for BEx with measures) or `DIMENSION`
- `outputViewType` = `Aggregation` (if measures) or `Projection`

### Repository Structure

```
xsodus_converter/
├── .claude/                           # AI assistant rules (18 mandatory rules)
│   ├── CLAUDE.md
│   ├── MANDATORY_PROCEDURES.md
│   └── SDLC_MASTER_PROCEDURE.md
│
├── core/                              # Shared library (x2s_core)
│   └── src/x2s_core/
│
├── pipelines/
│   ├── xml-to-sql/                    # MATURE - 15 XMLs validated
│   │   ├── src/xml_to_sql/
│   │   │   └── sql/renderer.py        # 1800+ lines, battle-tested
│   │   ├── catalog/hana/data/
│   │   │   ├── functions.yaml
│   │   │   └── patterns.yaml
│   │   ├── GOLDEN_COMMIT.yaml
│   │   └── docs/SOLVED_BUGS.md        # 40+ solved bugs
│   │
│   ├── bex-to-cv/                     # NEW - Phase 2 Complete
│   │   ├── src/bex_to_cv/
│   │   │   ├── parser/bex_parser.py   # Created
│   │   │   ├── domain/models.py       # Created
│   │   │   ├── renderer/cv_renderer.py # NEEDS DIALECT FIX
│   │   │   └── catalog/               # Created
│   │   ├── GOLDEN_COMMIT.yaml
│   │   └── docs/BUG_TRACKER.md
│   │
│   └── cv-to-cds/                     # NEW - Skeleton only
│       ├── src/cv_to_cds/
│       ├── GOLDEN_COMMIT.yaml
│       └── docs/BUG_TRACKER.md
│
├── Source (ABAP Programs)/
│   └── DATA_SOURCE/
│       └── DATA_SOURCES.calculationview  # Reference CV format
│
└── Source (XML Files)/
    └── BW_BEX_XML_VIEWS/
        └── 00O2TN3NK6BZ1GA7XWO79QYF4.xml  # Sample BEx XML
```

---

## SAP Ecosystem Background

### Understanding the Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SAP BW/BI Data Architecture                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SAP BW (Legacy)           SAP HANA              Modern Targets          │
│  ┌──────────────┐         ┌──────────────┐      ┌──────────────┐        │
│  │              │         │              │      │              │        │
│  │  BEx Query   │  ───►   │ Calculation  │ ───► │  CDS View    │        │
│  │   (XML)      │ bex-to  │    View      │ cv-  │  (ABAP/CAP)  │        │
│  │              │   -cv   │   (XML)      │ to-  │              │        │
│  │ asx:abap ns  │         │ Calculation: │ cds  │              │        │
│  │              │         │   scenario   │      │              │        │
│  │              │         │ v2.3         │      │              │        │
│  └──────────────┘         └──────────────┘      └──────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Physical Data Model Decision

**Question**: Where do the physical tables come from?

| Source Type | Table Pattern | Example | Catalog Needed |
|-------------|---------------|---------|----------------|
| **BW-on-HANA InfoCube** | `/BIC/F<CUBE>` | `/BIC/FZSAPLOM` | InfoCube → fact table |
| **BW-on-HANA DSO** | `/BIC/A<DSO>00` | `/BIC/AZSALES00` | DSO → active table |
| **BW InfoObject Master Data** | `/BI0/P<IOBJNM>` | `/BI0/PPLANT` | InfoObject → P-table |
| **BW InfoObject Text** | `/BI0/T<IOBJNM>` | `/BI0/TPLANT` | InfoObject → T-table |
| **ECC Table** | Standard name | `T001W`, `MARA` | Direct mapping |

**Current Implementation**: Uses `table_mappings.yaml` per InfoCube:

```yaml
table_mappings:
  - infocube: "ZSAPLOM"
    source_type: "BW_INFOCUBE"  # or "ECC_TABLE"
    schema: "SAPABAP1"
    fact_table: "/BIC/FZSAPLOM"  # or "ZSAPLOM" for ECC
    dimension_tables:
      "0PLANT": "/BI0/PPLANT"    # BW master data
      "0MATERIAL": "MARA"        # ECC table (hybrid)
```

---

## Support Matrices

### BEx Feature Support Matrix

| Feature | XML Section | Field | MVP | Phase 2 | Phase 3 |
|---------|-------------|-------|-----|---------|---------|
| **Query Metadata** | G_S_RKB1D | COMPID, INFOCUBE | YES | - | - |
| **Element Directory** | G_T_ELTDIR | DEFTP, MAPNAME | YES | - | - |
| **Char Variables (VARTYP=1)** | G_T_GLOBV | VNAM, IOBJNM, VPARSEL | YES | - | - |
| **Hierarchy Variables (VARTYP=2)** | G_T_GLOBV | | NO | NO | YES |
| **Selections (CHA)** | G_T_SELECT | IOBJNM, CHANM | YES | - | - |
| **Basic Key Figures (KYF)** | G_T_RANGE | IOBJNM, SELTP=6 | YES | - | - |
| **Calculated Key Figures (CKF)** | G_T_CALC | | STUB | STUB | YES |
| **Restricted Key Figures (RKF)** | G_T_RANGE + formula | | STUB | STUB | YES |
| **Range Filter (EQ)** | G_T_RANGE | OPT=EQ | YES | - | - |
| **Range Filter (BT)** | G_T_RANGE | OPT=BT | YES | - | - |
| **Range Filter (CP pattern)** | G_T_RANGE | OPT=CP | WARN | YES | - |
| **Variable Reference in Range** | G_T_RANGE | LOWFLAG=3 | YES | - | - |
| **Hierarchies** | G_T_HIERSEL | | NO | NO | YES |
| **Conditions** | G_T_COND | | NO | NO | YES |
| **Exceptions** | G_T_EXCEPT | | NO | NO | NO |

### CV Feature Support Matrix (Output)

| Feature | CV Element | MVP | Phase 2 | Phase 3 |
|---------|------------|-----|---------|---------|
| **Schema Version** | `schemaVersion="2.3"` | YES | - | - |
| **Data Source (Table)** | `<DataSource type="DATA_BASE_TABLE">` | YES | - | - |
| **Data Source (CV)** | `<DataSource type="CALCULATION_VIEW">` | NO | YES | - |
| **Projection Node** | `xsi:type="Calculation:ProjectionView"` | YES | - | - |
| **Aggregation Node** | `xsi:type="Calculation:AggregationView"` | YES | - | - |
| **Join Node** | `xsi:type="Calculation:JoinView"` | NO | YES | - |
| **Union Node** | `xsi:type="Calculation:UnionView"` | NO | YES | - |
| **Rank Node** | `xsi:type="Calculation:RankView"` | NO | NO | YES |
| **Input Parameters** | `<localVariables><variable parameter="true">` | YES | - | - |
| **Simple Filter** | `<filter xsi:type="AccessControl:SingleValueFilter">` | YES | - | - |
| **List Filter** | `<filter xsi:type="AccessControl:ListValueFilter">` | NO | YES | - |
| **Calculated Columns** | `<calculatedViewAttributes>` | BASIC | YES | - |
| **Star Join (Dimension Lookup)** | Multiple data sources + join | NO | YES | - |
| **Currency Conversion** | `<currencyConversion>` | NO | NO | YES |

### CDS Target Support Matrix

| Feature | ABAP CDS | CAP CDS | MVP |
|---------|----------|---------|-----|
| **Wrapper View (consume CV)** | YES | N/A | YES |
| **Parameters** | `with parameters` | N/A | YES |
| **Basic Types** | abap.char, abap.dec | String, Decimal | YES |
| **Aggregation Annotations** | `@DefaultAggregation` | N/A | YES |
| **Associations** | `association to` | `association to` | NO |
| **Full Rebuild (no CV)** | select from tables | entity definition | NO |

---

## Pipeline 1: BEx XML → HANA Calculation View

### 1.1 Correct CV XML Output Format

**Target Format** (schemaVersion 2.3):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Calculation:scenario
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:AccessControl="http://www.sap.com/ndb/SQLCoreModelAccessControl.ecore"
    xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"
    schemaVersion="2.3"
    id="CV_ZSAPLOM_REP_XS"
    applyPrivilegeType="NONE"
    checkAnalyticPrivileges="false"
    defaultClient="$$client$$"
    defaultLanguage="$$language$$"
    dataCategory="CUBE"
    enforceSqlExecution="false"
    outputViewType="Aggregation">

  <origin/>
  <descriptions defaultDescription="BEx Query: ZSAPLOM_REP_XS"/>

  <metadata activatedAt="2026-02-01T00:00:00.0" changedAt="2026-02-01T00:00:00.0"/>

  <localVariables>
    <variable id="IP_PLANT" parameter="true">
      <descriptions defaultDescription="Plant"/>
      <variableProperties mandatory="true" datatype="NVARCHAR" length="4"/>
    </variable>
  </localVariables>

  <variableMappings/>

  <dataSources>
    <DataSource id="ZSAPLOM" type="DATA_BASE_TABLE">
      <viewAttributes allViewAttributes="true"/>
      <columnObject schemaName="SAPABAP1" columnObjectName="ZSAPLOM"/>
    </DataSource>
  </dataSources>

  <calculationViews>
    <calculationView xsi:type="Calculation:ProjectionView" id="Projection_1">
      <descriptions/>
      <viewAttributes>
        <viewAttribute id="WERKS"/>
        <viewAttribute id="MATNR"/>
        <viewAttribute id="QUANTITY"/>
      </viewAttributes>
      <calculatedViewAttributes/>
      <input node="#ZSAPLOM">
        <mapping xsi:type="Calculation:AttributeMapping" target="WERKS" source="WERKS"/>
        <mapping xsi:type="Calculation:AttributeMapping" target="MATNR" source="MATNR"/>
        <mapping xsi:type="Calculation:AttributeMapping" target="QUANTITY" source="QUANTITY"/>
      </input>
      <filter xsi:type="AccessControl:SingleValueFilter" including="true" value="$$IP_PLANT$$">
        <attributeName>WERKS</attributeName>
      </filter>
    </calculationView>
  </calculationViews>

  <logicalModel id="Projection_1">
    <descriptions/>
    <attributes>
      <attribute id="WERKS" order="1" attributeHierarchyActive="false" displayAttribute="false">
        <descriptions defaultDescription="Plant"/>
        <keyMapping columnObjectName="Projection_1" columnName="WERKS"/>
      </attribute>
      <attribute id="MATNR" order="2" attributeHierarchyActive="false" displayAttribute="false">
        <descriptions defaultDescription="Material"/>
        <keyMapping columnObjectName="Projection_1" columnName="MATNR"/>
      </attribute>
    </attributes>
    <calculatedAttributes/>
    <privateDataFoundation>
      <tableProxies/>
      <joins/>
      <layout><shapes/></layout>
    </privateDataFoundation>
    <baseMeasures>
      <measure id="QUANTITY" order="3" aggregationType="sum" measureType="simple">
        <descriptions defaultDescription="Quantity"/>
        <measureMapping columnObjectName="Projection_1" columnName="QUANTITY"/>
      </measure>
    </baseMeasures>
    <calculatedMeasures/>
    <restrictedMeasures/>
    <localDimensions/>
  </logicalModel>

  <layout>
    <shapes>
      <shape expanded="true" modelObjectName="Output" modelObjectNameSpace="MeasureGroup">
        <upperLeftCorner x="100" y="100"/>
        <rectangleSize height="0" width="0"/>
      </shape>
      <shape expanded="true" modelObjectName="Projection_1" modelObjectNameSpace="CalculationView">
        <upperLeftCorner x="100" y="200"/>
        <rectangleSize height="-1" width="-1"/>
      </shape>
    </shapes>
  </layout>
</Calculation:scenario>
```

### 1.2 Key Differences from Current Implementation

| Aspect | Current (WRONG) | Corrected |
|--------|-----------------|-----------|
| Filter format | `<filter><expression>...</expression>` | `<filter xsi:type="AccessControl:SingleValueFilter">` |
| Data source reference | `<resourceUri>SCHEMA.TABLE</resourceUri>` | `<columnObject schemaName="..." columnObjectName="..."/>` |
| Input node reference | `node="fact_table"` | `node="#ZSAPLOM"` (hash prefix) |
| Attribute mapping | Implicit | Explicit `<mapping xsi:type="Calculation:AttributeMapping">` |
| Logical model reference | `id="CV_NAME"` | `id="Projection_1"` (node name) |
| Key mapping | `columnObjectName="Projection_1"` | Same (already correct) |

---

## BEx Cross-Linking Specification

### G_T_RANGE.LOW Cross-Reference to G_T_GLOBV.VARUNIID

**CRITICAL**: The `LOW` field in G_T_RANGE may contain a **variable reference**, not a literal value.

**Detection Logic**:
```
IF G_T_RANGE.LOWFLAG = 3 THEN
    G_T_RANGE.LOW contains VARUNIID (reference to G_T_GLOBV.VARUNIID)
ELSE IF G_T_RANGE.LOWFLAG = 1 THEN
    G_T_RANGE.LOW contains literal value
END IF
```

**Example from sample XML** (`00O2TN3NK6BZ1GA7XWO79QYF4.xml`):

```xml
<!-- G_T_RANGE entry -->
<item>
  <ELTUID>00O2TN3NK6BZ1GA7XNZ7G9SQO</ELTUID>  <!-- Links to G_T_ELTDIR -->
  <IOBJNM>0PLANT</IOBJNM>
  <SELTP>1</SELTP>                             <!-- 1=Mandatory selection -->
  <SIGN>I</SIGN>
  <OPT>EQ</OPT>
  <LOW>00O2THGY17LMBCG83S2CYZ4MY</LOW>         <!-- VARUNIID reference! -->
  <LOWFLAG>3</LOWFLAG>                          <!-- 3=Variable reference -->
</item>

<!-- Corresponding G_T_GLOBV entry -->
<item>
  <VARUNIID>00O2THGY17LMBCG83S2CYZ4MY</VARUNIID>  <!-- Matches LOW above -->
  <VNAM>VAR_PLANT</VNAM>
  <IOBJNM>0PLANT</IOBJNM>
  <VPARSEL>M</VPARSEL>                            <!-- M=Multiple selection -->
  <VARINPUT>X</VARINPUT>                          <!-- X=User input -->
</item>
```

### LOWFLAG Mapping Table

| LOWFLAG | Meaning | LOW Contains |
|---------|---------|--------------|
| 0 | Empty | Nothing |
| 1 | Literal value | Actual filter value |
| 2 | Hierarchy node | Node ID |
| 3 | Variable reference | VARUNIID |
| 4 | Formula | Formula reference |

### SELTP Mapping Table

| SELTP | Meaning | Behavior |
|-------|---------|----------|
| 1 | Mandatory selection | Variable must have value |
| 2 | Selection | Standard characteristic |
| 4 | Optional selection | Variable can be empty |
| 6 | Key Figure selection | Literal InfoObject name in LOW |

### SIGN and OPT Mapping

| SIGN | Meaning |
|------|---------|
| I | Include (AND with other I ranges, OR within same ELTUID) |
| E | Exclude (AND NOT) |

| OPT | Meaning | SQL Equivalent |
|-----|---------|----------------|
| EQ | Equal | `= value` |
| NE | Not Equal | `<> value` |
| BT | Between | `BETWEEN low AND high` |
| NB | Not Between | `NOT BETWEEN low AND high` |
| CP | Contains Pattern | `LIKE pattern` (with wildcard translation) |
| NP | Not Contains Pattern | `NOT LIKE pattern` |
| GE | Greater or Equal | `>= value` |
| GT | Greater Than | `> value` |
| LE | Less or Equal | `<= value` |
| LT | Less Than | `< value` |

### Parser Implementation Update Required

```python
def _resolve_range_value(self, range_item: Dict, variables: Dict[str, BExVariable]) -> Tuple[str, bool]:
    """Resolve LOW value, handling variable references.

    Returns:
        (resolved_value, is_variable_reference)
    """
    low = range_item.get('LOW', '')
    lowflag = int(range_item.get('LOWFLAG', '0'))

    if lowflag == 3:  # Variable reference
        varuniid = low
        variable = next(
            (v for v in variables.values() if v.element_uid == varuniid),
            None
        )
        if variable:
            return (variable.to_input_parameter_name(), True)
        else:
            self.warnings.append(f"Variable reference {varuniid} not found")
            return (low, False)
    elif lowflag == 1:  # Literal value
        return (low, False)
    else:
        return (low, False)
```

---

## Stage Gates

### Gate 0: Prerequisites (Entry)

**Entry Criteria**:
- [ ] Sample BEx XML available and readable
- [ ] Reference CV XML format verified (schemaVersion 2.3)
- [ ] HANA Studio connection confirmed
- [ ] InfoObject catalog populated (minimum 10 InfoObjects)

**Exit Artifacts**:
- Sample BEx XML parsed without errors
- InfoObject catalog YAML created

### Gate 1: Parser Complete

**Entry Criteria**:
- Gate 0 complete

**Exit Criteria**:
- [ ] BEx parser parses all G_T_* sections
- [ ] Cross-linking (LOWFLAG=3) resolved correctly
- [ ] BExQuery IR fully populated
- [ ] Parse warnings captured (no silent failures)

**Exit Artifacts**:
- `golden_ir/ZSAPLOM_REP_XS.json` - Serialized IR for regression
- Conversion report showing parsed elements

### Gate 2: CV Renderer Complete

**Entry Criteria**:
- Gate 1 complete
- Correct CV XML format documented

**Exit Criteria**:
- [ ] CV XML generated matches schemaVersion 2.3 format
- [ ] All attributes/filters use correct namespace prefixes
- [ ] Input parameters generated from variables
- [ ] All unsupported features produce stubs with warnings

**Exit Artifacts**:
- `golden_output/CV_ZSAPLOM_REP_XS.hdbcalculationview` - Reference output
- Conversion report with mapped/defaulted/skipped/stubbed counts

### Gate 3: CV Activation (HANA Validation)

**Entry Criteria**:
- Gate 2 complete
- Generated CV XML available

**Exit Criteria**:
- [ ] CV imports into HANA Studio without errors
- [ ] CV activates successfully
- [ ] CV appears in HANA catalog
- [ ] Basic SELECT against CV executes (with dummy parameter values)

**Exit Artifacts**:
- HANA activation log (success)
- SQL execution proof (screenshot or log)
- GOLDEN_COMMIT.yaml entry

### Gate 4: CV-to-CDS Parser Complete

**Entry Criteria**:
- Gate 3 complete OR validated CV from xml-to-sql pipeline

**Exit Criteria**:
- [ ] CV parser reads schemaVersion 2.3 CVs
- [ ] CDSView IR fully populated
- [ ] Parameter types mapped correctly

**Exit Artifacts**:
- `golden_ir/CV_EXAMPLE_cds.json` - Serialized CDS IR

### Gate 5: CDS Renderer Complete

**Entry Criteria**:
- Gate 4 complete

**Exit Criteria**:
- [ ] ABAP CDS wrapper syntax correct
- [ ] CAP CDS entity syntax correct
- [ ] `cds compile` passes for CAP output

**Exit Artifacts**:
- `golden_output/ZI_EXAMPLE.cds.txt` - ABAP CDS
- `golden_output/Example.cds` - CAP CDS
- Conversion report

### Gate 6: End-to-End Validation

**Entry Criteria**:
- Gates 1-5 complete

**Exit Criteria**:
- [ ] BEx → CV → CDS chain executes without errors
- [ ] All conversion reports complete
- [ ] No unhandled edge cases in sample XMLs

**Exit Artifacts**:
- Complete conversion report for each sample XML
- GOLDEN_COMMIT.yaml fully populated

---

## Conversion Report Specification

### Report Format (REQUIRED for every conversion)

Every conversion MUST produce a structured report. No silent behavior.

```yaml
# conversion_report.yaml
conversion:
  input_file: "00O2TN3NK6BZ1GA7XWO79QYF4.xml"
  output_file: "CV_ZSAPLOM_REP_XS.hdbcalculationview"
  timestamp: "2026-02-01T10:30:00Z"
  status: "SUCCESS_WITH_WARNINGS"  # SUCCESS | SUCCESS_WITH_WARNINGS | FAILED

summary:
  total_elements: 12
  mapped: 8
  defaulted: 2
  stubbed: 1
  skipped: 1
  unsupported_fatal: 0

elements:
  mapped:
    - element: "VAR_PLANT"
      type: "Variable"
      source: "G_T_GLOBV"
      target: "IP_PLANT"
      category: "MAPPED"

    - element: "0PLANT"
      type: "Selection"
      source: "G_T_SELECT"
      target: "WERKS"
      category: "MAPPED"
      note: "Resolved via InfoObject catalog"

  defaulted:
    - element: "0MRP_AREA"
      type: "Selection"
      source: "G_T_SELECT"
      target: "MRP_AREA"  # Used raw name
      category: "MAPPING_DEFAULT"
      warning: "No InfoObject mapping found, using raw InfoObject name"

  stubbed:
    - element: "CALC_AMOUNT"
      type: "CalculatedKeyFigure"
      source: "G_T_CALC"
      target: "0 as CALC_AMOUNT"
      category: "UNSUPPORTED_STUB"
      warning: "Calculated Key Figures not supported in MVP"

  skipped:
    - element: "Hierarchy_1"
      type: "Hierarchy"
      source: "G_T_HIERSEL"
      target: null
      category: "SKIPPED"
      warning: "Hierarchies not supported"

warnings:
  - "No InfoObject mapping found for 0MRP_AREA, using raw name"
  - "Calculated Key Figure CALC_AMOUNT stubbed with 0"
  - "Hierarchy Hierarchy_1 skipped"

errors: []
```

### Report Categories

| Category | Code | Description |
|----------|------|-------------|
| Mapped | `MAPPED` | Successfully translated with catalog lookup |
| Defaulted | `MAPPING_DEFAULT` | Used fallback (raw name, default type) |
| Stubbed | `UNSUPPORTED_STUB` | Placeholder generated with warning |
| Skipped | `SKIPPED` | Element ignored (logged) |
| Unsupported Fatal | `UNSUPPORTED_FATAL` | Conversion aborted |
| Warning | `WARN` | Non-fatal issue logged |

---

## Verification Strategy (Tiered)

### Tier 1: Automated Invariants (MANDATORY)

These checks run automatically on every conversion:

| Check | Tool | Pass Criteria |
|-------|------|---------------|
| XML well-formed | `lxml.etree.parse()` | No parse errors |
| Schema version | Regex | `schemaVersion="2.3"` present |
| Required elements | XPath | `<dataSources>`, `<calculationViews>`, `<logicalModel>` exist |
| No empty IDs | XPath | All `id` attributes non-empty |
| Node references valid | Custom | All `node="#X"` have matching `<calculationView id="X">` |
| CDS syntax | `cds compile --to json` | Exit code 0 (CAP only) |
| Conversion report complete | YAML parse | All sections present |

### Tier 2: Environment Validation (RECOMMENDED)

Requires access to validation environment:

| Check | Environment | Pass Criteria |
|-------|-------------|---------------|
| CV activates | HANA Studio | Activation completes without error |
| CV queryable | HANA SQL | `SELECT * FROM "CV_NAME" LIMIT 1` returns (with params) |
| ABAP CDS syntax | ADT | Syntax check passes |

### Tier 3: Limited Parity (OPTIONAL, MVP scope only)

Only within MVP scope (structural, not semantic):

| Check | Description | Pass Criteria |
|-------|-------------|---------------|
| Column count | CV columns match BEx selections + key figures | Counts equal |
| Parameter count | CV parameters match BEx input variables | Counts equal |
| Filter presence | Variables with ranges have filter expressions | Filters exist |

**NOT in scope for MVP**:
- Result set comparison
- Aggregation accuracy
- Currency/unit conversion parity

---

## Implementation Phases

### Phase 1: Foundation COMPLETE
- [x] Create folder structures
- [x] Initialize pyproject.toml
- [x] Create GOLDEN_COMMIT.yaml and BUG_TRACKER.md

### Phase 2: BEx Parser & Renderer COMPLETE (NEEDS UPDATES)
- [x] Implement bex_parser.py
- [x] Create domain models
- [x] Create InfoObject catalog
- [x] Implement cv_renderer.py
- [ ] **FIX**: Update cv_renderer.py to use schemaVersion 2.3 format
- [ ] **FIX**: Add AccessControl namespace for filters
- [ ] **ADD**: LOWFLAG=3 variable reference resolution
- [ ] **ADD**: Conversion report generation

### Phase 3: CV Validation & Enhancement PENDING
- [ ] Validate generated CV in HANA Studio
- [ ] Fix any activation errors
- [ ] Add Join/Union support
- [ ] Add calculated column support
- [ ] Write unit tests

### Phase 4: CV-to-CDS Parser PENDING
- [ ] Create cv_parser.py for schemaVersion 2.3
- [ ] Create CDS domain models
- [ ] Implement type mapping

### Phase 5: CDS Renderers PENDING
- [ ] Implement ABAP CDS wrapper renderer
- [ ] Implement CAP CDS entity renderer
- [ ] Validate with `cds compile`

### Phase 6: Web API & CLI PENDING
- [ ] Create FastAPI routes
- [ ] Build Typer CLI
- [ ] Implement conversion report export

### Phase 7: Documentation & Golden Commit PENDING
- [ ] Complete end-to-end testing
- [ ] Populate GOLDEN_COMMIT.yaml
- [ ] Document all conversion rules

---

## Known Risks & Mitigations

### Risk 1: CV XML Format Mismatch (HIGH)
**Risk**: Current cv_renderer.py generates incorrect XML format.
**Mitigation**: Phase 2 updates MUST fix format before Gate 3.

### Risk 2: InfoObject Resolution Gaps (MEDIUM)
**Risk**: Missing InfoObject mappings for customer-specific objects.
**Mitigation**: MAPPING_DEFAULT behavior with explicit warning in report.

### Risk 3: Complex BEx Structures (LOW for MVP)
**Risk**: CKF/RKF/Hierarchies not supported.
**Mitigation**: UNSUPPORTED_STUB with 0 placeholder, documented in report.

### Risk 4: HANA Version Compatibility (LOW)
**Risk**: schemaVersion 2.3 may not work on older HANA.
**Mitigation**: User has HANA 2.0 SPS03+ (verified with xml-to-sql pipeline).

---

## Summary for Reviewing Agent

### What Has Been Done
1. Complete folder structure for both pipelines
2. Domain models with dataclasses and enums
3. BEx parser handling G_T_* sections
4. CV renderer (NEEDS FORMAT FIX)
5. InfoObject catalog with 25+ mappings
6. Bug tracking infrastructure

### What Needs Immediate Fix
1. **cv_renderer.py**: Update to schemaVersion 2.3 format
2. **bex_parser.py**: Add LOWFLAG=3 variable reference resolution
3. **Both**: Add conversion report generation

### Critical Review Points
1. Is the schemaVersion 2.3 format correctly documented?
2. Is the LOWFLAG cross-linking logic correct?
3. Is the fail/warn/stub policy complete?
4. Are the 10 decisions reasonable for MVP?
5. Are the stage gates achievable?

### Files to Review
- `pipelines/bex-to-cv/src/bex_to_cv/parser/bex_parser.py` - 280 lines
- `pipelines/bex-to-cv/src/bex_to_cv/renderer/cv_renderer.py` - 340 lines (NEEDS UPDATE)
- `Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview` - Reference format
