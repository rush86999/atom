/**
 * Enhanced Analytics API
 * Comprehensive analytics and monitoring for ATOM
 */

import { NextApiRequest, NextApiResponse } from 'next';
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

interface AnalyticsData {
  timestamp: string;
  metrics: {
    users: {
      total: number;
      active: number;
      new: number;
    };
    integrations: {
      total: number;
      connected: number;
      usage: Array<{
        service: string;
        count: number;
        lastUsed: string;
      }>;
    };
    performance: {
      averageResponseTime: number;
      throughput: number;
      errorRate: number;
      uptime: number;
    };
    features: {
      searchQueries: number;
      workflowExecutions: number;
      agentTasks: number;
      aiInteractions: number;
    };
  };
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { timeRange = '24h', service } = req.query;
    
    const analyticsData = await generateAnalytics(timeRange as string, service as string);
    
    return res.status(200).json({
      success: true,
      data: analyticsData,
      timeRange,
      generatedAt: new Date().toISOString(),
    });
    
  } catch (error) {
    console.error('Analytics API error:', error);
    return res.status(500).json({
      success: false,
      error: 'Failed to generate analytics',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}

async function generateAnalytics(timeRange: string, service?: string): Promise<AnalyticsData> {
  const now = Date.now();
  const timeRanges = {
    '1h': now - 60 * 60 * 1000,
    '24h': now - 24 * 60 * 60 * 1000,
    '7d': now - 7 * 24 * 60 * 60 * 1000,
    '30d': now - 30 * 24 * 60 * 60 * 1000,
  };
  
  const startTime = timeRanges[timeRange as keyof typeof timeRanges] || timeRanges['24h'];
  
  // User metrics
  const userMetrics = await getUserMetrics(startTime);
  
  // Integration metrics
  const integrationMetrics = await getIntegrationMetrics(startTime, service);
  
  // Performance metrics
  const performanceMetrics = await getPerformanceMetrics(startTime);
  
  // Feature usage metrics
  const featureMetrics = await getFeatureMetrics(startTime);
  
  return {
    timestamp: new Date().toISOString(),
    metrics: {
      users: userMetrics,
      integrations: integrationMetrics,
      performance: performanceMetrics,
      features: featureMetrics,
    },
  };
}

async function getUserMetrics(startTime: number) {
  try {
    const totalUsers = await redis.get('analytics:users:total') || '0';
    const activeUsers = await redis.zcount('analytics:users:active', startTime / 1000, '+inf');
    const newUsers = await redis.zcount('analytics:users:new', startTime / 1000, '+inf');
    
    return {
      total: parseInt(totalUsers, 10),
      active: activeUsers,
      new: newUsers,
    };
  } catch (error) {
    console.error('Failed to get user metrics:', error);
    return { total: 0, active: 0, new: 0 };
  }
}

async function getIntegrationMetrics(startTime: number, service?: string) {
  try {
    const connectedIntegrations = await redis.smembers('analytics:integrations:connected');
    const totalIntegrations = await redis.get('analytics:integrations:total') || '0';
    
    let usage: Array<{
      service: string;
      count: number;
      lastUsed: string;
    }> = [];
    
    if (service) {
      const count = await redis.get(`analytics:integrations:${service}:count`) || '0';
      const lastUsed = await redis.get(`analytics:integrations:${service}:lastUsed`) || '0';
      
      usage = [{
        service: service as string,
        count: parseInt(count, 10),
        lastUsed: new Date(parseInt(lastUsed, 10)).toISOString(),
      }];
    } else {
      // Get usage for all integrations
      const integrationServices = [
        'slack', 'github', 'gitlab', 'notion', 'jira', 'asana',
        'trello', 'hubspot', 'salesforce', 'stripe', 'quickbooks',
        'xero', 'zendesk', 'zoom', 'discord', 'teams', 'box',
        'gdrive', 'onedrive', 'azure', 'google-workspace',
        'outlook', 'gmail', 'mailchimp', 'freshdesk',
        'intercom', 'airtable', 'linear', 'tableau', 'shopify'
      ];
      
      for (const svc of integrationServices) {
        const count = await redis.get(`analytics:integrations:${svc}:count`) || '0';
        const lastUsed = await redis.get(`analytics:integrations:${svc}:lastUsed`) || '0';
        
        if (parseInt(count, 10) > 0) {
          usage.push({
            service: svc,
            count: parseInt(count, 10),
            lastUsed: new Date(parseInt(lastUsed, 10)).toISOString(),
          });
        }
      }
    }
    
    return {
      total: parseInt(totalIntegrations, 10),
      connected: connectedIntegrations.length,
      usage: usage.sort((a, b) => b.count - a.count).slice(0, 10), // Top 10
    };
  } catch (error) {
    console.error('Failed to get integration metrics:', error);
    return { total: 0, connected: 0, usage: [] };
  }
}

async function getPerformanceMetrics(startTime: number) {
  try {
    const avgResponseTime = await redis.get('analytics:performance:avgResponse') || '0';
    const throughput = await redis.get('analytics:performance:throughput') || '0';
    const errorCount = await redis.get('analytics:performance:errors') || '0';
    const totalRequests = await redis.get('analytics:performance:requests') || '0';
    
    const uptime = process.uptime() * 1000; // Convert to milliseconds
    const errorRate = totalRequests > '0' ? 
      (parseInt(errorCount, 10) / parseInt(totalRequests, 10)) * 100 : 0;
    
    return {
      averageResponseTime: parseFloat(avgResponseTime),
      throughput: parseInt(throughput, 10),
      errorRate,
      uptime,
    };
  } catch (error) {
    console.error('Failed to get performance metrics:', error);
    return { averageResponseTime: 0, throughput: 0, errorRate: 0, uptime: 0 };
  }
}

async function getFeatureMetrics(startTime: number) {
  try {
    const searchQueries = await redis.zcount('analytics:features:search', startTime / 1000, '+inf');
    const workflowExecutions = await redis.zcount('analytics:features:workflows', startTime / 1000, '+inf');
    const agentTasks = await redis.zcount('analytics:features:agents', startTime / 1000, '+inf');
    const aiInteractions = await redis.zcount('analytics:features:ai', startTime / 1000, '+inf');
    
    return {
      searchQueries,
      workflowExecutions,
      agentTasks,
      aiInteractions,
    };
  } catch (error) {
    console.error('Failed to get feature metrics:', error);
    return { searchQueries: 0, workflowExecutions: 0, agentTasks: 0, aiInteractions: 0 };
  }
}