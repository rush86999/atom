"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  TrendingUp,
  Clock,
  DollarSign,
  Activity,
  Download,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertCircle
} from 'lucide-react'

interface WorkflowMetric {
  execution_count: number
  success_count: number
  failure_count: number
  total_duration_seconds: number
  total_time_saved_seconds: number
  total_business_value: number
  last_executed: string
  success_rate: number
  average_duration: number
}

interface IntegrationMetric {
  call_count: number
  error_count: number
  total_response_time_ms: number
  last_called: string
  status: string
  error_rate: number
  average_response_time: number
  uptime_percentage: number
}

interface DashboardData {
  workflows: {
    total_executions: number
    total_time_saved_hours: number
    total_business_value: number
    workflow_count: number
    workflows: Record<string, WorkflowMetric>
  }
  integrations: {
    total_integrations: number
    ready_count: number
    integrations: Record<string, IntegrationMetric>
  }
}

export default function AnalyticsPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = async () => {
    try {
      setRefreshing(true)
      const response = await fetch('http://localhost:8000/api/analytics/dashboard')
      const result = await response.json()
      setData(result)
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const exportCSV = async (type: 'workflow' | 'integration') => {
    try {
      const response = await fetch(`http://localhost:8000/api/analytics/export/csv?metric_type=${type}`)
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `atom_analytics_${type}_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to export CSV:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 mx-auto mb-4 text-destructive" />
          <p className="text-muted-foreground">Failed to load analytics data</p>
          <Button onClick={fetchData} className="mt-4">Retry</Button>
        </div>
      </div>
    )
  }

  const successRate = data.workflows.total_executions > 0
    ? ((Object.values(data.workflows.workflows).reduce((sum, w) => sum + w.success_count, 0) / data.workflows.total_executions) * 100).toFixed(1)
    : '0.0'

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
          <p className="text-muted-foreground">Monitor workflow performance and business value</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={fetchData}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            onClick={() => exportCSV('workflow')}
          >
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Executions</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.workflows.total_executions}</div>
            <p className="text-xs text-muted-foreground">
              {data.workflows.workflow_count} workflows tracked
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{successRate}%</div>
            <div className="w-full bg-secondary h-2 rounded-full mt-2">
              <div
                className="bg-primary h-2 rounded-full transition-all"
                style={{ width: `${successRate}%` }}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Time Saved</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.workflows.total_time_saved_hours}h</div>
            <p className="text-xs text-muted-foreground">
              Automation efficiency
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Business Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${data.workflows.total_business_value.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              Total value delivered
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Workflow Performance Table */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow Performance</CardTitle>
          <CardDescription>Detailed metrics for each workflow</CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(data.workflows.workflows).length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No workflow data yet. Execute workflows to see metrics.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Workflow</th>
                    <th className="text-right p-2">Executions</th>
                    <th className="text-right p-2">Success Rate</th>
                    <th className="text-right p-2">Avg Duration</th>
                    <th className="text-right p-2">Time Saved</th>
                    <th className="text-right p-2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.workflows.workflows).map(([id, metric]) => (
                    <tr key={id} className="border-b hover:bg-muted/50">
                      <td className="p-2 font-medium">{id}</td>
                      <td className="p-2 text-right">{metric.execution_count}</td>
                      <td className="p-2 text-right">
                        <Badge
                          variant={metric.success_rate >= 90 ? "default" : metric.success_rate >= 70 ? "secondary" : "destructive"}
                        >
                          {metric.success_rate.toFixed(1)}%
                        </Badge>
                      </td>
                      <td className="p-2 text-right">{metric.average_duration.toFixed(2)}s</td>
                      <td className="p-2 text-right">{(metric.total_time_saved_seconds / 3600).toFixed(2)}h</td>
                      <td className="p-2 text-right">${metric.total_business_value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Integration Health */}
      {data.integrations.total_integrations > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Integration Health</CardTitle>
            <CardDescription>
              {data.integrations.ready_count} of {data.integrations.total_integrations} integrations ready
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Integration</th>
                    <th className="text-center p-2">Status</th>
                    <th className="text-right p-2">Calls</th>
                    <th className="text-right p-2">Uptime</th>
                    <th className="text-right p-2">Avg Response</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.integrations.integrations).map(([name, metric]) => (
                    <tr key={name} className="border-b hover:bg-muted/50">
                      <td className="p-2 font-medium">{name}</td>
                      <td className="p-2 text-center">
                        <Badge
                          variant={
                            metric.status === 'READY' ? 'default' :
                              metric.status === 'PARTIAL' ? 'secondary' :
                                'destructive'
                          }
                        >
                          {metric.status === 'READY' && <CheckCircle2 className="h-3 w-3 mr-1 inline" />}
                          {metric.status === 'ERROR' && <XCircle className="h-3 w-3 mr-1 inline" />}
                          {metric.status}
                        </Badge>
                      </td>
                      <td className="p-2 text-right">{metric.call_count}</td>
                      <td className="p-2 text-right">{metric.uptime_percentage.toFixed(1)}%</td>
                      <td className="p-2 text-right">{metric.average_response_time.toFixed(0)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
