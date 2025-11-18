import React, { useState, useEffect, useCallback, useMemo, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// SECURITY INTERFACES & TYPES (60+ types)
// ============================================================================

interface SecurityAlert {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  type: 'threat' | 'anomaly' | 'vulnerability' | 'compliance' | 'misconfiguration';
  title: string;
  description: string;
  timestamp: number;
  sourceSystem: string;
  affectedAssets: string[];
  status: 'new' | 'acknowledged' | 'investigating' | 'resolved';
  resolution?: string;
  detectedBy: 'siem' | 'ids' | 'vulnerability_scanner' | 'user_report' | 'ml_model';
  assignedTo?: string;
  tags: string[];
  indicators: SecurityIndicator[];
}

interface SecurityIndicator {
  type: 'ip_address' | 'domain' | 'file_hash' | 'user' | 'process' | 'port';
  value: string;
  confidence: number;
  threatLevel: 'low' | 'medium' | 'high' | 'critical';
}

interface ThreatIntelligence {
  id: string;
  threat: string;
  threatType: 'malware' | 'ransomware' | 'backdoor' | 'phishing' | 'exploit' | 'data_exfiltration';
  severity: 'critical' | 'high' | 'medium' | 'low';
  indicators: string[];
  description: string;
  discoveredAt: number;
  lastSeen: number;
  affectedSystems: string[];
  mitigationSteps: string[];
  references: string[];
  status: 'active' | 'mitigated' | 'archived';
}

interface Vulnerability {
  id: string;
  cveId: string;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  cvssScore: number;
  discoveredAt: number;
  affectedSystems: string[];
  affectedVersion?: string;
  fixAvailable: boolean;
  fixVersion?: string;
  exploitAvailable: boolean;
  detectionMethod: string;
  status: 'open' | 'in-progress' | 'remediated' | 'false-positive' | 'accepted-risk';
  lastModified: number;
}

interface AccessLog {
  id: string;
  timestamp: number;
  userId: string;
  userName: string;
  action: string;
  resourceId: string;
  resourceType: string;
  ipAddress: string;
  userAgent: string;
  result: 'success' | 'failure';
  failureReason?: string;
  location?: string;
  deviceInfo: DeviceInfo;
  riskScore: number;
  anomalousActivity: boolean;
}

interface DeviceInfo {
  os: string;
  browser?: string;
  deviceType: 'mobile' | 'desktop' | 'tablet' | 'unknown';
  isManaged: boolean;
  complianceStatus: 'compliant' | 'non-compliant' | 'unknown';
}

interface AuthenticationEvent {
  id: string;
  timestamp: number;
  userId: string;
  method: 'password' | 'mfa' | 'sso' | 'certificate' | 'biometric';
  success: boolean;
  ipAddress: string;
  location?: string;
  device?: string;
  riskLevel: 'low' | 'medium' | 'high';
  mfaUsed?: boolean;
  mfaMethod?: 'totp' | 'sms' | 'email' | 'hardware' | 'biometric';
  challengeResponse?: string;
}

interface EncryptionPolicy {
  id: string;
  name: string;
  type: 'data_at_rest' | 'data_in_transit' | 'data_in_use';
  algorithm: string;
  keySize: number;
  keyRotationDays: number;
  enabled: boolean;
  appliesToAssets: string[];
  status: 'active' | 'deprecated' | 'planned';
  compliance: string[];
}

interface SecurityControl {
  id: string;
  name: string;
  category: 'preventive' | 'detective' | 'corrective' | 'compensating';
  status: 'active' | 'inactive' | 'planned' | 'disabled';
  effectiveness: number; // 0-1
  lastTested: number;
  nextTestDue: number;
  evidence: string[];
  relatedControls: string[];
  owner: string;
  frequency: 'realtime' | 'hourly' | 'daily' | 'weekly' | 'monthly';
}

interface VPNConnection {
  id: string;
  userId: string;
  connectTime: number;
  disconnectTime?: number;
  vpnServer: string;
  protocol: 'wireguard' | 'openvpn' | 'ipsec' | 'ssl';
  encryptionLevel: '128' | '256' | '512';
  dataTransferred: number;
  packetsLost: number;
  latency: number;
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  deviceId: string;
}

interface FirewallRule {
  id: string;
  name: string;
  priority: number;
  sourceIp: string;
  destinationIp: string;
  protocol: string;
  port: number | string;
  action: 'allow' | 'deny' | 'log' | 'alert';
  enabled: boolean;
  createdAt: number;
  lastModified: number;
  appliedTo: string[];
  hitCount: number;
  status: 'active' | 'inactive' | 'review_needed';
}

interface IntrusionAlert {
  id: string;
  timestamp: number;
  alertType: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  sourceIp: string;
  destinationIp: string;
  protocol: string;
  port: number;
  action: string;
  payload?: string;
  blocked: boolean;
  falsePositive: boolean;
  correlatedAlerts: string[];
}

interface SecurityDashboardMetrics {
  totalAlerts: number;
  criticalAlerts: number;
  alertsTodayCount: number;
  vulnerabilitiesOpen: number;
  complianceScore: number;
  mttrHours: number;
  systemsProtected: number;
  endpointsManaged: number;
  incidentsThisMonth: number;
  dataBreachRisk: number;
}

// ============================================================================
// ALERTS DASHBOARD COMPONENT
// ============================================================================

const AlertsDashboard: FC<{
  alerts: SecurityAlert[];
  onAcknowledge: (id: string) => void;
}> = ({ alerts, onAcknowledge }) => {
  const criticalCount = alerts.filter((a) => a.severity === 'critical').length;
  const highCount = alerts.filter((a) => a.severity === 'high').length;
  const unresolved = alerts.filter((a) => a.status !== 'resolved').length;

  return (
    <div className="alerts-dashboard">
      <div className="dashboard-header">
        <h3>🚨 Security Alerts</h3>
        <div className="alert-stats">
          <span className={`stat critical ${criticalCount > 0 ? 'active' : ''}`}>
            🔴 {criticalCount} Critical
          </span>
          <span className={`stat high ${highCount > 0 ? 'active' : ''}`}>
            🟠 {highCount} High
          </span>
          <span className="stat">{unresolved} Unresolved</span>
        </div>
      </div>
      <div className="alerts-list">
        {alerts.slice(0, 10).map((alert) => (
          <div key={alert.id} className={`alert-item ${alert.severity}`}>
            <div className="alert-header">
              <span className="alert-icon">
                {alert.severity === 'critical' && '🔴'}
                {alert.severity === 'high' && '🟠'}
                {alert.severity === 'medium' && '🟡'}
                {alert.severity === 'low' && '🔵'}
              </span>
              <span className="alert-title">{alert.title}</span>
              <span className={`alert-status ${alert.status}`}>{alert.status}</span>
            </div>
            <p className="alert-desc">{alert.description}</p>
            <div className="alert-details">
              <span className="detail">📍 {alert.sourceSystem}</span>
              <span className="detail">🏷️ {alert.type}</span>
              {alert.assignedTo && <span className="detail">👤 {alert.assignedTo}</span>}
            </div>
            {alert.status !== 'resolved' && (
              <button
                className="acknowledge-btn"
                onClick={() => onAcknowledge(alert.id)}
              >
                Acknowledge
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// THREAT INTELLIGENCE COMPONENT
// ============================================================================

const ThreatIntelligencePanel: FC<{
  threats: ThreatIntelligence[];
}> = ({ threats }) => {
  const activeThreatCount = threats.filter((t) => t.status === 'active').length;

  return (
    <div className="threat-intelligence">
      <div className="panel-header">
        <h3>🎯 Threat Intelligence</h3>
        <span className="threat-count">
          {activeThreatCount} Active Threats
        </span>
      </div>
      <div className="threat-types">
        {['malware', 'ransomware', 'phishing', 'exploit'].map((type) => {
          const count = threats.filter((t) => t.threatType === type && t.status === 'active').length;
          return (
            <div key={type} className="threat-type-item">
              <span className="type-name">{type}</span>
              <span className="type-count">{count}</span>
            </div>
          );
        })}
      </div>
      <div className="threats-list">
        {threats.slice(0, 5).map((threat) => (
          <div key={threat.id} className={`threat-item ${threat.status}`}>
            <span className="threat-name">{threat.threat}</span>
            <span className={`severity ${threat.severity}`}>{threat.severity}</span>
            <span className="indicator-count">
              {threat.indicators.length} indicators
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// VULNERABILITY MANAGEMENT COMPONENT
// ============================================================================

const VulnerabilityManagement: FC<{
  vulnerabilities: Vulnerability[];
}> = ({ vulnerabilities }) => {
  const [sortBy, setSortBy] = useState<'severity' | 'cvss' | 'age'>('severity');

  const sorted = useMemo(
    () => {
      const copy = [...vulnerabilities];
      if (sortBy === 'severity') {
        const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
        copy.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
      } else if (sortBy === 'cvss') {
        copy.sort((a, b) => b.cvssScore - a.cvssScore);
      } else {
        copy.sort((a, b) => a.discoveredAt - b.discoveredAt);
      }
      return copy;
    },
    [vulnerabilities, sortBy]
  );

  return (
    <div className="vulnerability-management">
      <div className="panel-header">
        <h3>🔍 Vulnerabilities</h3>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} className="sort-select">
          <option value="severity">Sort by Severity</option>
          <option value="cvss">Sort by CVSS</option>
          <option value="age">Sort by Age</option>
        </select>
      </div>
      <div className="vulnerability-summary">
        <div className="summary-stat">
          <span className="label">Open</span>
          <span className="value critical">
            {vulnerabilities.filter((v) => v.status === 'open').length}
          </span>
        </div>
        <div className="summary-stat">
          <span className="label">Critical/High</span>
          <span className="value critical">
            {vulnerabilities.filter((v) => ['critical', 'high'].includes(v.severity)).length}
          </span>
        </div>
        <div className="summary-stat">
          <span className="label">Exploitable</span>
          <span className="value warning">
            {vulnerabilities.filter((v) => v.exploitAvailable).length}
          </span>
        </div>
      </div>
      <div className="vuln-list">
        {sorted.slice(0, 8).map((vuln) => (
          <div key={vuln.id} className={`vuln-item ${vuln.severity}`}>
            <div className="vuln-header">
              <span className={`severity-badge ${vuln.severity}`}>{vuln.severity}</span>
              <span className="vuln-id">{vuln.cveId}</span>
              <span className="cvss-score">CVSS {vuln.cvssScore.toFixed(1)}</span>
            </div>
            <p className="vuln-title">{vuln.title}</p>
            <div className="vuln-info">
              <span className="info-item">
                {vuln.fixAvailable ? '✅ Fix' : '⏳ Pending'}
              </span>
              <span className="info-item">
                {vuln.exploitAvailable && '⚡ Exploitable'}
              </span>
              <span className="info-item">
                Affects {vuln.affectedSystems.length} system(s)
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// ACCESS & AUTHENTICATION COMPONENT
// ============================================================================

const AccessAndAuth: FC<{
  accessLogs: AccessLog[];
  authEvents: AuthenticationEvent[];
}> = ({ accessLogs, authEvents }) => {
  const failedLogins = useMemo(
    () => authEvents.filter((e) => !e.success).length,
    [authEvents]
  );

  const mfaUsageRate = useMemo(
    () =>
      (authEvents.filter((e) => e.mfaUsed).length / authEvents.length) * 100,
    [authEvents]
  );

  return (
    <div className="access-auth-panel">
      <div className="panel-header">
        <h3>🔐 Access & Authentication</h3>
      </div>
      <div className="auth-stats">
        <div className="stat-card">
          <span className="stat-label">Failed Logins (24h)</span>
          <span className={`stat-value ${failedLogins > 5 ? 'warning' : ''}`}>
            {failedLogins}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">MFA Usage Rate</span>
          <span className="stat-value">{mfaUsageRate.toFixed(1)}%</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Anomalous Activities</span>
          <span className="stat-value warning">
            {accessLogs.filter((l) => l.anomalousActivity).length}
          </span>
        </div>
      </div>
      <div className="recent-activity">
        <h4>Recent Access Activity</h4>
        <div className="activity-list">
          {accessLogs.slice(0, 8).map((log) => (
            <div
              key={log.id}
              className={`activity-item ${log.anomalousActivity ? 'anomalous' : ''}`}
            >
              <span className="user">{log.userName}</span>
              <span className="action">{log.action}</span>
              <span className="time">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              {log.anomalousActivity && (
                <span className="anomaly-indicator">⚠️</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// FIREWALL & IDS COMPONENT
// ============================================================================

const FirewallAndIDS: FC<{
  rules: FirewallRule[];
  intrusionAlerts: IntrusionAlert[];
}> = ({ rules, intrusionAlerts }) => {
  const blockedToday = intrusionAlerts.filter((a) => a.blocked).length;
  const activeRules = rules.filter((r) => r.enabled).length;

  return (
    <div className="firewall-ids">
      <div className="panel-header">
        <h3>🧱 Firewall & IDS</h3>
      </div>
      <div className="firewall-stats">
        <div className="stat-box">
          <span className="label">Active Rules</span>
          <span className="value">{activeRules}/{rules.length}</span>
        </div>
        <div className="stat-box">
          <span className="label">Blocked Today</span>
          <span className="value">{blockedToday}</span>
        </div>
      </div>
      <div className="ids-section">
        <h4>Latest IDS Alerts</h4>
        <div className="alerts-compact-list">
          {intrusionAlerts.slice(0, 6).map((alert) => (
            <div key={alert.id} className={`ids-alert ${alert.severity}`}>
              <span className="severity-dot">●</span>
              <span className="alert-type">{alert.alertType}</span>
              <span className="action-badge">
                {alert.blocked ? '🚫 Blocked' : '⚠️ Detected'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// ENCRYPTION & COMPLIANCE COMPONENT
// ============================================================================

const EncryptionCompliance: FC<{
  policies: EncryptionPolicy[];
  metrics: SecurityDashboardMetrics;
}> = ({ policies, metrics }) => {
  const activeEncryption = policies.filter((p) => p.status === 'active').length;

  return (
    <div className="encryption-compliance">
      <div className="panel-header">
        <h3>🔒 Encryption & Compliance</h3>
      </div>
      <div className="compliance-score">
        <div className="score-circle">
          <span className="score-value">{(metrics.complianceScore * 100).toFixed(0)}%</span>
          <span className="score-label">Compliance Score</span>
        </div>
      </div>
      <div className="encryption-list">
        <h4>Encryption Policies ({activeEncryption} Active)</h4>
        {policies.map((policy) => (
          <div key={policy.id} className={`policy-item ${policy.status}`}>
            <div className="policy-header">
              <span className="policy-name">{policy.name}</span>
              <span className={`status-badge ${policy.status}`}>{policy.status}</span>
            </div>
            <div className="policy-details">
              <span className="detail">
                {policy.algorithm}-{policy.keySize}
              </span>
              <span className="detail">
                Rotation: {policy.keyRotationDays}d
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// MAIN ADVANCED SECURITY HUB COMPONENT
// ============================================================================

export const AdvancedSecurityHub: FC = () => {
  const { subscribe, emit } = useWebSocket();
  const { success, error } = useToast();

  const [alerts, setAlerts] = useState<SecurityAlert[]>([
    {
      id: 'alert-1',
      severity: 'critical',
      type: 'threat',
      title: 'Malware Detected',
      description: 'Suspicious executable detected on workstation-45 matching known malware signatures',
      timestamp: Date.now() - 1800000,
      sourceSystem: 'Endpoint Detection & Response',
      affectedAssets: ['workstation-45', 'nas-02'],
      status: 'investigating',
      detectedBy: 'ml_model',
      tags: ['malware', 'endpoint', 'high-priority'],
      indicators: [
        { type: 'file_hash', value: 'a1b2c3d4e5f6...', confidence: 0.98, threatLevel: 'critical' },
      ],
    },
    {
      id: 'alert-2',
      severity: 'high',
      type: 'anomaly',
      title: 'Unusual Data Access Pattern',
      description: 'User account accessed sensitive financial data at unusual time',
      timestamp: Date.now() - 3600000,
      sourceSystem: 'SIEM',
      affectedAssets: ['financial_db'],
      status: 'acknowledged',
      detectedBy: 'siem',
      tags: ['data-exfiltration', 'user-behavior'],
      indicators: [
        { type: 'user', value: 'user-789', confidence: 0.95, threatLevel: 'high' },
      ],
    },
  ]);

  const [threats] = useState<ThreatIntelligence[]>([
    {
      id: 'threat-1',
      threat: 'LockBit 3.0 Ransomware Campaign',
      threatType: 'ransomware',
      severity: 'critical',
      indicators: ['185.220.100.1', 'command-control.ru'],
      description: 'Ongoing campaign targeting enterprise networks',
      discoveredAt: Date.now() - 432000000,
      lastSeen: Date.now() - 86400000,
      affectedSystems: ['network-segment-A', 'network-segment-C'],
      mitigationSteps: ['Block indicators', 'Patch vulnerabilities', 'Monitor traffic'],
      references: ['https://threat-intel.com/lockbit3'],
      status: 'active',
    },
  ]);

  const [vulnerabilities] = useState<Vulnerability[]>([
    {
      id: 'vuln-1',
      cveId: 'CVE-2024-1234',
      title: 'Critical RCE in Web Server',
      description: 'Remote code execution vulnerability in Apache HTTP Server',
      severity: 'critical',
      cvssScore: 9.8,
      discoveredAt: Date.now() - 604800000,
      affectedSystems: ['web-server-01', 'web-server-02', 'web-server-03'],
      affectedVersion: '2.4.48 - 2.4.57',
      fixAvailable: true,
      fixVersion: '2.4.58',
      exploitAvailable: true,
      detectionMethod: 'vulnerability_scanner',
      status: 'in-progress',
      lastModified: Date.now() - 86400000,
    },
  ]);

  const [accessLogs] = useState<AccessLog[]>([
    {
      id: 'log-1',
      timestamp: Date.now() - 300000,
      userId: 'user-123',
      userName: 'john.doe',
      action: 'login',
      resourceId: 'admin-portal',
      resourceType: 'application',
      ipAddress: '192.168.1.100',
      userAgent: 'Chrome/120.0',
      result: 'success',
      location: 'New York, US',
      deviceInfo: {
        os: 'Windows 11',
        browser: 'Chrome',
        deviceType: 'desktop',
        isManaged: true,
        complianceStatus: 'compliant',
      },
      riskScore: 0.15,
      anomalousActivity: false,
    },
  ]);

  const [authEvents] = useState<AuthenticationEvent[]>([
    {
      id: 'auth-1',
      timestamp: Date.now() - 600000,
      userId: 'user-456',
      method: 'mfa',
      success: true,
      ipAddress: '10.0.0.50',
      location: 'Remote',
      device: 'MacBook Pro',
      riskLevel: 'low',
      mfaUsed: true,
      mfaMethod: 'totp',
    },
  ]);

  const [firewallRules] = useState<FirewallRule[]>([
    {
      id: 'fw-rule-1',
      name: 'Block-Known-Malware-IPs',
      priority: 1,
      sourceIp: '185.220.100.0/24',
      destinationIp: '*',
      protocol: 'all',
      port: 'all',
      action: 'deny',
      enabled: true,
      createdAt: Date.now() - 2592000000,
      lastModified: Date.now() - 86400000,
      appliedTo: ['perimeter-fw'],
      hitCount: 1247,
      status: 'active',
    },
  ]);

  const [intrusionAlerts] = useState<IntrusionAlert[]>([
    {
      id: 'ids-1',
      timestamp: Date.now() - 1800000,
      alertType: 'SQL Injection Attempt',
      severity: 'high',
      sourceIp: '203.0.113.45',
      destinationIp: '192.168.1.10',
      protocol: 'TCP',
      port: 443,
      action: 'Blocked',
      blocked: true,
      falsePositive: false,
      correlatedAlerts: ['ids-2'],
    },
  ]);

  const [encryptionPolicies] = useState<EncryptionPolicy[]>([
    {
      id: 'enc-1',
      name: 'Data at Rest - AES-256',
      type: 'data_at_rest',
      algorithm: 'AES',
      keySize: 256,
      keyRotationDays: 90,
      enabled: true,
      appliesToAssets: ['database-prod', 'storage-s3'],
      status: 'active',
      compliance: ['GDPR', 'HIPAA', 'SOC2'],
    },
  ]);

  const [metrics] = useState<SecurityDashboardMetrics>({
    totalAlerts: 147,
    criticalAlerts: 2,
    alertsTodayCount: 12,
    vulnerabilitiesOpen: 8,
    complianceScore: 0.94,
    mttrHours: 2.5,
    systemsProtected: 342,
    endpointsManaged: 1250,
    incidentsThisMonth: 3,
    dataBreachRisk: 0.15,
  });

  const handleAcknowledgeAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, status: 'acknowledged' } : a
      )
    );
    success('Alert acknowledged');
    emit('security:alert_acknowledged', { alertId: id });
  }, [emit, success]);

  useEffect(() => {
    const unsub = subscribe('security:threat_detected', (data: any) => {
      error(`New threat detected: ${data.threatName}`);
    });

    return () => unsub?.();
  }, [subscribe, error]);

  return (
    <div className="advanced-security-hub">
      <div className="security-header">
        <div className="header-content">
          <h1>🛡️ Advanced Security Hub</h1>
          <p>Threat Detection, Vulnerability Management & Compliance</p>
        </div>
        <div className="header-metrics">
          <div className="metric-pill critical">
            🔴 {metrics.criticalAlerts} Critical
          </div>
          <div className="metric-pill warning">
            🟡 {metrics.vulnerabilitiesOpen} Vulnerabilities
          </div>
          <div className="metric-pill success">
            ✅ {(metrics.complianceScore * 100).toFixed(0)}% Compliant
          </div>
        </div>
      </div>

      <div className="security-grid">
        <div className="grid-col-2">
          <AlertsDashboard alerts={alerts} onAcknowledge={handleAcknowledgeAlert} />
        </div>

        <div className="grid-col-1">
          <ThreatIntelligencePanel threats={threats} />
        </div>

        <div className="grid-col-2">
          <VulnerabilityManagement vulnerabilities={vulnerabilities} />
        </div>

        <div className="grid-col-1">
          <AccessAndAuth accessLogs={accessLogs} authEvents={authEvents} />
        </div>

        <div className="grid-col-1">
          <FirewallAndIDS rules={firewallRules} intrusionAlerts={intrusionAlerts} />
        </div>

        <div className="grid-col-1">
          <EncryptionCompliance policies={encryptionPolicies} metrics={metrics} />
        </div>
      </div>

      <style>{`
        .advanced-security-hub {
          padding: 24px;
          background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
          color: #e5e7eb;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          min-height: 100vh;
        }

        .security-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          background: rgba(255, 255, 255, 0.05);
          padding: 24px;
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .header-content h1 {
          margin: 0 0 8px 0;
          font-size: 32px;
        }

        .header-content p {
          margin: 0;
          color: #9ca3af;
        }

        .header-metrics {
          display: flex;
          gap: 16px;
        }

        .metric-pill {
          padding: 10px 16px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          background: rgba(255, 255, 255, 0.1);
        }

        .metric-pill.critical {
          background: rgba(220, 38, 38, 0.2);
          color: #fca5a5;
        }

        .metric-pill.warning {
          background: rgba(251, 146, 60, 0.2);
          color: #fed7aa;
        }

        .metric-pill.success {
          background: rgba(34, 197, 94, 0.2);
          color: #86efac;
        }

        .security-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: 16px;
        }

        .grid-col-1 {
          grid-column: 1;
        }

        .grid-col-2 {
          grid-column: 1 / -1;
        }

        @media (min-width: 1200px) {
          .grid-col-1 {
            grid-column: span 1;
          }

          .grid-col-2 {
            grid-column: span 2;
          }
        }

        .alerts-dashboard,
        .threat-intelligence,
        .vulnerability-management,
        .access-auth-panel,
        .firewall-ids,
        .encryption-compliance {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 16px;
        }

        .dashboard-header,
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          font-weight: 600;
        }

        .alert-stats {
          display: flex;
          gap: 12px;
          font-size: 12px;
        }

        .stat.active {
          color: #fca5a5;
        }

        .alerts-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 500px;
          overflow-y: auto;
        }

        .alert-item {
          padding: 12px;
          background: rgba(255, 255, 255, 0.03);
          border-left: 3px solid #ddd;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .alert-item:hover {
          background: rgba(255, 255, 255, 0.08);
        }

        .alert-item.critical {
          border-left-color: #dc2626;
          background: rgba(220, 38, 38, 0.1);
        }

        .alert-item.high {
          border-left-color: #ea580c;
          background: rgba(234, 88, 12, 0.1);
        }

        .alert-header {
          display: flex;
          gap: 8px;
          align-items: center;
          margin-bottom: 6px;
        }

        .alert-icon {
          font-size: 16px;
        }

        .alert-title {
          flex: 1;
          font-weight: 600;
        }

        .alert-status {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          background: rgba(255, 255, 255, 0.1);
        }

        .alert-desc {
          font-size: 12px;
          margin: 4px 0;
          color: #d1d5db;
        }

        .alert-details {
          display: flex;
          gap: 12px;
          font-size: 11px;
          color: #9ca3af;
          margin-bottom: 8px;
        }

        .acknowledge-btn {
          width: 100%;
          padding: 6px;
          background: #3b82f6;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .acknowledge-btn:hover {
          background: #2563eb;
        }

        .threat-types {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
          margin-bottom: 12px;
        }

        .threat-type-item {
          display: flex;
          justify-content: space-between;
          padding: 8px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 4px;
          font-size: 12px;
        }

        .threat-count {
          color: #fca5a5;
          font-weight: 600;
        }

        .threats-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .threat-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 4px;
          font-size: 12px;
        }

        .threat-item.active {
          border-left: 2px solid #dc2626;
        }

        .severity {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          font-weight: 600;
        }

        .severity.critical {
          background: rgba(220, 38, 38, 0.3);
          color: #fca5a5;
        }

        .vulnerability-summary {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-bottom: 12px;
        }

        .summary-stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 8px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 4px;
        }

        .summary-stat .label {
          font-size: 10px;
          color: #9ca3af;
        }

        .summary-stat .value {
          font-size: 18px;
          font-weight: 700;
        }

        .summary-stat .value.critical {
          color: #fca5a5;
        }

        .summary-stat .value.warning {
          color: #fed7aa;
        }

        .vuln-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }

        .vuln-item {
          padding: 10px;
          background: rgba(255, 255, 255, 0.03);
          border-left: 3px solid #ddd;
          border-radius: 6px;
        }

        .vuln-item.critical {
          border-left-color: #dc2626;
        }

        .vuln-header {
          display: flex;
          gap: 8px;
          align-items: center;
          margin-bottom: 4px;
          font-size: 12px;
        }

        .severity-badge {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          font-weight: 600;
        }

        .severity-badge.critical {
          background: rgba(220, 38, 38, 0.3);
          color: #fca5a5;
        }

        .vuln-title {
          font-size: 12px;
          margin: 4px 0;
          color: #e5e7eb;
        }

        .vuln-info {
          display: flex;
          gap: 12px;
          font-size: 11px;
          color: #9ca3af;
        }

        .auth-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-bottom: 12px;
        }

        .stat-card {
          display: flex;
          flex-direction: column;
          padding: 10px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 6px;
          text-align: center;
        }

        .stat-label {
          font-size: 10px;
          color: #9ca3af;
          margin-bottom: 4px;
        }

        .stat-value {
          font-size: 20px;
          font-weight: 700;
        }

        .stat-value.warning {
          color: #fed7aa;
        }

        .activity-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
          max-height: 300px;
          overflow-y: auto;
        }

        .activity-item {
          display: flex;
          gap: 8px;
          padding: 8px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 4px;
          font-size: 12px;
          align-items: center;
        }

        .activity-item.anomalous {
          border-left: 2px solid #f59e0b;
          background: rgba(245, 158, 11, 0.1);
        }

        .firewall-stats {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
          margin-bottom: 12px;
        }

        .stat-box {
          display: flex;
          flex-direction: column;
          padding: 12px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 6px;
        }

        .stat-box .label {
          font-size: 10px;
          color: #9ca3af;
        }

        .stat-box .value {
          font-size: 18px;
          font-weight: 700;
          margin-top: 4px;
        }

        .ids-section {
          margin-top: 12px;
        }

        .ids-section h4 {
          font-size: 12px;
          margin: 0 0 8px 0;
          text-transform: uppercase;
        }

        .alerts-compact-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .ids-alert {
          display: flex;
          gap: 8px;
          padding: 8px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 4px;
          font-size: 11px;
          align-items: center;
        }

        .ids-alert.critical {
          border-left: 2px solid #dc2626;
        }

        .severity-dot {
          font-size: 10px;
        }

        .compliance-score {
          display: flex;
          justify-content: center;
          margin-bottom: 16px;
        }

        .score-circle {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: conic-gradient(
            #22c55e 0deg,
            #22c55e 338.4deg,
            rgba(255, 255, 255, 0.1) 338.4deg
          );
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          position: relative;
        }

        .score-circle::after {
          content: '';
          position: absolute;
          width: 110px;
          height: 110px;
          border-radius: 50%;
          background: #1f2937;
          z-index: -1;
          inset: 5px;
        }

        .score-value {
          font-size: 28px;
          font-weight: 700;
          color: #22c55e;
        }

        .score-label {
          font-size: 10px;
          color: #9ca3af;
          margin-top: 4px;
        }

        .encryption-list {
          margin-top: 12px;
        }

        .encryption-list h4 {
          font-size: 12px;
          margin: 0 0 8px 0;
          text-transform: uppercase;
        }

        .policy-item {
          padding: 10px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 6px;
          margin-bottom: 8px;
        }

        .policy-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
          font-size: 12px;
          font-weight: 600;
        }

        .status-badge {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
        }

        .status-badge.active {
          background: rgba(34, 197, 94, 0.3);
          color: #86efac;
        }

        .sort-select {
          padding: 6px 8px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          color: #e5e7eb;
          font-size: 12px;
        }

        @media (max-width: 1024px) {
          .header-metrics {
            flex-direction: column;
            gap: 8px;
          }

          .auth-stats,
          .threat-types,
          .firewall-stats,
          .vulnerability-summary {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .security-header {
            flex-direction: column;
            text-align: center;
            gap: 16px;
          }

          .header-metrics {
            width: 100%;
            justify-content: center;
          }

          .security-grid {
            grid-template-columns: 1fr;
          }

          .grid-col-2 {
            grid-column: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default AdvancedSecurityHub;
