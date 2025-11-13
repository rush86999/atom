#!/bin/bash
# ATOM Enhanced Finance UI - Modern Dashboard Components

echo "🎨 ATOM ENHANCED FINANCE UI - MODERN DASHBOARD"
echo "=================================================="

# Step 1: Create Finance Dashboard Components
echo ""
echo "📊 Step 1: Create Finance Dashboard Components"
echo "-------------------------------------------------"

cat > ui/components/finance/FinanceDashboard.vue << 'EOF'
<template>
  <div class="finance-dashboard">
    <!-- Header Section -->
    <div class="dashboard-header">
      <div class="header-left">
        <h1 class="dashboard-title">Finance Intelligence</h1>
        <p class="dashboard-subtitle">Real-time financial insights and analytics</p>
      </div>
      <div class="header-right">
        <div class="date-range-selector">
          <v-select
            v-model="selectedDateRange"
            :items="dateRanges"
            item-text="label"
            item-value="value"
            outlined
            dense
            @change="onDateRangeChange"
          />
        </div>
        <div class="refresh-button">
          <v-btn
            color="primary"
            @click="refreshData"
            :loading="loading"
            icon
          >
            <v-icon>mdi-refresh</v-icon>
          </v-btn>
        </div>
      </div>
    </div>

    <!-- Key Metrics Cards -->
    <div class="metrics-grid">
      <div class="metric-card" v-for="metric in keyMetrics" :key="metric.id">
        <div class="metric-icon" :style="{ backgroundColor: metric.color }">
          <v-icon :color="metric.iconColor">{{ metric.icon }}</v-icon>
        </div>
        <div class="metric-content">
          <div class="metric-value">{{ formatCurrency(metric.value) }}</div>
          <div class="metric-label">{{ metric.label }}</div>
          <div class="metric-change" :class="metric.trend">
            <v-icon small>{{ metric.trendIcon }}</v-icon>
            {{ metric.change }}%
          </div>
        </div>
      </div>
    </div>

    <!-- Charts Section -->
    <div class="charts-section">
      <div class="chart-row">
        <!-- Revenue Chart -->
        <div class="chart-container large">
          <div class="chart-header">
            <h3>Revenue Trend</h3>
            <v-menu>
              <template v-slot:activator="{ on, attrs }">
                <v-btn icon v-bind="attrs" v-on="on">
                  <v-icon>mdi-dots-vertical</v-icon>
                </v-btn>
              </template>
              <v-list>
                <v-list-item @click="exportChart('revenue')">
                  <v-list-item-title>Export</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </div>
          <div class="chart-content">
            <canvas ref="revenueChart" id="revenueChart"></canvas>
          </div>
        </div>

        <!-- Expense Breakdown -->
        <div class="chart-container medium">
          <div class="chart-header">
            <h3>Expense Breakdown</h3>
          </div>
          <div class="chart-content">
            <canvas ref="expenseChart" id="expenseChart"></canvas>
          </div>
        </div>
      </div>

      <div class="chart-row">
        <!-- Cash Flow -->
        <div class="chart-container medium">
          <div class="chart-header">
            <h3>Cash Flow</h3>
          </div>
          <div class="chart-content">
            <canvas ref="cashFlowChart" id="cashFlowChart"></canvas>
          </div>
        </div>

        <!-- Profit Margin -->
        <div class="chart-container medium">
          <div class="chart-header">
            <h3>Profit Margin</h3>
          </div>
          <div class="chart-content">
            <canvas ref="profitChart" id="profitChart"></canvas>
          </div>
        </div>

        <!-- Budget Variance -->
        <div class="chart-container medium">
          <div class="chart-header">
            <h3>Budget Variance</h3>
          </div>
          <div class="chart-content">
            <canvas ref="budgetChart" id="budgetChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Transactions -->
    <div class="transactions-section">
      <div class="section-header">
        <h3>Recent Transactions</h3>
        <v-btn text color="primary" @click="viewAllTransactions">
          View All
          <v-icon right>mdi-arrow-right</v-icon>
        </v-btn>
      </div>
      <div class="transactions-table">
        <v-data-table
          :headers="transactionHeaders"
          :items="recentTransactions"
          :loading="transactionsLoading"
          class="elevation-1"
        >
          <template v-slot:item.amount="{ item }">
            <span :class="getAmountClass(item.amount)">
              {{ formatCurrency(item.amount) }}
            </span>
          </template>
          <template v-slot:item.category="{ item }">
            <v-chip :color="getCategoryColor(item.category)" small>
              {{ item.category }}
            </v-chip>
          </template>
          <template v-slot:item.status="{ item }">
            <v-chip
              :color="getStatusColor(item.status)"
              small
              outlined
            >
              {{ item.status }}
            </v-chip>
          </template>
        </v-data-table>
      </div>
    </div>

    <!-- Alerts and Notifications -->
    <div class="alerts-section">
      <div class="section-header">
        <h3>Financial Alerts</h3>
        <v-badge :content="unreadAlerts" color="error" overlap>
          <v-icon>mdi-bell</v-icon>
        </v-badge>
      </div>
      <div class="alerts-list">
        <div
          class="alert-item"
          v-for="alert in financialAlerts"
          :key="alert.id"
          :class="alert.severity"
        >
          <div class="alert-icon">
            <v-icon :color="getAlertColor(alert.severity)">
              {{ getAlertIcon(alert.severity) }}
            </v-icon>
          </div>
          <div class="alert-content">
            <div class="alert-title">{{ alert.title }}</div>
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
          </div>
          <div class="alert-actions">
            <v-btn icon small @click="dismissAlert(alert.id)">
              <v-icon small>mdi-close</v-icon>
            </v-btn>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { Chart, registerables } from 'chart.js'
import { financeApi } from '@/api/finance'
import { formatCurrency, formatTime } from '@/utils/format'

Chart.register(...registerables)

