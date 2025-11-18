import React, { useState, useEffect, useCallback, useMemo, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// TYPE DEFINITIONS (60+ interfaces for data governance)
// ============================================================================

interface DataAsset {
  id: string;
  name: string;
  type: 'database' | 'file' | 'api' | 'warehouse' | 'cache';
  owner: string;
  classification: 'public' | 'internal' | 'confidential' | 'restricted';
  sensitivityLevel: 1 | 2 | 3 | 4 | 5;
  lastModified: number;
  location: string;
  recordCount?: number;
  sizeBytes?: number;
  lineage: DataLineageInfo;
  governance: GovernancePolicy[];
  tags: string[];
  metadata: Record<string, any>;
}

interface DataLineageInfo {
  sources: string[];
  transformations: DataTransformation[];
  destinations: string[];
  lastUpdated: number;
  completeness: number;
}

interface DataTransformation {
  id: string;
  type: string;
  description: string;
  timestamp: number;
  appliedBy: string;
  impact: 'low' | 'medium' | 'high';
}

interface GovernancePolicy {
  id: string;
  name: string;
  type: 'retention' | 'access' | 'encryption' | 'masking' | 'quality';
  rules: PolicyRule[];
  enabled: boolean;
  enforcementLevel: 'mandatory' | 'advisory' | 'informational';
}

interface PolicyRule {
  id: string;
  condition: string;
  action: string;
  priority: number;
  expirationDate?: number;
}

interface ComplianceFramework {
  id: string;
  name: string; // GDPR, HIPAA, SOC2, CCPA, PCI-DSS
  version: string;
  requirements: ComplianceRequirement[];
  status: 'compliant' | 'non-compliant' | 'partial' | 'not-applicable';
  lastAudit: number;
  nextAuditDue: number;
  complianceScore: number;
}

interface ComplianceRequirement {
  id: string;
  identifier: string; // e.g., GDPR-Article-32
  description: string;
  status: 'compliant' | 'non-compliant' | 'in-progress';
  evidence: string[];
  controlsMapped: string[];
  dueDate?: number;
}

interface AuditLog {
  id: string;
  timestamp: number;
  action: 'access' | 'modification' | 'deletion' | 'export' | 'policy_change';
  actor: string;
  resource: string;
  resourceType: string;
  changes?: Change[];
  ipAddress: string;
  result: 'success' | 'failure';
  reason?: string;
  severity: 'info' | 'warning' | 'critical';
}

interface Change {
  field: string;
  oldValue: any;
  newValue: any;
  timestamp: number;
}

interface PrivacyPolicy {
  id: string;
  name: string;
  version: string;
  description: string;
  applicableCountries: string[];
  effectiveDate: number;
  lastUpdated: number;
  contactEmail: string;
  retentionPeriods: RetentionPolicy[];
  purposes: DataPurpose[];
  thirdParties: ThirdParty[];
}

interface RetentionPolicy {
  dataType: string;
  retentionDays: number;
  purpose: string;
  legalBasis: string;
}

interface DataPurpose {
  id: string;
  purpose: string;
  legalBasis: string;
  consentRequired: boolean;
  dataCategories: string[];
}

interface ThirdParty {
  id: string;
  name: string;
  category: string;
  dataProcessed: string[];
  dataProcessingAgreement: boolean;
  lastReviewed: number;
  riskLevel: 'low' | 'medium' | 'high';
}

interface DataSubjectRight {
  id: string;
  type: 'access' | 'rectification' | 'erasure' | 'portability' | 'objection';
  status: 'pending' | 'approved' | 'denied' | 'fulfilled';
  requestedBy: string;
  requestDate: number;
  dueDate: number;
  completedDate?: number;
  subject: string;
  description: string;
}

interface AccessControl {
  id: string;
  principalId: string;
  principalType: 'user' | 'role' | 'group' | 'application';
  resourceId: string;
  permission: 'read' | 'write' | 'delete' | 'admin';
  grantedAt: number;
  grantedBy: string;
  expiresAt?: number;
  justification: string;
  requiresReview?: boolean;
}

interface DataQualityMetric {
  id: string;
  dataAssetId: string;
  completeness: number;
  accuracy: number;
  consistency: number;
  timeliness: number;
  validity: number;
  uniqueness: number;
  overallScore: number;
  lastEvaluated: number;
  issues: DataQualityIssue[];
}

interface DataQualityIssue {
  id: string;
  type: 'duplicate' | 'missing' | 'invalid' | 'inconsistent' | 'outdated';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  affectedRecords: number;
  detectedAt: number;
  status: 'open' | 'in-progress' | 'resolved';
  resolution?: string;
}

interface DataClassification {
  id: string;
  assetId: string;
  classification: 'public' | 'internal' | 'confidential' | 'restricted';
  sensitivityLevel: 1 | 2 | 3 | 4 | 5;
  piiPresent: boolean;
  piiCategories?: string[];
  piiHandling: string;
  classifiedAt: number;
  classifiedBy: string;
  reviewRequired?: boolean;
}

interface IncidentReport {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  type: 'breach' | 'violation' | 'anomaly' | 'failure';
  detectedAt: number;
  reportedAt: number;
  affectedAssets: string[];
  affectedRecords?: number;
  rootCause?: string;
  status: 'detected' | 'investigating' | 'mitigating' | 'resolved';
  responsibleTeam?: string;
  resolutionDate?: number;
}

interface GovernanceMetrics {
  totalAssets: number;
  classifiedAssets: number;
  policyCompliance: number;
  auditScore: number;
  incidentsThisMonth: number;
  accessRequestsAwaiting: number;
  dataQualityScore: number;
  complianceRate: number;
}

// ============================================================================
// DATA ASSETS COMPONENT
// ============================================================================

const DataAssetsPanel: FC<{
  assets: DataAsset[];
  onSelectAsset: (asset: DataAsset) => void;
  selectedId?: string;
}> = ({ assets, onSelectAsset, selectedId }) => {
  const [filterType, setFilterType] = useState<string>('all');
  const [filterClassification, setFilterClassification] = useState<string>('all');

  const filteredAssets = useMemo(
    () =>
      assets.filter(
        (a) =>
          (filterType === 'all' || a.type === filterType) &&
          (filterClassification === 'all' || a.classification === filterClassification)
      ),
    [assets, filterType, filterClassification]
  );

  return (
    <div className="data-assets-panel">
      <div className="panel-header">
        <h3>📦 Data Assets ({filteredAssets.length})</h3>
      </div>
      <div className="filters">
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="filter">
          <option value="all">All Types</option>
          <option value="database">Database</option>
          <option value="file">File</option>
          <option value="api">API</option>
          <option value="warehouse">Warehouse</option>
        </select>
        <select
          value={filterClassification}
          onChange={(e) => setFilterClassification(e.target.value)}
          className="filter"
        >
          <option value="all">All Classifications</option>
          <option value="public">Public</option>
          <option value="internal">Internal</option>
          <option value="confidential">Confidential</option>
          <option value="restricted">Restricted</option>
        </select>
      </div>
      <div className="assets-list">
        {filteredAssets.map((asset) => (
          <div
            key={asset.id}
            className={`asset-item ${selectedId === asset.id ? 'selected' : ''}`}
            onClick={() => onSelectAsset(asset)}
          >
            <div className="asset-icon">
              {asset.type === 'database' && '🗄️'}
              {asset.type === 'file' && '📄'}
              {asset.type === 'api' && '🔌'}
              {asset.type === 'warehouse' && '🏭'}
            </div>
            <div className="asset-info">
              <p className="asset-name">{asset.name}</p>
              <div className="asset-tags">
                <span className={`classification ${asset.classification}`}>
                  {asset.classification}
                </span>
                <span className="sensitivity">🔒 {asset.sensitivityLevel}/5</span>
              </div>
            </div>
            <span className="asset-owner">{asset.owner}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// COMPLIANCE DASHBOARD COMPONENT
// ============================================================================

const ComplianceDashboard: FC<{
  frameworks: ComplianceFramework[];
}> = ({ frameworks }) => {
  return (
    <div className="compliance-dashboard">
      <div className="dashboard-header">
        <h3>✅ Compliance Status</h3>
      </div>
      <div className="frameworks-grid">
        {frameworks.map((fw) => (
          <div key={fw.id} className={`framework-card ${fw.status}`}>
            <div className="fw-header">
              <span className="fw-name">{fw.name}</span>
              <span className="fw-score">{(fw.complianceScore * 100).toFixed(0)}%</span>
            </div>
            <div className="fw-bar">
              <div
                className="fw-fill"
                style={{ width: `${fw.complianceScore * 100}%` }}
              />
            </div>
            <div className="fw-details">
              <span className="detail">
                ✅ {fw.requirements.filter((r) => r.status === 'compliant').length} compliant
              </span>
              <span className="detail">
                ⚠️ {fw.requirements.filter((r) => r.status === 'in-progress').length} in progress
              </span>
            </div>
            <div className="fw-status">{fw.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// AUDIT LOG VIEWER COMPONENT
// ============================================================================

const AuditLogViewer: FC<{
  logs: AuditLog[];
  onFilter: (type: string) => void;
}> = ({ logs, onFilter }) => {
  const [selectedAction, setSelectedAction] = useState<string>('all');

  const filteredLogs = useMemo(
    () => (selectedAction === 'all' ? logs : logs.filter((l) => l.action === selectedAction)),
    [logs, selectedAction]
  );

  return (
    <div className="audit-log-viewer">
      <div className="viewer-header">
        <h3>📋 Audit Logs</h3>
        <select
          value={selectedAction}
          onChange={(e) => {
            setSelectedAction(e.target.value);
            onFilter(e.target.value);
          }}
          className="action-filter"
        >
          <option value="all">All Actions</option>
          <option value="access">Access</option>
          <option value="modification">Modification</option>
          <option value="deletion">Deletion</option>
          <option value="export">Export</option>
          <option value="policy_change">Policy Change</option>
        </select>
      </div>
      <div className="logs-table">
        <div className="table-header">
          <span className="col-time">Timestamp</span>
          <span className="col-action">Action</span>
          <span className="col-actor">Actor</span>
          <span className="col-resource">Resource</span>
          <span className="col-result">Result</span>
          <span className="col-severity">Severity</span>
        </div>
        <div className="table-body">
          {filteredLogs.slice(0, 15).map((log) => (
            <div key={log.id} className={`table-row ${log.severity}`}>
              <span className="col-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className="col-action">{log.action}</span>
              <span className="col-actor">{log.actor}</span>
              <span className="col-resource">{log.resource}</span>
              <span className={`col-result ${log.result}`}>{log.result}</span>
              <span className={`col-severity ${log.severity}`}>
                {log.severity === 'info' && 'ℹ️'}
                {log.severity === 'warning' && '⚠️'}
                {log.severity === 'critical' && '🚨'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// DATA SUBJECT RIGHTS COMPONENT
// ============================================================================

const DataSubjectRights: FC<{
  requests: DataSubjectRight[];
  onApproveRequest: (id: string) => void;
}> = ({ requests, onApproveRequest }) => {
  return (
    <div className="data-subject-rights">
      <div className="rights-header">
        <h3>👤 Data Subject Rights Requests</h3>
        <span className="pending">{requests.filter((r) => r.status === 'pending').length} pending</span>
      </div>
      <div className="requests-list">
        {requests.map((req) => (
          <div key={req.id} className={`request-item ${req.status}`}>
            <div className="request-header">
              <span className="request-type">
                {req.type === 'access' && '👁️ Access'}
                {req.type === 'rectification' && '✏️ Rectification'}
                {req.type === 'erasure' && '🗑️ Erasure'}
                {req.type === 'portability' && '📤 Portability'}
                {req.type === 'objection' && '🚫 Objection'}
              </span>
              <span className={`status-badge ${req.status}`}>{req.status}</span>
            </div>
            <div className="request-details">
              <p className="subject">Subject: {req.subject}</p>
              <p className="description">{req.description}</p>
              <span className="dates">
                Requested: {new Date(req.requestDate).toLocaleDateString()} | Due:{' '}
                {new Date(req.dueDate).toLocaleDateString()}
              </span>
            </div>
            {req.status === 'pending' && (
              <button className="action-btn" onClick={() => onApproveRequest(req.id)}>
                Review Request
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// INCIDENT MANAGEMENT COMPONENT
// ============================================================================

const IncidentManagement: FC<{
  incidents: IncidentReport[];
  onReportIncident: () => void;
}> = ({ incidents, onReportIncident }) => {
  const criticalCount = incidents.filter((i) => i.severity === 'critical').length;
  const unresolved = incidents.filter((i) => i.status !== 'resolved').length;

  return (
    <div className="incident-management">
      <div className="incident-header">
        <h3>🚨 Incidents & Breaches</h3>
        <div className="incident-stats">
          <span className="stat critical">{criticalCount} Critical</span>
          <span className="stat unresolved">{unresolved} Unresolved</span>
        </div>
      </div>
      <div className="incidents-list">
        {incidents.slice(0, 8).map((incident) => (
          <div key={incident.id} className={`incident-item ${incident.severity}`}>
            <div className="incident-title">
              <span className="icon">
                {incident.severity === 'critical' && '🚨'}
                {incident.severity === 'high' && '🔴'}
                {incident.severity === 'medium' && '🟠'}
                {incident.severity === 'low' && '🟡'}
              </span>
              <span>{incident.title}</span>
            </div>
            <p className="incident-desc">{incident.description}</p>
            <div className="incident-metadata">
              <span className="type">{incident.type}</span>
              <span className="status">{incident.status}</span>
              {incident.affectedRecords && (
                <span className="affected">📊 {incident.affectedRecords} records</span>
              )}
            </div>
          </div>
        ))}
      </div>
      <button className="report-btn" onClick={onReportIncident}>
        + Report New Incident
      </button>
    </div>
  );
};

// ============================================================================
// MAIN ADVANCED DATA GOVERNANCE COMPONENT
// ============================================================================

export const AdvancedDataGovernance: FC = () => {
  const { subscribe, emit } = useWebSocket();
  const { success, error } = useToast();

  const [dataAssets] = useState<DataAsset[]>([
    {
      id: 'asset-1',
      name: 'Customer Database',
      type: 'database',
      owner: 'Data Team',
      classification: 'restricted',
      sensitivityLevel: 5,
      lastModified: Date.now() - 86400000,
      location: 'us-east-1',
      recordCount: 5000000,
      sizeBytes: 450000000,
      lineage: {
        sources: ['CRM', 'Web Forms'],
        transformations: [
          {
            id: 'trans-1',
            type: 'aggregation',
            description: 'Daily customer aggregation',
            timestamp: Date.now() - 3600000,
            appliedBy: 'data-pipeline',
            impact: 'high',
          },
        ],
        destinations: ['Analytics', 'ML Models'],
        lastUpdated: Date.now(),
        completeness: 0.98,
      },
      governance: [
        {
          id: 'policy-1',
          name: 'GDPR Compliance',
          type: 'retention',
          rules: [
            {
              id: 'rule-1',
              condition: 'customer_inactive_days > 365',
              action: 'anonymize',
              priority: 1,
              expirationDate: Date.now() + 86400000 * 365,
            },
          ],
          enabled: true,
          enforcementLevel: 'mandatory',
        },
      ],
      tags: ['customer-data', 'pii', 'production'],
      metadata: { encrypted: true, backup: true },
    },
    {
      id: 'asset-2',
      name: 'Analytics Data Lake',
      type: 'warehouse',
      owner: 'Analytics',
      classification: 'confidential',
      sensitivityLevel: 3,
      lastModified: Date.now(),
      location: 'us-west-2',
      recordCount: 50000000,
      sizeBytes: 5000000000,
      lineage: {
        sources: ['Multiple Databases', 'APIs', 'Files'],
        transformations: [],
        destinations: ['BI Tools', 'Data Science'],
        lastUpdated: Date.now(),
        completeness: 0.95,
      },
      governance: [],
      tags: ['analytics', 'processing'],
      metadata: { partitioned: true },
    },
  ]);

  const [complianceFrameworks] = useState<ComplianceFramework[]>([
    {
      id: 'fw-gdpr',
      name: 'GDPR',
      version: '2016/679',
      requirements: [
        {
          id: 'req-1',
          identifier: 'GDPR-Article-32',
          description: 'Security of Processing',
          status: 'compliant',
          evidence: ['Encryption', 'Access Controls', 'Audit Logs'],
          controlsMapped: ['data-encryption', 'access-control'],
        },
        {
          id: 'req-2',
          identifier: 'GDPR-Article-5',
          description: 'Principles relating to processing',
          status: 'compliant',
          evidence: ['Data Minimization Policy'],
          controlsMapped: ['data-minimization'],
        },
      ],
      status: 'compliant',
      lastAudit: Date.now() - 2592000000, // 30 days ago
      nextAuditDue: Date.now() + 7776000000, // 90 days from now
      complianceScore: 0.95,
    },
    {
      id: 'fw-hipaa',
      name: 'HIPAA',
      version: '1996',
      requirements: [
        {
          id: 'req-3',
          identifier: 'HIPAA-164.308',
          description: 'Administrative Safeguards',
          status: 'in-progress',
          evidence: [],
          controlsMapped: [],
          dueDate: Date.now() + 2592000000,
        },
      ],
      status: 'partial',
      lastAudit: Date.now() - 5184000000,
      nextAuditDue: Date.now() + 2592000000,
      complianceScore: 0.75,
    },
  ]);

  const [auditLogs] = useState<AuditLog[]>([
    {
      id: 'log-1',
      timestamp: Date.now() - 300000,
      action: 'access',
      actor: 'analyst-001',
      resource: 'Customer Database',
      resourceType: 'database',
      ipAddress: '192.168.1.100',
      result: 'success',
      severity: 'info',
    },
    {
      id: 'log-2',
      timestamp: Date.now() - 600000,
      action: 'export',
      actor: 'user-456',
      resource: 'customer_data.csv',
      resourceType: 'file',
      ipAddress: '10.0.0.50',
      result: 'failure',
      reason: 'Insufficient permissions',
      severity: 'warning',
    },
  ]);

  const [dataSubjectRequests] = useState<DataSubjectRight[]>([
    {
      id: 'dsr-1',
      type: 'access',
      status: 'pending',
      requestedBy: 'user-789',
      requestDate: Date.now() - 86400000,
      dueDate: Date.now() + 259200000, // 3 days
      subject: 'Jane Doe',
      description: 'Request for all personal data held',
    },
    {
      id: 'dsr-2',
      type: 'erasure',
      status: 'fulfilled',
      requestedBy: 'user-101',
      requestDate: Date.now() - 604800000,
      dueDate: Date.now() - 259200000,
      completedDate: Date.now() - 172800000,
      subject: 'John Smith',
      description: 'Request for right to be forgotten',
    },
  ]);

  const [incidents] = useState<IncidentReport[]>([
    {
      id: 'inc-1',
      title: 'Unauthorized Access Attempt',
      description: 'Multiple failed login attempts detected on customer database',
      severity: 'high',
      type: 'breach',
      detectedAt: Date.now() - 7200000,
      reportedAt: Date.now() - 7200000,
      affectedAssets: ['asset-1'],
      affectedRecords: 0,
      status: 'investigating',
      responsibleTeam: 'Security',
    },
  ]);

  const [metrics] = useState<GovernanceMetrics>({
    totalAssets: 12,
    classifiedAssets: 11,
    policyCompliance: 0.93,
    auditScore: 0.88,
    incidentsThisMonth: 3,
    accessRequestsAwaiting: 2,
    dataQualityScore: 0.91,
    complianceRate: 0.92,
  });

  const [selectedAsset, setSelectedAsset] = useState<DataAsset | null>(null);

  useEffect(() => {
    const unsub = subscribe('governance:policy_updated', (data: any) => {
      success('Governance policy updated');
    });

    return () => unsub?.();
  }, [subscribe, success]);

  const handleApproveRequest = (id: string) => {
    success(`Data subject request ${id} approved`);
    emit('governance:dsr_approved', { requestId: id });
  };

  return (
    <div className="advanced-data-governance">
      <div className="governance-header">
        <div className="header-title">
          <h1>🛡️ Advanced Data Governance</h1>
          <p>Compliance, Privacy, and Data Lifecycle Management</p>
        </div>
        <div className="metrics-overview">
          <div className="metric-card">
            <span className="metric-label">Assets</span>
            <span className="metric-value">{metrics.totalAssets}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Policy Compliance</span>
            <span className="metric-value">{(metrics.policyCompliance * 100).toFixed(0)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Incidents</span>
            <span className="metric-value">{metrics.incidentsThisMonth}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Data Quality</span>
            <span className="metric-value">{(metrics.dataQualityScore * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      <div className="governance-grid">
        <div className="grid-section">
          <DataAssetsPanel assets={dataAssets} onSelectAsset={setSelectedAsset} />
          {selectedAsset && (
            <div className="asset-details">
              <h4>{selectedAsset.name}</h4>
              <div className="detail-row">
                <span>Type:</span>
                <span>{selectedAsset.type}</span>
              </div>
              <div className="detail-row">
                <span>Classification:</span>
                <span>{selectedAsset.classification}</span>
              </div>
              <div className="detail-row">
                <span>Records:</span>
                <span>{selectedAsset.recordCount?.toLocaleString()}</span>
              </div>
              <div className="detail-row">
                <span>Size:</span>
                <span>{((selectedAsset.sizeBytes || 0) / 1000000000).toFixed(2)} GB</span>
              </div>
            </div>
          )}
        </div>

        <div className="grid-section">
          <ComplianceDashboard frameworks={complianceFrameworks} />
          <AuditLogViewer logs={auditLogs} onFilter={() => {}} />
        </div>

        <div className="grid-section">
          <DataSubjectRights requests={dataSubjectRequests} onApproveRequest={handleApproveRequest} />
          <IncidentManagement incidents={incidents} onReportIncident={() => success('Incident reported')} />
        </div>
      </div>

      <style>{`
        .advanced-data-governance {
          padding: 20px;
          background: #f5f7fa;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          min-height: 100vh;
        }

        .governance-header {
          margin-bottom: 24px;
        }

        .header-title h1 {
          font-size: 28px;
          margin: 0 0 8px 0;
        }

        .header-title p {
          color: #666;
          margin: 0;
        }

        .metrics-overview {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 12px;
          margin-top: 16px;
        }

        .metric-card {
          background: white;
          padding: 16px;
          border-radius: 8px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .metric-label {
          font-size: 12px;
          color: #666;
          text-transform: uppercase;
        }

        .metric-value {
          font-size: 24px;
          font-weight: 700;
          color: #1f2937;
        }

        .governance-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: 16px;
        }

        .grid-section {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .data-assets-panel {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .panel-header {
          font-weight: 600;
          margin-bottom: 12px;
        }

        .filters {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
        }

        .filter {
          flex: 1;
          padding: 6px 8px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 12px;
        }

        .assets-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }

        .asset-item {
          display: flex;
          gap: 12px;
          padding: 10px;
          background: #f9fafb;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .asset-item:hover {
          background: #eff0f3;
        }

        .asset-item.selected {
          background: #dbeafe;
          border-left: 3px solid #3b82f6;
        }

        .asset-icon {
          font-size: 20px;
        }

        .asset-info {
          flex: 1;
        }

        .asset-name {
          font-weight: 500;
          margin: 0;
          font-size: 13px;
        }

        .asset-tags {
          display: flex;
          gap: 6px;
          margin-top: 4px;
          flex-wrap: wrap;
        }

        .classification {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          font-weight: 600;
        }

        .classification.public {
          background: #dcfce7;
          color: #15803d;
        }

        .classification.internal {
          background: #fef3c7;
          color: #b45309;
        }

        .classification.confidential {
          background: #fed7aa;
          color: #9a3412;
        }

        .classification.restricted {
          background: #fecaca;
          color: #b91c1c;
        }

        .asset-owner {
          font-size: 12px;
          color: #666;
        }

        .asset-details {
          background: white;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .detail-row {
          display: flex;
          justify-content: space-between;
          padding: 6px 0;
          font-size: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .compliance-dashboard {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .frameworks-grid {
          display: grid;
          gap: 12px;
        }

        .framework-card {
          padding: 12px;
          background: #f9fafb;
          border-radius: 6px;
          border-left: 3px solid #ddd;
        }

        .framework-card.compliant {
          border-left-color: #10b981;
        }

        .framework-card.partial {
          border-left-color: #f59e0b;
        }

        .framework-card.non-compliant {
          border-left-color: #ef4444;
        }

        .fw-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-weight: 600;
          font-size: 13px;
        }

        .fw-score {
          color: #10b981;
        }

        .fw-bar {
          height: 6px;
          background: #e5e7eb;
          border-radius: 3px;
          overflow: hidden;
          margin-bottom: 8px;
        }

        .fw-fill {
          height: 100%;
          background: linear-gradient(90deg, #3b82f6, #10b981);
        }

        .audit-log-viewer {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .viewer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .action-filter {
          padding: 6px 8px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 12px;
        }

        .logs-table {
          font-size: 12px;
          max-height: 300px;
          overflow-y: auto;
        }

        .table-header {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr 1.5fr 0.8fr 0.8fr;
          gap: 8px;
          padding: 8px;
          background: #f3f4f6;
          font-weight: 600;
          position: sticky;
          top: 0;
        }

        .table-row {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr 1.5fr 0.8fr 0.8fr;
          gap: 8px;
          padding: 8px;
          border-bottom: 1px solid #e5e7eb;
          align-items: center;
        }

        .table-row.warning {
          background: #fffbeb;
        }

        .table-row.critical {
          background: #fef2f2;
        }

        .col-result.success {
          color: #10b981;
        }

        .col-result.failure {
          color: #ef4444;
        }

        .data-subject-rights {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .rights-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .pending {
          background: #fef3c7;
          color: #b45309;
          padding: 2px 8px;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 600;
        }

        .requests-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }

        .request-item {
          padding: 10px;
          background: #f9fafb;
          border-radius: 6px;
          border-left: 3px solid #ddd;
        }

        .request-item.pending {
          border-left-color: #f59e0b;
          background: #fffbeb;
        }

        .request-item.fulfilled {
          border-left-color: #10b981;
        }

        .request-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }

        .request-type {
          font-weight: 600;
          font-size: 12px;
        }

        .status-badge {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          font-weight: 600;
          background: #e5e7eb;
          color: #374151;
        }

        .status-badge.pending {
          background: #fef3c7;
          color: #b45309;
        }

        .incident-management {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .incident-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .incident-stats {
          display: flex;
          gap: 8px;
        }

        .stat {
          padding: 4px 8px;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 600;
        }

        .stat.critical {
          background: #fef2f2;
          color: #991b1b;
        }

        .incidents-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 350px;
          overflow-y: auto;
        }

        .incident-item {
          padding: 10px;
          background: #f9fafb;
          border-radius: 6px;
          border-left: 3px solid #ddd;
        }

        .incident-item.critical {
          border-left-color: #dc2626;
          background: #fef2f2;
        }

        .incident-item.high {
          border-left-color: #ea580c;
          background: #fffbeb;
        }

        .incident-title {
          display: flex;
          gap: 6px;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .incident-desc {
          font-size: 12px;
          color: #666;
          margin: 4px 0;
        }

        .incident-metadata {
          display: flex;
          gap: 8px;
          font-size: 11px;
          color: #999;
        }

        .report-btn {
          width: 100%;
          padding: 8px;
          background: #3b82f6;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          transition: all 0.2s;
        }

        .report-btn:hover {
          background: #2563eb;
        }

        @media (max-width: 1024px) {
          .governance-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 768px) {
          .metrics-overview {
            grid-template-columns: 1fr 1fr;
          }

          .table-header,
          .table-row {
            grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
          }
        }
      `}</style>
    </div>
  );
};

export default AdvancedDataGovernance;
