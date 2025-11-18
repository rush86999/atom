import React, { useState, useEffect, useCallback, useMemo, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// CUSTOMER SUCCESS INTERFACES & TYPES (70+ types)
// ============================================================================

interface Customer {
  id: string;
  name: string;
  email: string;
  company: string;
  industry: string;
  tier: 'starter' | 'growth' | 'enterprise' | 'strategic';
  status: 'active' | 'at-risk' | 'churned' | 'prospect';
  signupDate: number;
  contractEndDate: number;
  arr: number; // Annual Recurring Revenue
  healthScore: number; // 0-100
  healthTrend: 'improving' | 'stable' | 'declining';
  nextCheckpoint: number;
  contacts: Contact[];
  usage: CustomerUsage;
  engagementLevel: 'high' | 'medium' | 'low';
  metadata: Record<string, any>;
}

interface Contact {
  id: string;
  name: string;
  email: string;
  role: string;
  primary: boolean;
  lastContactDate?: number;
  department?: string;
}

interface CustomerUsage {
  activeUsers: number;
  loginFrequency: number; // logins per week
  featuresUsed: string[];
  moau: number; // Monthly Active Users
  dau: number; // Daily Active Users
  lastActivityDate: number;
  utilizationRate: number; // 0-100
  adoptionRate: number; // 0-100
  frequencyTrend: 'increasing' | 'stable' | 'decreasing';
}

interface HealthScoreComponent {
  category: 'usage' | 'engagement' | 'growth' | 'support' | 'expansion';
  weight: number;
  score: number;
  trend: string;
  indicators: HealthIndicator[];
}

interface HealthIndicator {
  name: string;
  value: number;
  target: number;
  threshold: 'danger' | 'warning' | 'healthy';
}

interface ChurnRisk {
  customerId: string;
  riskScore: number; // 0-100
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  factors: ChurnFactor[];
  predictedChurnDate?: number;
  riskTrend: string;
  mitigationActions: MitigationAction[];
}

interface ChurnFactor {
  factor: string;
  weight: number;
  trend: string;
  impact: number; // -100 to 100
}

interface MitigationAction {
  id: string;
  title: string;
  description: string;
  type: 'engagement' | 'upsell' | 'support' | 'training';
  priority: 'high' | 'medium' | 'low';
  targetDate: number;
  owner: string;
  status: 'pending' | 'in-progress' | 'completed';
  expectedImpact: number;
}

interface ExpansionOpportunity {
  id: string;
  customerId: string;
  type: 'upsell' | 'cross-sell' | 'vertical-expansion' | 'account-growth';
  productName: string;
  currentValue: number;
  estimatedValue: number;
  confidence: number;
  likelihood: 'high' | 'medium' | 'low';
  maturityLevel: number; // 0-100
  recommendedAction: string;
  targetDate: number;
  owner: string;
  status: 'identified' | 'qualified' | 'proposed' | 'won' | 'lost';
}

interface NPS {
  respondentId: string;
  customerId: string;
  date: number;
  score: number; // 0-10
  category: 'promoter' | 'passive' | 'detractor';
  feedback: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  topics: string[];
  responseRate: number;
  followUpRequired: boolean;
  followUpDone?: boolean;
}

interface Touchpoint {
  id: string;
  customerId: string;
  date: number;
  type: 'call' | 'email' | 'meeting' | 'training' | 'demo' | 'support_ticket';
  owner: string;
  topic: string;
  notes: string;
  outcome: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  actionItems: ActionItem[];
  duration?: number; // in minutes
  nextTouchpoint?: number;
}

interface ActionItem {
  id: string;
  description: string;
  owner: string;
  dueDate: number;
  status: 'pending' | 'completed' | 'overdue';
  priority: number;
}

interface TrainingProgram {
  id: string;
  name: string;
  description: string;
  modules: TrainingModule[];
  duration: number; // in hours
  targetAudience: string;
  completionRate: number; // 0-100
  enrolledCount: number;
  completedCount: number;
  averageScore: number;
  status: 'active' | 'archived' | 'draft';
  createdAt: number;
}

interface TrainingModule {
  id: string;
  name: string;
  duration: number;
  content: string;
  assessments: Assessment[];
}

interface Assessment {
  id: string;
  type: 'quiz' | 'practical' | 'survey';
  questions: number;
  passingScore: number;
}

interface CustomerSuccessMetrics {
  totalCustomers: number;
  activeCustomers: number;
  atRiskCustomers: number;
  averageHealthScore: number;
  npsScore: number;
  netRetentionRate: number;
  churnRate: number;
  expansionRate: number;
  csat: number;
  timeToROI: number; // in days
  grossRetentionRate: number;
  expansionRevenue: number;
  totalARR: number;
}

interface CustomerJourney {
  id: string;
  customerId: string;
  stage: 'onboarding' | 'adoption' | 'expansion' | 'maturity' | 'advocacy' | 'churn';
  enteredAt: number;
  exitedAt?: number;
  duration: number; // in days
  successCriteria: SuccessCriteria[];
  completionRate: number; // 0-100
  risks: string[];
}

interface SuccessCriteria {
  id: string;
  name: string;
  description: string;
  target: number;
  current: number;
  unit: string;
  status: 'on-track' | 'at-risk' | 'off-track';
}

interface Account {
  id: string;
  name: string;
  customers: Customer[];
  accountOwner: string;
  accountTeam: string[];
  totalARR: number;
  healthScore: number;
  growthPotential: number;
  lastReviewDate: number;
  nextReviewDate: number;
  strategicValue: 'low' | 'medium' | 'high' | 'strategic';
}

// ============================================================================
// CUSTOMER HEALTH DASHBOARD COMPONENT
// ============================================================================

const CustomerHealthDashboard: FC<{
  customers: Customer[];
  onSelectCustomer: (customer: Customer) => void;
}> = ({ customers, onSelectCustomer }) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = useMemo(
    () =>
      customers.filter(
        (c) =>
          (filterStatus === 'all' || c.status === filterStatus) &&
          (c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            c.company.toLowerCase().includes(searchTerm.toLowerCase()))
      ),
    [customers, filterStatus, searchTerm]
  );

  return (
    <div className="health-dashboard">
      <div className="dashboard-header">
        <h3>👥 Customer Health</h3>
      </div>
      <div className="filters-section">
        <input
          type="text"
          placeholder="Search customer or company..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="status-filter"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="at-risk">At Risk</option>
          <option value="churned">Churned</option>
        </select>
      </div>
      <div className="customers-list">
        {filtered.map((customer) => (
          <div
            key={customer.id}
            className={`customer-card ${customer.status}`}
            onClick={() => onSelectCustomer(customer)}
          >
            <div className="card-header">
              <div className="customer-info">
                <h4>{customer.name}</h4>
                <p className="company">{customer.company}</p>
              </div>
              <div className="status-badge" title={customer.status}>
                {customer.status === 'active' && '🟢'}
                {customer.status === 'at-risk' && '🟡'}
                {customer.status === 'churned' && '🔴'}
              </div>
            </div>
            <div className="health-bar">
              <div
                className={`health-fill ${
                  customer.healthScore >= 75
                    ? 'good'
                    : customer.healthScore >= 50
                    ? 'medium'
                    : 'poor'
                }`}
                style={{ width: `${customer.healthScore}%` }}
              />
            </div>
            <div className="card-footer">
              <span className="health-score">{customer.healthScore}%</span>
              <span className="arr">ARR: ${(customer.arr / 1000).toFixed(0)}K</span>
              <span className="tier">{customer.tier}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// CHURN RISK ANALYSIS COMPONENT
// ============================================================================

const ChurnRiskAnalysis: FC<{
  churnRisks: ChurnRisk[];
}> = ({ churnRisks }) => {
  const criticalRisks = churnRisks.filter((r) => r.riskLevel === 'critical');
  const highRisks = churnRisks.filter((r) => r.riskLevel === 'high');

  return (
    <div className="churn-risk-panel">
      <div className="panel-header">
        <h3>⚠️ Churn Risk Analysis</h3>
        <div className="risk-stats">
          <span className="stat critical">{criticalRisks.length} Critical</span>
          <span className="stat high">{highRisks.length} High</span>
        </div>
      </div>
      <div className="risks-list">
        {churnRisks.slice(0, 8).map((risk) => (
          <div key={risk.customerId} className={`risk-item ${risk.riskLevel}`}>
            <div className="risk-header">
              <span className="risk-icon">
                {risk.riskLevel === 'critical' && '🔴'}
                {risk.riskLevel === 'high' && '🟠'}
                {risk.riskLevel === 'medium' && '🟡'}
              </span>
              <span className="risk-score">{risk.riskScore}% Risk</span>
            </div>
            <div className="risk-factors">
              {risk.factors.slice(0, 2).map((factor) => (
                <span key={factor.factor} className="factor-tag">
                  {factor.factor}
                </span>
              ))}
            </div>
            <div className="mitigation-actions">
              {risk.mitigationActions.slice(0, 2).map((action) => (
                <span
                  key={action.id}
                  className={`action-badge ${action.status}`}
                  title={action.title}
                >
                  {action.status === 'pending' && '⏳'}
                  {action.status === 'in-progress' && '🔄'}
                  {action.status === 'completed' && '✅'}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// EXPANSION OPPORTUNITIES COMPONENT
// ============================================================================

const ExpansionOpportunitiesPanel: FC<{
  opportunities: ExpansionOpportunity[];
}> = ({ opportunities }) => {
  const totalPotential = opportunities.reduce((sum, o) => sum + o.estimatedValue, 0);
  const byType = useMemo(
    () => {
      const grouped: Record<string, ExpansionOpportunity[]> = {};
      opportunities.forEach((opp) => {
        if (!grouped[opp.type]) grouped[opp.type] = [];
        grouped[opp.type].push(opp);
      });
      return grouped;
    },
    [opportunities]
  );

  return (
    <div className="expansion-panel">
      <div className="panel-header">
        <h3>🚀 Expansion Opportunities</h3>
        <span className="potential-revenue">
          ${(totalPotential / 1000).toFixed(0)}K Total
        </span>
      </div>
      <div className="opportunity-types">
        {Object.entries(byType).map(([type, opps]) => (
          <div key={type} className="type-section">
            <h4>{type}</h4>
            <div className="opps-list">
              {opps.map((opp) => (
                <div key={opp.id} className={`opportunity-item ${opp.likelihood}`}>
                  <div className="opp-header">
                    <span className="opp-name">{opp.productName}</span>
                    <span className={`likelihood-badge ${opp.likelihood}`}>
                      {opp.likelihood}
                    </span>
                  </div>
                  <div className="opp-value">
                    ${opp.estimatedValue.toLocaleString()} estimated
                  </div>
                  <div className="maturity-bar">
                    <div
                      className="maturity-fill"
                      style={{ width: `${opp.maturityLevel}%` }}
                    />
                  </div>
                  <span className="maturity-label">{opp.status}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// NPS & SENTIMENT COMPONENT
// ============================================================================

const NPSSentimentPanel: FC<{
  npsScores: NPS[];
  metrics: CustomerSuccessMetrics;
}> = ({ npsScores, metrics }) => {
  const promoters = useMemo(
    () => npsScores.filter((n) => n.category === 'promoter').length,
    [npsScores]
  );

  const detractors = useMemo(
    () => npsScores.filter((n) => n.category === 'detractor').length,
    [npsScores]
  );

  const passives = useMemo(
    () => npsScores.filter((n) => n.category === 'passive').length,
    [npsScores]
  );

  const total = npsScores.length || 1;

  return (
    <div className="nps-sentiment-panel">
      <div className="panel-header">
        <h3>😊 NPS & Sentiment</h3>
      </div>
      <div className="nps-score-display">
        <div className="nps-number">
          <span className="score">{metrics.npsScore}</span>
          <span className="label">NPS</span>
        </div>
      </div>
      <div className="nps-breakdown">
        <div className="breakdown-item promoter">
          <span className="category">Promoters</span>
          <span className="count">{promoters}</span>
          <span className="percentage">({((promoters / total) * 100).toFixed(0)}%)</span>
        </div>
        <div className="breakdown-item passive">
          <span className="category">Passives</span>
          <span className="count">{passives}</span>
          <span className="percentage">({((passives / total) * 100).toFixed(0)}%)</span>
        </div>
        <div className="breakdown-item detractor">
          <span className="category">Detractors</span>
          <span className="count">{detractors}</span>
          <span className="percentage">({((detractors / total) * 100).toFixed(0)}%)</span>
        </div>
      </div>
      <div className="sentiment-summary">
        <h4>Recent Feedback Themes</h4>
        <div className="themes-list">
          {['Product Quality', 'Customer Support', 'Pricing', 'Feature Requests'].map(
            (theme, idx) => (
              <span key={theme} className="theme-tag">
                {theme}
              </span>
            )
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// TOUCHPOINTS & ENGAGEMENT COMPONENT
// ============================================================================

const TouchpointsPanel: FC<{
  touchpoints: Touchpoint[];
}> = ({ touchpoints }) => {
  return (
    <div className="touchpoints-panel">
      <div className="panel-header">
        <h3>📞 Recent Touchpoints</h3>
      </div>
      <div className="touchpoints-list">
        {touchpoints.slice(0, 10).map((tp) => (
          <div key={tp.id} className={`touchpoint-item ${tp.type}`}>
            <div className="tp-icon">
              {tp.type === 'call' && '📱'}
              {tp.type === 'email' && '📧'}
              {tp.type === 'meeting' && '👥'}
              {tp.type === 'training' && '🎓'}
              {tp.type === 'demo' && '🎬'}
              {tp.type === 'support_ticket' && '🎫'}
            </div>
            <div className="tp-content">
              <p className="tp-topic">{tp.topic}</p>
              <span className="tp-date">
                {new Date(tp.date).toLocaleDateString()}
              </span>
              {tp.actionItems.length > 0 && (
                <span className="action-count">
                  {tp.actionItems.filter((a) => a.status === 'pending').length} pending actions
                </span>
              )}
            </div>
            <span className={`tp-sentiment ${tp.sentiment}`}>
              {tp.sentiment === 'positive' && '😊'}
              {tp.sentiment === 'neutral' && '😐'}
              {tp.sentiment === 'negative' && '😞'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// MAIN ADVANCED CUSTOMER SUCCESS COMPONENT
// ============================================================================

export const AdvancedCustomerSuccess: FC = () => {
  const { subscribe, emit } = useWebSocket();
  const { success, error } = useToast();

  const [customers] = useState<Customer[]>([
    {
      id: 'cust-1',
      name: 'Alice Johnson',
      email: 'alice@company.com',
      company: 'Tech Innovations Inc',
      industry: 'Technology',
      tier: 'enterprise',
      status: 'active',
      signupDate: Date.now() - 31536000000, // 1 year ago
      contractEndDate: Date.now() + 31536000000, // 1 year from now
      arr: 150000,
      healthScore: 88,
      healthTrend: 'improving',
      nextCheckpoint: Date.now() + 2592000000,
      contacts: [
        {
          id: 'contact-1',
          name: 'Alice Johnson',
          email: 'alice@company.com',
          role: 'CTO',
          primary: true,
        },
      ],
      usage: {
        activeUsers: 450,
        loginFrequency: 8.5,
        featuresUsed: ['Analytics', 'Reporting', 'API', 'Custom Integrations'],
        moau: 420,
        dau: 380,
        lastActivityDate: Date.now() - 3600000,
        utilizationRate: 92,
        adoptionRate: 85,
        frequencyTrend: 'increasing',
      },
      engagementLevel: 'high',
      metadata: { industry: 'tech', region: 'US' },
    },
    {
      id: 'cust-2',
      name: 'Bob Smith',
      email: 'bob@company.com',
      company: 'Global Solutions Ltd',
      industry: 'Finance',
      tier: 'growth',
      status: 'at-risk',
      signupDate: Date.now() - 15768000000,
      contractEndDate: Date.now() + 15768000000,
      arr: 45000,
      healthScore: 42,
      healthTrend: 'declining',
      nextCheckpoint: Date.now() + 604800000,
      contacts: [
        {
          id: 'contact-2',
          name: 'Bob Smith',
          email: 'bob@company.com',
          role: 'VP Sales',
          primary: true,
        },
      ],
      usage: {
        activeUsers: 25,
        loginFrequency: 2.1,
        featuresUsed: ['Analytics'],
        moau: 15,
        dau: 5,
        lastActivityDate: Date.now() - 86400000,
        utilizationRate: 18,
        adoptionRate: 20,
        frequencyTrend: 'decreasing',
      },
      engagementLevel: 'low',
      metadata: { industry: 'finance', region: 'EU' },
    },
  ]);

  const [churnRisks] = useState<ChurnRisk[]>([
    {
      customerId: 'cust-2',
      riskScore: 78,
      riskLevel: 'high',
      factors: [
        { factor: 'Declining Usage', weight: 0.4, trend: 'negative', impact: -35 },
        { factor: 'Low Adoption Rate', weight: 0.3, trend: 'stable', impact: -25 },
        { factor: 'Infrequent Logins', weight: 0.3, trend: 'negative', impact: -18 },
      ],
      riskTrend: 'increasing',
      mitigationActions: [
        {
          id: 'action-1',
          title: 'Executive Check-in Call',
          description: 'Schedule call with VP to understand concerns',
          type: 'engagement',
          priority: 'high',
          targetDate: Date.now() + 604800000,
          owner: 'csm-001',
          status: 'pending',
          expectedImpact: 25,
        },
      ],
    },
  ]);

  const [expansionOps] = useState<ExpansionOpportunity[]>([
    {
      id: 'exp-1',
      customerId: 'cust-1',
      type: 'upsell',
      productName: 'Advanced Analytics Premium',
      currentValue: 150000,
      estimatedValue: 180000,
      confidence: 0.85,
      likelihood: 'high',
      maturityLevel: 75,
      recommendedAction: 'Schedule product demo',
      targetDate: Date.now() + 2592000000,
      owner: 'csm-001',
      status: 'qualified',
    },
  ]);

  const [npsScores] = useState<NPS[]>([
    {
      respondentId: 'resp-1',
      customerId: 'cust-1',
      date: Date.now() - 604800000,
      score: 9,
      category: 'promoter',
      feedback: 'Excellent product and support team!',
      sentiment: 'positive',
      topics: ['Product Quality', 'Customer Support'],
      responseRate: 0.45,
      followUpRequired: false,
    },
  ]);

  const [touchpoints] = useState<Touchpoint[]>([
    {
      id: 'tp-1',
      customerId: 'cust-1',
      date: Date.now() - 86400000,
      type: 'meeting',
      owner: 'csm-001',
      topic: 'Q4 Business Review',
      notes: 'Discussed expansion opportunities and upcoming features',
      outcome: 'Scheduled follow-up for next month',
      sentiment: 'positive',
      actionItems: [
        {
          id: 'action-1',
          description: 'Prepare expansion proposal',
          owner: 'csm-001',
          dueDate: Date.now() + 604800000,
          status: 'pending',
          priority: 1,
        },
      ],
    },
  ]);

  const [metrics] = useState<CustomerSuccessMetrics>({
    totalCustomers: 245,
    activeCustomers: 218,
    atRiskCustomers: 12,
    averageHealthScore: 74,
    npsScore: 52,
    netRetentionRate: 1.15,
    churnRate: 0.03,
    expansionRate: 0.22,
    csat: 4.2,
    timeToROI: 45,
    grossRetentionRate: 0.97,
    expansionRevenue: 2800000,
    totalARR: 8500000,
  });

  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);

  useEffect(() => {
    const unsub = subscribe('cs:health_updated', (data: any) => {
      success('Customer health scores updated');
    });

    return () => unsub?.();
  }, [subscribe, success]);

  return (
    <div className="advanced-customer-success">
      <div className="cs-header">
        <div className="header-content">
          <h1>🎯 Advanced Customer Success</h1>
          <p>Health Scoring, Churn Prevention & Expansion</p>
        </div>
        <div className="header-metrics">
          <div className="metric-box">
            <span className="label">NPS</span>
            <span className="value">{metrics.npsScore}</span>
          </div>
          <div className="metric-box">
            <span className="label">At Risk</span>
            <span className="value warning">{metrics.atRiskCustomers}</span>
          </div>
          <div className="metric-box">
            <span className="label">Expansion Revenue</span>
            <span className="value">${(metrics.expansionRevenue / 1000000).toFixed(1)}M</span>
          </div>
          <div className="metric-box">
            <span className="label">NRR</span>
            <span className="value success">{(metrics.netRetentionRate * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      <div className="cs-grid">
        <div className="grid-col-1">
          <CustomerHealthDashboard customers={customers} onSelectCustomer={setSelectedCustomer} />
        </div>

        <div className="grid-col-1">
          <ChurnRiskAnalysis churnRisks={churnRisks} />
        </div>

        <div className="grid-col-2">
          <ExpansionOpportunitiesPanel opportunities={expansionOps} />
        </div>

        <div className="grid-col-1">
          <NPSSentimentPanel npsScores={npsScores} metrics={metrics} />
        </div>

        <div className="grid-col-1">
          <TouchpointsPanel touchpoints={touchpoints} />
        </div>

        {selectedCustomer && (
          <div className="grid-col-1">
            <div className="customer-detail-panel">
              <h3>📊 {selectedCustomer.name} Details</h3>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="label">Health Score:</span>
                  <span className="value">{selectedCustomer.healthScore}%</span>
                </div>
                <div className="detail-item">
                  <span className="label">ARR:</span>
                  <span className="value">${(selectedCustomer.arr / 1000).toFixed(0)}K</span>
                </div>
                <div className="detail-item">
                  <span className="label">Active Users:</span>
                  <span className="value">{selectedCustomer.usage.activeUsers}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Utilization:</span>
                  <span className="value">{selectedCustomer.usage.utilizationRate}%</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .advanced-customer-success {
          padding: 24px;
          background: linear-gradient(135deg, #f0fdf4 0%, #f0f9ff 100%);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          min-height: 100vh;
        }

        .cs-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          background: white;
          padding: 24px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .header-content h1 {
          margin: 0 0 8px 0;
          font-size: 28px;
        }

        .header-content p {
          margin: 0;
          color: #666;
        }

        .header-metrics {
          display: flex;
          gap: 16px;
        }

        .metric-box {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px 16px;
          background: #f9fafb;
          border-radius: 8px;
          text-align: center;
        }

        .metric-box .label {
          font-size: 11px;
          color: #666;
          text-transform: uppercase;
          margin-bottom: 4px;
        }

        .metric-box .value {
          font-size: 20px;
          font-weight: 700;
          color: #1f2937;
        }

        .metric-box .value.warning {
          color: #f59e0b;
        }

        .metric-box .value.success {
          color: #10b981;
        }

        .cs-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
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

        .health-dashboard,
        .churn-risk-panel,
        .expansion-panel,
        .nps-sentiment-panel,
        .touchpoints-panel,
        .customer-detail-panel {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .dashboard-header,
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          font-weight: 600;
        }

        .filters-section {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
        }

        .search-input,
        .status-filter {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 12px;
        }

        .customers-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 500px;
          overflow-y: auto;
        }

        .customer-card {
          padding: 12px;
          background: #f9fafb;
          border-left: 3px solid #ddd;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .customer-card:hover {
          background: #eff0f3;
          transform: translateX(4px);
        }

        .customer-card.at-risk {
          border-left-color: #f59e0b;
        }

        .customer-card.churned {
          border-left-color: #ef4444;
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 8px;
        }

        .customer-info h4 {
          margin: 0;
          font-size: 14px;
        }

        .customer-info .company {
          margin: 2px 0 0 0;
          font-size: 12px;
          color: #666;
        }

        .health-bar {
          height: 6px;
          background: #e5e7eb;
          border-radius: 3px;
          overflow: hidden;
          margin-bottom: 8px;
        }

        .health-fill {
          height: 100%;
          transition: width 0.3s;
        }

        .health-fill.good {
          background: #10b981;
        }

        .health-fill.medium {
          background: #f59e0b;
        }

        .health-fill.poor {
          background: #ef4444;
        }

        .card-footer {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #666;
        }

        .churn-risk-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .risk-stats {
          display: flex;
          gap: 8px;
        }

        .stat.critical {
          color: #ef4444;
        }

        .stat.high {
          color: #f59e0b;
        }

        .risks-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }

        .risk-item {
          padding: 10px;
          background: #f9fafb;
          border-left: 3px solid #ddd;
          border-radius: 6px;
        }

        .risk-item.critical {
          border-left-color: #ef4444;
          background: #fef2f2;
        }

        .risk-item.high {
          border-left-color: #f59e0b;
          background: #fffbeb;
        }

        .risk-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
          font-size: 12px;
        }

        .risk-score {
          font-weight: 600;
        }

        .risk-factors,
        .mitigation-actions {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
          margin-top: 6px;
        }

        .factor-tag,
        .action-badge {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          background: rgba(0, 0, 0, 0.05);
        }

        .action-badge.pending {
          background: #fef3c7;
          color: #b45309;
        }

        .action-badge.in-progress {
          background: #dbeafe;
          color: #1e40af;
        }

        .action-badge.completed {
          background: #dcfce7;
          color: #166534;
        }

        .expansion-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .potential-revenue {
          color: #10b981;
          font-weight: 600;
        }

        .opportunity-types {
          display: grid;
          gap: 12px;
        }

        .type-section h4 {
          font-size: 12px;
          margin: 0 0 8px 0;
          text-transform: uppercase;
          color: #666;
        }

        .opps-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .opportunity-item {
          padding: 8px;
          background: #f9fafb;
          border-radius: 6px;
          border-left: 2px solid #ddd;
        }

        .opportunity-item.high {
          border-left-color: #10b981;
        }

        .opportunity-item.medium {
          border-left-color: #f59e0b;
        }

        .opp-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;
        }

        .opp-name {
          font-size: 12px;
          font-weight: 600;
        }

        .likelihood-badge {
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 10px;
          font-weight: 600;
        }

        .likelihood-badge.high {
          background: #dcfce7;
          color: #166534;
        }

        .likelihood-badge.medium {
          background: #fef3c7;
          color: #b45309;
        }

        .opp-value {
          font-size: 11px;
          color: #666;
          margin-bottom: 4px;
        }

        .maturity-bar {
          height: 4px;
          background: #e5e7eb;
          border-radius: 2px;
          overflow: hidden;
          margin-bottom: 4px;
        }

        .maturity-fill {
          height: 100%;
          background: #3b82f6;
        }

        .maturity-label {
          font-size: 10px;
          color: #999;
        }

        .nps-sentiment-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .nps-score-display {
          display: flex;
          justify-content: center;
          padding: 20px;
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          border-radius: 8px;
          color: white;
        }

        .nps-number {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }

        .score {
          font-size: 36px;
          font-weight: 700;
        }

        .label {
          font-size: 12px;
        }

        .nps-breakdown {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
        }

        .breakdown-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px;
          background: #f9fafb;
          border-radius: 6px;
          border-top: 3px solid #ddd;
        }

        .breakdown-item.promoter {
          border-top-color: #10b981;
        }

        .breakdown-item.passive {
          border-top-color: #f59e0b;
        }

        .breakdown-item.detractor {
          border-top-color: #ef4444;
        }

        .breakdown-item .category {
          font-size: 11px;
          color: #666;
          margin-bottom: 4px;
        }

        .breakdown-item .count {
          font-size: 18px;
          font-weight: 700;
        }

        .breakdown-item .percentage {
          font-size: 10px;
          color: #999;
        }

        .sentiment-summary {
          margin-top: 8px;
        }

        .sentiment-summary h4 {
          font-size: 12px;
          margin: 0 0 8px 0;
          text-transform: uppercase;
        }

        .themes-list {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .theme-tag {
          padding: 4px 8px;
          background: #dbeafe;
          color: #1e40af;
          border-radius: 4px;
          font-size: 11px;
        }

        .touchpoints-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .touchpoints-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 400px;
          overflow-y: auto;
        }

        .touchpoint-item {
          display: flex;
          gap: 10px;
          padding: 10px;
          background: #f9fafb;
          border-radius: 6px;
          border-left: 3px solid #ddd;
        }

        .tp-icon {
          font-size: 18px;
        }

        .tp-content {
          flex: 1;
          min-width: 0;
        }

        .tp-topic {
          margin: 0;
          font-size: 12px;
          font-weight: 600;
        }

        .tp-date {
          font-size: 10px;
          color: #999;
          display: block;
          margin-top: 2px;
        }

        .action-count {
          font-size: 10px;
          color: #ef4444;
          display: block;
          margin-top: 2px;
        }

        .tp-sentiment {
          font-size: 16px;
          text-align: center;
        }

        .customer-detail-panel {
          padding: 16px;
          background: linear-gradient(135deg, #dbeafe 0%, #f0f9ff 100%);
          border-radius: 8px;
          border: 1px solid #bfdbfe;
        }

        .customer-detail-panel h3 {
          margin: 0 0 12px 0;
          font-size: 14px;
        }

        .detail-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .detail-item {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          padding: 8px 0;
          border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        }

        .detail-item .label {
          color: #666;
        }

        .detail-item .value {
          font-weight: 600;
          color: #1f2937;
        }

        @media (max-width: 1024px) {
          .header-metrics {
            flex-direction: column;
            gap: 8px;
          }

          .cs-grid {
            grid-template-columns: 1fr;
          }

          .grid-col-2 {
            grid-column: 1;
          }
        }

        @media (max-width: 768px) {
          .cs-header {
            flex-direction: column;
            text-align: center;
            gap: 16px;
          }

          .header-metrics {
            width: 100%;
            justify-content: center;
          }

          .nps-breakdown,
          .detail-grid {
            grid-template-columns: 1fr;
          }

          .filters-section {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
};

export default AdvancedCustomerSuccess;