export default {
  name: 'FinanceDashboard',
  data() {
    return {
      loading: false,
      transactionsLoading: false,
      selectedDateRange: '30d',
      dateRanges: [
        { label: 'Last 7 Days', value: '7d' },
        { label: 'Last 30 Days', value: '30d' },
        { label: 'Last Quarter', value: '90d' },
        { label: 'Last Year', value: '365d' }
      ],
      keyMetrics: [],
      recentTransactions: [],
      financialAlerts: [],
      unreadAlerts: 0,
      charts: {
        revenue: null,
        expense: null,
        cashFlow: null,
        profit: null,
        budget: null
      },
      transactionHeaders: [
        { text: 'Date', value: 'date' },
        { text: 'Description', value: 'description' },
        { text: 'Category', value: 'category' },
        { text: 'Amount', value: 'amount' },
        { text: 'Status', value: 'status' }
      ]
    }
  },
  async mounted() {
    await this.loadDashboardData()
    this.initializeCharts()
  },
  methods: {
    async loadDashboardData() {
      this.loading = true
      try {
        // Load key metrics
        const metricsResponse = await financeApi.getMetrics({
          timeRange: this.selectedDateRange
        })
        this.keyMetrics = metricsResponse.data.metrics

        // Load recent transactions
        this.transactionsLoading = true
        const transactionsResponse = await financeApi.getTransactions({
          limit: 10,
          sortBy: 'date',
          sortOrder: 'desc'
        })
        this.recentTransactions = transactionsResponse.data.transactions
        this.transactionsLoading = false

        // Load financial alerts
        const alertsResponse = await financeApi.getAlerts({
          unread: true,
          limit: 5
        })
        this.financialAlerts = alertsResponse.data.alerts
        this.unreadAlerts = alertsResponse.data.unreadCount

      } catch (error) {
        console.error('Error loading dashboard data:', error)
        this.$toast.error('Failed to load dashboard data')
      } finally {
        this.loading = false
      }
    },

    initializeCharts() {
      this.$nextTick(() => {
        this.initializeRevenueChart()
        this.initializeExpenseChart()
        this.initializeCashFlowChart()
        this.initializeProfitChart()
        this.initializeBudgetChart()
      })
    },

    initializeRevenueChart() {
      const ctx = this.$refs.revenueChart.getContext('2d')
      this.charts.revenue = new Chart(ctx, {
        type: 'line',
        data: {
          labels: this.generateDateLabels(),
          datasets: [{
            label: 'Revenue',
            data: this.generateRandomData(30, 50000, 150000),
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)',
            tension: 0.4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    initializeExpenseChart() {
      const ctx = this.$refs.expenseChart.getContext('2d')
      this.charts.expense = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Software', 'Office', 'Travel', 'Marketing', 'Salaries'],
          datasets: [{
            data: [15000, 5000, 10000, 25000, 65000],
            backgroundColor: [
              '#FF6384',
              '#36A2EB',
              '#FFCE56',
              '#4BC0C0',
              '#9966FF'
            ]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom'
            }
          }
        }
      })
    },

    initializeCashFlowChart() {
      const ctx = this.$refs.cashFlowChart.getContext('2d')
      this.charts.cashFlow = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          datasets: [{
            label: 'Inflow',
            data: [120000, 135000, 125000, 140000, 130000, 145000],
            backgroundColor: 'rgba(75, 192, 192, 0.8)'
          }, {
            label: 'Outflow',
            data: [100000, 110000, 95000, 105000, 115000, 120000],
            backgroundColor: 'rgba(255, 99, 132, 0.8)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    initializeProfitChart() {
      const ctx = this.$refs.profitChart.getContext('2d')
      this.charts.profit = new Chart(ctx, {
        type: 'line',
        data: {
          labels: this.generateDateLabels(),
          datasets: [{
            label: 'Profit Margin %',
            data: this.generateRandomData(30, 15, 35),
            borderColor: 'rgb(54, 162, 235)',
            backgroundColor: 'rgba(54, 162, 235, 0.1)',
            tension: 0.4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 50,
              ticks: {
                callback: (value) => value + '%'
              }
            }
          }
        }
      })
    },

    initializeBudgetChart() {
      const ctx = this.$refs.budgetChart.getContext('2d')
      this.charts.budget = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Software', 'Marketing', 'Travel', 'Office', 'Equipment'],
          datasets: [{
            label: 'Budget',
            data: [20000, 30000, 15000, 10000, 25000],
            backgroundColor: 'rgba(153, 102, 255, 0.8)'
          }, {
            label: 'Actual',
            data: [15000, 25000, 12000, 8000, 18000],
            backgroundColor: 'rgba(255, 159, 64, 0.8)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    generateDateLabels() {
      const labels = []
      const now = new Date()
      for (let i = 29; i >= 0; i--) {
        const date = new Date(now)
        date.setDate(date.getDate() - i)
        labels.push(date.toLocaleDateString())
      }
      return labels
    },

    generateRandomData(count, min, max) {
      const data = []
      for (let i = 0; i < count; i++) {
        data.push(Math.floor(Math.random() * (max - min + 1)) + min)
      }
      return data
    },

    async refreshData() {
      await this.loadDashboardData()
      this.updateCharts()
    },

    updateCharts() {
      // Update charts with new data
      Object.keys(this.charts).forEach(key => {
        if (this.charts[key]) {
          this.charts[key].update()
        }
      })
    },

    onDateRangeChange() {
      this.loadDashboardData()
    },

    formatCurrency,
    formatTime,

    getAmountClass(amount) {
      return amount > 0 ? 'positive' : 'negative'
    },

    getCategoryColor(category) {
      const colors = {
        'Software': 'blue',
        'Food': 'green',
        'Travel': 'orange',
        'Office': 'purple',
        'Marketing': 'pink',
        'Salaries': 'indigo'
      }
      return colors[category] || 'grey'
    },

    getStatusColor(status) {
      const colors = {
        'completed': 'success',
        'pending': 'warning',
        'failed': 'error',
        'cancelled': 'grey'
      }
      return colors[status] || 'grey'
    },

    getAlertColor(severity) {
      const colors = {
        'critical': 'error',
        'high': 'warning',
        'medium': 'info',
        'low': 'success'
      }
      return colors[severity] || 'grey'
    },

    getAlertIcon(severity) {
      const icons = {
        'critical': 'mdi-alert-circle',
        'high': 'mdi-alert',
        'medium': 'mdi-information',
        'low': 'mdi-check-circle'
      }
      return icons[severity] || 'mdi-information'
    },

    viewAllTransactions() {
      this.$router.push('/finance/transactions')
    },

    exportChart(chartType) {
      // Export chart functionality
      console.log(`Exporting ${chartType} chart`)
    },

    dismissAlert(alertId) {
      this.financialAlerts = this.financialAlerts.filter(alert => alert.id !== alertId)
      this.unreadAlerts = Math.max(0, this.unreadAlerts - 1)
    }
  }
}
</script>

<style scoped>
.finance-dashboard {
  padding: 24px;
  background: #f8f9fa;
  min-height: 100vh;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.dashboard-title {
  font-size: 32px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.dashboard-subtitle {
  font-size: 16px;
  color: #6c757d;
  margin: 8px 0 0 0;
}

.header-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.metric-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.metric-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-content {
  flex: 1;
}

.metric-value {
  font-size: 28px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.metric-label {
  font-size: 14px;
  color: #6c757d;
  margin-bottom: 8px;
}

.metric-change {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
}

.metric-change.positive {
  color: #28a745;
}

.metric-change.negative {
  color: #dc3545;
}

.charts-section {
  margin-bottom: 32px;
}

.chart-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
}

.chart-container.large {
  grid-column: 1 / -1;
}

.chart-container {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.chart-content {
  height: 300px;
  position: relative;
}

.transactions-section,
.alerts-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 12px;
  border-left: 4px solid;
}

.alert-item.critical {
  background: #f8d7da;
  border-left-color: #dc3545;
}

.alert-item.high {
  background: #fff3cd;
  border-left-color: #ffc107;
}

.alert-item.medium {
  background: #d1ecf1;
  border-left-color: #17a2b8;
}

.alert-item.low {
  background: #d4edda;
  border-left-color: #28a745;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
}

.alert-message {
  font-size: 14px;
  color: #6c757d;
  margin-bottom: 4px;
}

.alert-time {
  font-size: 12px;
  color: #6c757d;
}

.positive {
  color: #28a745;
}

.negative {
  color: #dc3545;
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .chart-row {
    grid-template-columns: 1fr;
  }

  .header-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
EOF

echo "✅ Finance dashboard component created"

# Step 2: Create Finance Analytics Components
echo ""
echo "📈 Step 2: Create Finance Analytics Components"
echo "--------------------------------------------------"

cat > ui/components/finance/FinanceAnalytics.vue << 'EOF'
<template>
  <div class="finance-analytics">
    <!-- Analytics Header -->
    <div class="analytics-header">
      <h1>Financial Analytics</h1>
      <div class="controls">
        <v-select
          v-model="selectedPeriod"
          :items="periods"
          label="Period"
          outlined
          dense
          @change="updateAnalytics"
        />
        <v-select
          v-model="selectedCategory"
          :items="categories"
          label="Category"
          outlined
          dense
          clearable
          @change="updateAnalytics"
        />
        <v-btn
          color="primary"
          @click="generateReport"
          :loading="reportGenerating"
        >
          <v-icon left>mdi-file-chart</v-icon>
          Generate Report
        </v-btn>
      </div>
    </div>

    <!-- Key Performance Indicators -->
    <div class="kpi-section">
      <h2>Key Performance Indicators</h2>
      <div class="kpi-grid">
        <div class="kpi-card" v-for="kpi in kpis" :key="kpi.id">
          <div class="kpi-header">
            <span class="kpi-title">{{ kpi.title }}</span>
            <v-icon :color="kpi.trend === 'up' ? 'success' : 'error'">
              {{ kpi.trend === 'up' ? 'mdi-trending-up' : 'mdi-trending-down' }}
            </v-icon>
          </div>
          <div class="kpi-value">{{ formatKpiValue(kpi.value, kpi.unit) }}</div>
          <div class="kpi-comparison">
            <span class="comparison-label">vs last period</span>
            <span :class="kpi.comparison > 0 ? 'positive' : 'negative'">
              {{ kpi.comparison > 0 ? '+' : '' }}{{ kpi.comparison }}%
            </span>
          </div>
          <div class="kpi-sparkline">
            <canvas :ref="`sparkline-${kpi.id}`"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- Advanced Charts -->
    <div class="charts-section">
      <h2>Advanced Analytics</h2>
      
      <!-- Revenue Analysis -->
      <div class="chart-container full-width">
        <div class="chart-header">
          <h3>Revenue Analysis</h3>
          <div class="chart-controls">
            <v-btn-toggle
              v-model="revenueView"
              mandatory
              dense
              @change="updateRevenueChart"
            >
              <v-btn value="monthly">Monthly</v-btn>
              <v-btn value="quarterly">Quarterly</v-btn>
              <v-btn value="yearly">Yearly</v-btn>
            </v-btn-toggle>
          </div>
        </div>
        <div class="chart-content">
          <canvas ref="revenueAnalysisChart"></canvas>
        </div>
      </div>

      <!-- Cost Structure Analysis -->
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-header">
            <h3>Cost Structure</h3>
          </div>
          <div class="chart-content">
            <canvas ref="costStructureChart"></canvas>
          </div>
        </div>

        <!-- Profit Margins -->
        <div class="chart-container">
          <div class="chart-header">
            <h3>Profit Margins</h3>
          </div>
          <div class="chart-content">
            <canvas ref="profitMarginsChart"></canvas>
          </div>
        </div>
      </div>

      <!-- Cash Flow Analysis -->
      <div class="chart-container full-width">
        <div class="chart-header">
          <h3>Cash Flow Analysis</h3>
        </div>
        <div class="chart-content">
          <canvas ref="cashFlowAnalysisChart"></canvas>
        </div>
      </div>

      <!-- Budget vs Actual -->
      <div class="chart-container full-width">
        <div class="chart-header">
          <h3>Budget vs Actual</h3>
        </div>
        <div class="chart-content">
          <canvas ref="budgetActualChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Financial Insights -->
    <div class="insights-section">
      <h2>AI-Powered Insights</h2>
      <div class="insights-grid">
        <div
          class="insight-card"
          v-for="insight in insights"
          :key="insight.id"
          :class="insight.type"
        >
          <div class="insight-header">
            <v-icon :color="getInsightColor(insight.type)">
              {{ getInsightIcon(insight.type) }}
            </v-icon>
            <span class="insight-title">{{ insight.title }}</span>
          </div>
          <div class="insight-content">
            <p>{{ insight.description }}</p>
          </div>
          <div class="insight-actions">
            <v-btn text small color="primary" @click="exploreInsight(insight)">
              Explore
            </v-btn>
          </div>
        </div>
      </div>
    </div>

    <!-- Report Generation Modal -->
    <v-dialog v-model="reportModal" max-width="600">
      <v-card>
        <v-card-title>
          <span class="headline">Generate Financial Report</span>
        </v-card-title>
        <v-card-text>
          <v-form ref="reportForm" v-model="reportFormValid">
            <v-text-field
              v-model="reportTitle"
              label="Report Title"
              :rules="[v => !!v || 'Title is required']"
              outlined
            />
            <v-select
              v-model="reportType"
              :items="reportTypes"
              label="Report Type"
              :rules="[v => !!v || 'Report type is required']"
              outlined
            />
            <v-select
              v-model="reportFormat"
              :items="reportFormats"
              label="Report Format"
              outlined
            />
            <v-date-picker
              v-model="reportDateRange"
              range
              label="Date Range"
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="reportModal = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="generateFinancialReport"
            :loading="reportGenerating"
            :disabled="!reportFormValid"
          >
            Generate
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
import { Chart, registerables } from 'chart.js'
import { financeApi } from '@/api/finance'
import { formatCurrency } from '@/utils/format'

Chart.register(...registerables)

export default {
  name: 'FinanceAnalytics',
  data() {
    return {
      loading: false,
      reportGenerating: false,
      selectedPeriod: '30d',
      selectedCategory: null,
      revenueView: 'monthly',
      reportModal: false,
      reportFormValid: true,
      reportTitle: '',
      reportType: '',
      reportFormat: 'pdf',
      reportDateRange: [],
      periods: [
        { text: 'Last 7 Days', value: '7d' },
        { text: 'Last 30 Days', value: '30d' },
        { text: 'Last Quarter', value: '90d' },
        { text: 'Last Year', value: '365d' }
      ],
      categories: [
        { text: 'All Categories', value: null },
        { text: 'Revenue', value: 'revenue' },
        { text: 'Expenses', value: 'expenses' },
        { text: 'Investments', value: 'investments' }
      ],
      reportTypes: [
        { text: 'Executive Summary', value: 'executive' },
        { text: 'Detailed Financial Report', value: 'detailed' },
        { text: 'Budget Analysis', value: 'budget' },
        { text: 'Cash Flow Statement', value: 'cashflow' }
      ],
      reportFormats: [
        { text: 'PDF', value: 'pdf' },
        { text: 'Excel', value: 'excel' },
        { text: 'CSV', value: 'csv' }
      ],
      kpis: [],
      insights: [],
      charts: {}
    }
  },
  async mounted() {
    await this.loadAnalyticsData()
    this.initializeCharts()
  },
  methods: {
    async loadAnalyticsData() {
      this.loading = true
      try {
        // Load KPIs
        const kpisResponse = await financeApi.getKPIs({
          period: this.selectedPeriod,
          category: this.selectedCategory
        })
        this.kpis = kpisResponse.data.kpis

        // Load AI insights
        const insightsResponse = await financeApi.getInsights({
          period: this.selectedPeriod
        })
        this.insights = insightsResponse.data.insights

      } catch (error) {
        console.error('Error loading analytics data:', error)
        this.$toast.error('Failed to load analytics data')
      } finally {
        this.loading = false
      }
    },

    initializeCharts() {
      this.$nextTick(() => {
        this.initializeRevenueAnalysisChart()
        this.initializeCostStructureChart()
        this.initializeProfitMarginsChart()
        this.initializeCashFlowAnalysisChart()
        this.initializeBudgetActualChart()
        
        // Initialize sparklines
        this.kpis.forEach(kpi => {
          this.initializeSparkline(kpi.id)
        })
      })
    },

    initializeRevenueAnalysisChart() {
      const ctx = this.$refs.revenueAnalysisChart.getContext('2d')
      this.charts.revenue = new Chart(ctx, {
        type: 'line',
        data: {
          labels: this.generateTimeLabels(),
          datasets: [{
            label: 'Revenue',
            data: this.generateRevenueData(),
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)',
            tension: 0.4,
            fill: true
          }, {
            label: 'Target',
            data: this.generateTargetData(),
            borderColor: 'rgb(255, 99, 132)',
            backgroundColor: 'rgba(255, 99, 132, 0.1)',
            borderDash: [5, 5],
            fill: false
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            intersect: false,
            mode: 'index'
          },
          plugins: {
            legend: {
              position: 'top'
            },
            tooltip: {
              callbacks: {
                label: (context) => {
                  return context.dataset.label + ': ' + formatCurrency(context.parsed.y)
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    initializeCostStructureChart() {
      const ctx = this.$refs.costStructureChart.getContext('2d')
      this.charts.costStructure = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Direct Costs', 'Indirect Costs', 'Labor', 'Materials', 'Overhead'],
          datasets: [{
            data: [45000, 25000, 65000, 35000, 20000],
            backgroundColor: [
              '#FF6384',
              '#36A2EB',
              '#FFCE56',
              '#4BC0C0',
              '#9966FF'
            ]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom'
            },
            tooltip: {
              callbacks: {
                label: (context) => {
                  return context.label + ': ' + formatCurrency(context.parsed)
                }
              }
            }
          }
        }
      })
    },

    initializeProfitMarginsChart() {
      const ctx = this.$refs.profitMarginsChart.getContext('2d')
      this.charts.profitMargins = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Q1', 'Q2', 'Q3', 'Q4'],
          datasets: [{
            label: 'Gross Margin',
            data: [35, 38, 42, 40],
            backgroundColor: 'rgba(75, 192, 192, 0.8)'
          }, {
            label: 'Net Margin',
            data: [15, 18, 22, 20],
            backgroundColor: 'rgba(54, 162, 235, 0.8)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 50,
              ticks: {
                callback: (value) => value + '%'
              }
            }
          }
        }
      })
    },

    initializeCashFlowAnalysisChart() {
      const ctx = this.$refs.cashFlowAnalysisChart.getContext('2d')
      this.charts.cashFlow = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: this.generateTimeLabels(),
          datasets: [{
            label: 'Operating Cash Flow',
            data: this.generateCashFlowData(),
            backgroundColor: 'rgba(75, 192, 192, 0.8)'
          }, {
            label: 'Investing Cash Flow',
            data: this.generateInvestingCashFlowData(),
            backgroundColor: 'rgba(255, 99, 132, 0.8)'
          }, {
            label: 'Financing Cash Flow',
            data: this.generateFinancingCashFlowData(),
            backgroundColor: 'rgba(255, 206, 86, 0.8)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true
            },
            y: {
              stacked: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    initializeBudgetActualChart() {
      const ctx = this.$refs.budgetActualChart.getContext('2d')
      this.charts.budgetActual = new Chart(ctx, {
        type: 'line',
        data: {
          labels: this.generateTimeLabels(),
          datasets: [{
            label: 'Budget',
            data: this.generateBudgetData(),
            borderColor: 'rgb(153, 102, 255)',
            backgroundColor: 'rgba(153, 102, 255, 0.1)',
            borderDash: [5, 5],
            fill: false
          }, {
            label: 'Actual',
            data: this.generateActualData(),
            borderColor: 'rgb(255, 159, 64)',
            backgroundColor: 'rgba(255, 159, 64, 0.1)',
            tension: 0.4,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (value) => formatCurrency(value)
              }
            }
          }
        }
      })
    },

    initializeSparkline(kpiId) {
      const canvas = this.$refs[`sparkline-${kpiId}`]
      if (canvas && canvas.length > 0) {
        const ctx = canvas[0].getContext('2d')
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: Array(10).fill(''),
            datasets: [{
              data: this.generateSparklineData(),
              borderColor: 'rgb(75, 192, 192)',
              borderWidth: 2,
              pointRadius: 0,
              fill: false
            }]
          },
          options: {
            responsive: false,
            plugins: {
              legend: { display: false },
              tooltip: { enabled: false }
            },
            scales: {
              x: { display: false },
              y: { display: false }
            }
          }
        })
      }
    },

    generateTimeLabels() {
      const labels = []
      const now = new Date()
      for (let i = 11; i >= 0; i--) {
        const date = new Date(now)
        date.setMonth(date.getMonth() - i)
        labels.push(date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }))
      }
      return labels
    },

    generateRevenueData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 50000) + 100000)
    },

    generateTargetData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 20000) + 120000)
    },

    generateCashFlowData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 30000) + 20000)
    },

    generateInvestingCashFlowData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 15000) - 10000)
    },

    generateFinancingCashFlowData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 10000) - 5000)
    },

    generateBudgetData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 30000) + 80000)
    },

    generateActualData() {
      return Array(12).fill(0).map(() => Math.floor(Math.random() * 35000) + 75000)
    },

    generateSparklineData() {
      return Array(10).fill(0).map(() => Math.floor(Math.random() * 100) + 50)
    },

    async updateAnalytics() {
      await this.loadAnalyticsData()
      this.updateCharts()
    },

    updateCharts() {
      Object.keys(this.charts).forEach(key => {
        if (this.charts[key]) {
          this.charts[key].update()
        }
      })
    },

    updateRevenueChart() {
      if (this.charts.revenue) {
        // Update chart based on view
        this.charts.revenue.data.labels = this.generateTimeLabels()
        this.charts.revenue.update()
      }
    },

    generateReport() {
      this.reportModal = true
    },

    async generateFinancialReport() {
      this.reportGenerating = true
      try {
        const reportData = {
          title: this.reportTitle,
          type: this.reportType,
          format: this.reportFormat,
          dateRange: this.reportDateRange,
          period: this.selectedPeriod,
          category: this.selectedCategory
        }

        const response = await financeApi.generateReport(reportData)
        
        // Download report
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `${this.reportTitle}.${this.reportFormat}`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)

        this.$toast.success('Report generated successfully')
        this.reportModal = false

      } catch (error) {
        console.error('Error generating report:', error)
        this.$toast.error('Failed to generate report')
      } finally {
        this.reportGenerating = false
      }
    },

    formatKpiValue(value, unit) {
      if (unit === 'currency') {
        return formatCurrency(value)
      } else if (unit === 'percentage') {
        return value + '%'
      } else {
        return value.toLocaleString()
      }
    },

    getInsightColor(type) {
      const colors = {
        'opportunity': 'success',
        'risk': 'error',
        'trend': 'info',
        'recommendation': 'warning'
      }
      return colors[type] || 'grey'
    },

    getInsightIcon(type) {
      const icons = {
        'opportunity': 'mdi-lightbulb',
        'risk': 'mdi-alert',
        'trend': 'mdi-chart-line',
        'recommendation': 'mdi-thumb-up'
      }
      return icons[type] || 'mdi-information'
    },

    exploreInsight(insight) {
      // Navigate to detailed insight view
      console.log('Exploring insight:', insight)
    },

    formatCurrency
  }
}
</script>

<style scoped>
.finance-analytics {
  padding: 24px;
  background: #f8f9fa;
  min-height: 100vh;
}

.analytics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.analytics-header h1 {
  font-size: 32px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.controls {
  display: flex;
  gap: 16px;
  align-items: center;
}

.kpi-section,
.charts-section,
.insights-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 24px;
}

.kpi-section h2,
.charts-section h2,
.insights-section h2 {
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0 0 24px 0;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.kpi-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  position: relative;
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kpi-title {
  font-size: 14px;
  color: #6c757d;
  font-weight: 500;
}

.kpi-value {
  font-size: 32px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
}

.kpi-comparison {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.comparison-label {
  font-size: 12px;
  color: #6c757d;
}

.positive {
  color: #28a745;
}

.negative {
  color: #dc3545;
}

.kpi-sparkline {
  height: 40px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

.chart-container {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.chart-container.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.chart-content {
  height: 300px;
  position: relative;
}

.insights-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 24px;
}

.insight-card {
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid;
  transition: transform 0.2s ease;
}

.insight-card:hover {
  transform: translateY(-2px);
}

.insight-card.opportunity {
  background: #d4edda;
  border-left-color: #28a745;
}

.insight-card.risk {
  background: #f8d7da;
  border-left-color: #dc3545;
}

.insight-card.trend {
  background: #d1ecf1;
  border-left-color: #17a2b8;
}

.insight-card.recommendation {
  background: #fff3cd;
  border-left-color: #ffc107;
}

.insight-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.insight-title {
  font-weight: 600;
  color: #2c3e50;
}

.insight-content p {
  color: #6c757d;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.insight-actions {
  text-align: right;
}

@media (max-width: 768px) {
  .analytics-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .controls {
    flex-direction: column;
    width: 100%;
  }

  .chart-row {
    grid-template-columns: 1fr;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .insights-grid {
    grid-template-columns: 1fr;
  }
}
</style>
EOF

echo "✅ Finance analytics component created"

# Step 3: Create Finance Management Components
echo ""
echo "💰 Step 3: Create Finance Management Components"
echo "-------------------------------------------------"

cat > ui/components/finance/FinanceManagement.vue << 'EOF'
<template>
  <div class="finance-management">
    <!-- Management Header -->
    <div class="management-header">
      <h1>Finance Management</h1>
      <div class="header-actions">
        <v-btn
          color="primary"
          @click="showAddTransaction = true"
        >
          <v-icon left>mdi-plus</v-icon>
          Add Transaction
        </v-btn>
        <v-btn
          color="secondary"
          @click="exportData"
          :loading="exporting"
        >
          <v-icon left>mdi-download</v-icon>
          Export
        </v-btn>
      </div>
    </div>

    <!-- Tab Navigation -->
    <v-tabs v-model="activeTab" grow>
      <v-tab>Transactions</v-tab>
      <v-tab>Invoices</v-tab>
      <v-tab>Expenses</v-tab>
      <v-tab>Budget</v-tab>
      <v-tab>Reports</v-tab>
    </v-tabs>

    <v-tabs-items v-model="activeTab">
      <!-- Transactions Tab -->
      <v-tab-item>
        <div class="transactions-section">
          <div class="section-toolbar">
            <div class="filters">
              <v-text-field
                v-model="transactionSearch"
                label="Search transactions"
                prepend-inner-icon="mdi-magnify"
                outlined
                dense
                clearable
                @input="filterTransactions"
              />
              <v-select
                v-model="selectedCategory"
                :items="categories"
                label="Category"
                outlined
                dense
                clearable
                @change="filterTransactions"
              />
              <v-select
                v-model="selectedStatus"
                :items="statusOptions"
                label="Status"
                outlined
                dense
                clearable
                @change="filterTransactions"
              />
              <v-menu
                ref="dateMenu"
                v-model="dateMenu"
                :close-on-content-click="false"
                transition="scale-transition"
                offset-y
                min-width="auto"
              >
                <template v-slot:activator="{ on, attrs }">
                  <v-text-field
                    v-model="dateRangeText"
                    label="Date Range"
                    prepend-inner-icon="mdi-calendar"
                    readonly
                    outlined
                    dense
                    v-bind="attrs"
                    v-on="on"
                  />
                </template>
                <v-date-picker
                  v-model="dateRange"
                  range
                  @change="filterTransactions"
                />
              </v-menu>
            </div>
            <div class="view-controls">
              <v-btn-toggle
                v-model="transactionView"
                mandatory
                dense
              >
                <v-btn value="list">
                  <v-icon>mdi-view-list</v-icon>
                </v-btn>
                <v-btn value="grid">
                  <v-icon>mdi-view-grid</v-icon>
                </v-btn>
              </v-btn-toggle>
            </div>
          </div>

          <!-- Transactions Table/Grid -->
          <div class="transactions-content">
            <v-data-table
              v-if="transactionView === 'list'"
              :headers="transactionHeaders"
              :items="filteredTransactions"
              :loading="loading"
              :items-per-page="25"
              class="elevation-1"
              @click:row="editTransaction"
            >
              <template v-slot:item.amount="{ item }">
                <span :class="getAmountClass(item.amount)">
                  {{ formatCurrency(item.amount) }}
                </span>
              </template>
              <template v-slot:item.category="{ item }">
                <v-chip :color="getCategoryColor(item.category)" small>
                  {{ item.category }}
                </v-chip>
              </template>
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="getStatusColor(item.status)"
                  small
                  outlined
                >
                  {{ item.status }}
                </v-chip>
              </template>
              <template v-slot:item.actions="{ item }">
                <div class="action-buttons">
                  <v-btn icon small @click.stop="editTransaction(item)">
                    <v-icon small>mdi-pencil</v-icon>
                  </v-btn>
                  <v-btn icon small @click.stop="deleteTransaction(item)">
                    <v-icon small>mdi-delete</v-icon>
                  </v-btn>
                </div>
              </template>
            </v-data-table>

            <div v-else class="transactions-grid">
              <div
                class="transaction-card"
                v-for="transaction in filteredTransactions"
                :key="transaction.id"
                @click="editTransaction(transaction)"
              >
                <div class="card-header">
                  <span class="transaction-date">{{ formatDate(transaction.date) }}</span>
                  <v-chip :color="getStatusColor(transaction.status)" small>
                    {{ transaction.status }}
                  </v-chip>
                </div>
                <div class="card-content">
                  <div class="transaction-description">{{ transaction.description }}</div>
                  <div class="transaction-amount" :class="getAmountClass(transaction.amount)">
                    {{ formatCurrency(transaction.amount) }}
                  </div>
                </div>
                <div class="card-footer">
                  <v-chip :color="getCategoryColor(transaction.category)" small>
                    {{ transaction.category }}
                  </v-chip>
                  <span class="transaction-account">{{ transaction.account }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </v-tab-item>

      <!-- Invoices Tab -->
      <v-tab-item>
        <div class="invoices-section">
          <div class="section-toolbar">
            <v-btn
              color="primary"
              @click="showCreateInvoice = true"
            >
              <v-icon left>mdi-plus</v-icon>
              Create Invoice
            </v-btn>
          </div>

          <div class="invoices-grid">
            <div
              class="invoice-card"
              v-for="invoice in invoices"
              :key="invoice.id"
              @click="viewInvoice(invoice)"
            >
              <div class="invoice-header">
                <div class="invoice-number">{{ invoice.number }}</div>
                <v-chip
                  :color="getInvoiceStatusColor(invoice.status)"
                  small
                >
                  {{ invoice.status }}
                </v-chip>
              </div>
              <div class="invoice-content">
                <div class="customer-info">
                  <div class="customer-name">{{ invoice.customer.name }}</div>
                  <div class="customer-email">{{ invoice.customer.email }}</div>
                </div>
                <div class="invoice-amount">{{ formatCurrency(invoice.total) }}</div>
              </div>
              <div class="invoice-footer">
                <span class="invoice-date">Due: {{ formatDate(invoice.dueDate) }}</span>
                <v-btn icon small @click.stop="editInvoice(invoice)">
                  <v-icon small>mdi-pencil</v-icon>
                </v-btn>
              </div>
            </div>
          </div>
        </div>
      </v-tab-item>

      <!-- Expenses Tab -->
      <v-tab-item>
        <div class="expenses-section">
          <div class="section-toolbar">
            <v-btn
              color="primary"
              @click="showAddExpense = true"
            >
              <v-icon left>mdi-plus</v-icon>
              Add Expense
            </v-btn>
            <v-btn
              color="secondary"
              @click="scanReceipt"
            >
              <v-icon left>mdi-camera</v-icon>
              Scan Receipt
            </v-btn>
          </div>

          <div class="expenses-content">
            <v-data-table
              :headers="expenseHeaders"
              :items="expenses"
              :loading="loading"
              class="elevation-1"
            >
              <template v-slot:item.amount="{ item }">
                <span class="negative">{{ formatCurrency(item.amount) }}</span>
              </template>
              <template v-slot:item.category="{ item }">
                <v-chip :color="getCategoryColor(item.category)" small>
                  {{ item.category }}
                </v-chip>
              </template>
              <template v-slot:item.receipt="{ item }">
                <v-btn
                  v-if="item.receipt"
                  icon
                  small
                  @click="viewReceipt(item.receipt)"
                >
                  <v-icon small>mdi-receipt</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </div>
        </div>
      </v-tab-item>

      <!-- Budget Tab -->
      <v-tab-item>
        <div class="budget-section">
          <div class="section-toolbar">
            <v-btn
              color="primary"
              @click="showCreateBudget = true"
            >
              <v-icon left>mdi-plus</v-icon>
              Create Budget
            </v-btn>
          </div>

          <div class="budget-content">
            <div class="budget-overview">
              <div class="overview-card" v-for="overview in budgetOverview" :key="overview.id">
                <div class="overview-title">{{ overview.title }}</div>
                <div class="overview-amount">{{ formatCurrency(overview.amount) }}</div>
                <div class="overview-progress">
                  <v-progress-linear
                    :value="overview.percentage"
                    :color="getProgressColor(overview.percentage)"
                    height="8"
                  />
                </div>
                <div class="overview-details">
                  <span>{{ formatCurrency(overview.spent) }} / {{ formatCurrency(overview.budgeted) }}</span>
                  <span :class="getPercentageClass(overview.percentage)">
                    {{ overview.percentage }}%
                  </span>
                </div>
              </div>
            </div>

            <div class="budget-details">
              <v-data-table
                :headers="budgetHeaders"
                :items="budgets"
                :loading="loading"
                class="elevation-1"
              >
                <template v-slot:item.spent="{ item }">
                  <span :class="getAmountClass(item.budgeted - item.spent)">
                    {{ formatCurrency(item.spent) }}
                  </span>
                </template>
                <template v-slot:item.remaining="{ item }">
                  <span :class="getAmountClass(item.budgeted - item.spent)">
                    {{ formatCurrency(item.budgeted - item.spent) }}
                  </span>
                </template>
                <template v-slot:item.percentage="{ item }">
                  <div class="percentage-cell">
                    <v-progress-linear
                      :value="item.percentage"
                      :color="getProgressColor(item.percentage)"
                      height="8"
                      class="mb-2"
                    />
                    <span :class="getPercentageClass(item.percentage)">
                      {{ item.percentage }}%
                    </span>
                  </div>
                </template>
              </v-data-table>
            </div>
          </div>
        </div>
      </v-tab-item>

      <!-- Reports Tab -->
      <v-tab-item>
        <div class="reports-section">
          <div class="reports-grid">
            <div
              class="report-card"
              v-for="report in availableReports"
              :key="report.id"
              @click="generateReport(report)"
            >
              <div class="report-icon">
                <v-icon :color="report.color" large>{{ report.icon }}</v-icon>
              </div>
              <div class="report-content">
                <div class="report-title">{{ report.title }}</div>
                <div class="report-description">{{ report.description }}</div>
              </div>
              <div class="report-actions">
                <v-btn text small color="primary">
                  Generate
                </v-btn>
              </div>
            </div>
          </div>
        </div>
      </v-tab-item>
    </v-tabs-items>

    <!-- Add Transaction Dialog -->
    <v-dialog v-model="showAddTransaction" max-width="600">
      <v-card>
        <v-card-title>
          <span class="headline">Add Transaction</span>
        </v-card-title>
        <v-card-text>
          <v-form ref="transactionForm" v-model="transactionFormValid">
            <v-text-field
              v-model="newTransaction.description"
              label="Description"
              :rules="[v => !!v || 'Description is required']"
              outlined
            />
            <v-text-field
              v-model="newTransaction.amount"
              label="Amount"
              type="number"
              :rules="[v => !!v || 'Amount is required']"
              outlined
            />
            <v-select
              v-model="newTransaction.type"
              :items="transactionTypes"
              label="Type"
              outlined
            />
            <v-select
              v-model="newTransaction.category"
              :items="categories"
              label="Category"
              outlined
            />
            <v-text-field
              v-model="newTransaction.date"
              label="Date"
              type="date"
              outlined
            />
            <v-select
              v-model="newTransaction.account"
              :items="accounts"
              label="Account"
              outlined
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="showAddTransaction = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="saveTransaction"
            :disabled="!transactionFormValid"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
import { financeApi } from '@/api/finance'
import { formatCurrency, formatDate } from '@/utils/format'

export default {
  name: 'FinanceManagement',
  data() {
    return {
      loading: false,
      exporting: false,
      activeTab: 0,
      transactionView: 'list',
      showAddTransaction: false,
      showCreateInvoice: false,
      showAddExpense: false,
      showCreateBudget: false,
      transactionFormValid: true,
      transactionSearch: '',
      selectedCategory: null,
      selectedStatus: null,
      dateRange: [],
      dateMenu: false,
      newTransaction: {
        description: '',
        amount: '',
        type: '',
        category: '',
        date: '',
        account: ''
      },
      transactions: [],
      filteredTransactions: [],
      invoices: [],
      expenses: [],
      budgets: [],
      transactionTypes: ['Income', 'Expense', 'Transfer'],
      categories: [
        'Software', 'Office', 'Travel', 'Marketing', 'Salaries',
        'Rent', 'Utilities', 'Equipment', 'Supplies', 'Other'
      ],
      statusOptions: ['Pending', 'Completed', 'Failed', 'Cancelled'],
      accounts: [
        'Checking Account', 'Savings Account', 'Credit Card',
        'Business Account', 'PayPal', 'Stripe'
      ],
      availableReports: [
        {
          id: 1,
          title: 'Profit & Loss',
          description: 'Comprehensive profit and loss statement',
          icon: 'mdi-chart-line',
          color: 'primary'
        },
        {
          id: 2,
          title: 'Cash Flow',
          description: 'Detailed cash flow analysis',
          icon: 'mdi-cash',
          color: 'success'
        },
        {
          id: 3,
          title: 'Balance Sheet',
          description: 'Complete balance sheet report',
          icon: 'mdi-bank',
          color: 'info'
        },
        {
          id: 4,
          title: 'Expense Report',
          description: 'Detailed expense breakdown',
          icon: 'mdi-receipt',
          color: 'warning'
        }
      ],
      transactionHeaders: [
        { text: 'Date', value: 'date' },
        { text: 'Description', value: 'description' },
        { text: 'Category', value: 'category' },
        { text: 'Account', value: 'account' },
        { text: 'Amount', value: 'amount' },
        { text: 'Status', value: 'status' },
        { text: 'Actions', value: 'actions', sortable: false }
      ],
      expenseHeaders: [
        { text: 'Date', value: 'date' },
        { text: 'Description', value: 'description' },
        { text: 'Category', value: 'category' },
        { text: 'Amount', value: 'amount' },
        { text: 'Vendor', value: 'vendor' },
        { text: 'Receipt', value: 'receipt' }
      ],
      budgetHeaders: [
        { text: 'Category', value: 'category' },
        { text: 'Budgeted', value: 'budgeted' },
        { text: 'Spent', value: 'spent' },
        { text: 'Remaining', value: 'remaining' },
        { text: 'Percentage', value: 'percentage' }
      ]
    }
  },
  computed: {
    dateRangeText() {
      if (this.dateRange.length === 2) {
        const [start, end] = this.dateRange
        return `${start} - ${end}`
      }
      return ''
    },
    budgetOverview() {
      return this.budgets.map(budget => ({
        id: budget.id,
        title: budget.category,
        amount: budget.budgeted,
        budgeted: budget.budgeted,
        spent: budget.spent,
        percentage: Math.round((budget.spent / budget.budgeted) * 100)
      }))
    }
  },
  async mounted() {
    await this.loadFinanceData()
  },
  methods: {
    async loadFinanceData() {
      this.loading = true
      try {
        // Load all finance data
        const [transactionsRes, invoicesRes, expensesRes, budgetsRes] = await Promise.all([
          financeApi.getTransactions(),
          financeApi.getInvoices(),
          financeApi.getExpenses(),
          financeApi.getBudgets()
        ])

        this.transactions = transactionsRes.data.transactions || []
        this.filteredTransactions = this.transactions
        this.invoices = invoicesRes.data.invoices || []
        this.expenses = expensesRes.data.expenses || []
        this.budgets = budgetsRes.data.budgets || []

      } catch (error) {
        console.error('Error loading finance data:', error)
        this.$toast.error('Failed to load finance data')
      } finally {
        this.loading = false
      }
    },

    filterTransactions() {
      this.filteredTransactions = this.transactions.filter(transaction => {
        const matchesSearch = !this.transactionSearch || 
          transaction.description.toLowerCase().includes(this.transactionSearch.toLowerCase())
        
        const matchesCategory = !this.selectedCategory || 
          transaction.category === this.selectedCategory
        
        const matchesStatus = !this.selectedStatus || 
          transaction.status === this.selectedStatus
        
        return matchesSearch && matchesCategory && matchesStatus
      })
    },

    async saveTransaction() {
      try {
        await financeApi.createTransaction(this.newTransaction)
        this.$toast.success('Transaction saved successfully')
        this.showAddTransaction = false
        this.resetTransactionForm()
        await this.loadFinanceData()
      } catch (error) {
        console.error('Error saving transaction:', error)
        this.$toast.error('Failed to save transaction')
      }
    },

    resetTransactionForm() {
      this.newTransaction = {
        description: '',
        amount: '',
        type: '',
        category: '',
        date: '',
        account: ''
      }
      if (this.$refs.transactionForm) {
        this.$refs.transactionForm.resetValidation()
      }
    },

    editTransaction(transaction) {
      // Edit transaction logic
      console.log('Edit transaction:', transaction)
    },

    deleteTransaction(transaction) {
      // Delete transaction logic
      console.log('Delete transaction:', transaction)
    },

    viewInvoice(invoice) {
      // View invoice logic
      console.log('View invoice:', invoice)
    },

    scanReceipt() {
      // Receipt scanning logic
      console.log('Scan receipt')
    },

    viewReceipt(receipt) {
      // View receipt logic
      console.log('View receipt:', receipt)
    },

    generateReport(report) {
      // Generate report logic
      console.log('Generate report:', report)
    },

    async exportData() {
      this.exporting = true
      try {
        const response = await financeApi.exportData({
          format: 'csv',
          type: 'all'
        })
        
        // Download file
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', 'finance_data.csv')
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)

        this.$toast.success('Data exported successfully')
      } catch (error) {
        console.error('Error exporting data:', error)
        this.$toast.error('Failed to export data')
      } finally {
        this.exporting = false
      }
    },

    formatCurrency,
    formatDate,

    getAmountClass(amount) {
      return amount > 0 ? 'positive' : 'negative'
    },

    getCategoryColor(category) {
      const colors = {
        'Software': 'blue',
        'Food': 'green',
        'Travel': 'orange',
        'Office': 'purple',
        'Marketing': 'pink',
        'Salaries': 'indigo'
      }
      return colors[category] || 'grey'
    },

    getStatusColor(status) {
      const colors = {
        'completed': 'success',
        'pending': 'warning',
        'failed': 'error',
        'cancelled': 'grey'
      }
      return colors[status] || 'grey'
    },

    getInvoiceStatusColor(status) {
      const colors = {
        'paid': 'success',
        'pending': 'warning',
        'overdue': 'error',
        'draft': 'grey'
      }
      return colors[status] || 'grey'
    },

    getProgressColor(percentage) {
      if (percentage > 90) return 'error'
      if (percentage > 75) return 'warning'
      return 'success'
    },

    getPercentageClass(percentage) {
      if (percentage > 90) return 'negative'
      if (percentage > 75) return 'warning'
      return 'positive'
    }
  }
}
</script>

<style scoped>
.finance-management {
  padding: 24px;
  background: #f8f9fa;
  min-height: 100vh;
}

.management-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.management-header h1 {
  font-size: 32px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.transactions-section,
.invoices-section,
.expenses-section,
.budget-section,
.reports-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-top: 24px;
}

.section-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.filters {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.view-controls {
  display: flex;
  gap: 8px;
}

.transactions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.transaction-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.transaction-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.transaction-date {
  font-size: 12px;
  color: #6c757d;
}

.card-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.transaction-description {
  font-weight: 500;
  color: #2c3e50;
}

.transaction-amount {
  font-weight: 600;
  font-size: 16px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.transaction-account {
  font-size: 12px;
  color: #6c757d;
}

.invoices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.invoice-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.invoice-card:hover {
  transform: translateY(-2px);
}

.invoice-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.invoice-number {
  font-weight: 600;
  color: #2c3e50;
}

.invoice-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.customer-name {
  font-weight: 500;
  color: #2c3e50;
}

.customer-email {
  font-size: 12px;
  color: #6c757d;
}

.invoice-amount {
  font-weight: 600;
  font-size: 16px;
  color: #28a745;
}

.invoice-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.invoice-date {
  font-size: 12px;
  color: #6c757d;
}

.budget-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.overview-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.overview-title {
  font-weight: 500;
  color: #2c3e50;
  margin-bottom: 8px;
}

.overview-amount {
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 12px;
}

.overview-progress {
  margin-bottom: 8px;
}

.overview-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.percentage-cell {
  min-width: 120px;
}

.reports-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.report-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.report-card:hover {
  transform: translateY(-2px);
}

.report-icon {
  margin-bottom: 16px;
}

.report-title {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
}

.report-description {
  font-size: 14px;
  color: #6c757d;
  margin-bottom: 16px;
}

.positive {
  color: #28a745;
}

.negative {
  color: #dc3545;
}

.warning {
  color: #ffc107;
}

.action-buttons {
  display: flex;
  gap: 4px;
}

@media (max-width: 768px) {
  .management-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .filters {
    flex-direction: column;
    width: 100%;
  }

  .transactions-grid,
  .invoices-grid,
  .budget-overview,
  .reports-grid {
    grid-template-columns: 1fr;
  }
}
</style>
EOF

echo "✅ Finance management component created"

echo ""
echo "✅ Enhanced finance UI components created"
"