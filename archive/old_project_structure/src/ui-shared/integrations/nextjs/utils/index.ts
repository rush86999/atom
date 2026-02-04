/**
 * Next.js Integration Utilities
 * Helper functions for Next.js/Vercel integration
 */

import { NextjsProject, NextjsBuild, NextjsDeployment, NextjsAnalytics } from '../types';

export class NextjsUtils {
  /**
   * Format build duration in human-readable format
   */
  static formatBuildDuration(duration?: number): string {
    if (!duration) return 'N/A';
    
    const seconds = Math.round(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${seconds}s`;
  }

  /**
   * Format file size for build artifacts
   */
  static formatFileSize(bytes?: number): string {
    if (!bytes) return 'N/A';
    
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(2)} ${units[unitIndex]}`;
  }

  /**
   * Get status color for build/deployment status
   */
  static getStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'ready':
      case 'success':
      case 'active':
        return 'green';
      case 'building':
      case 'pending':
      case 'in_progress':
        return 'blue';
      case 'error':
      case 'failed':
      case 'canceled':
        return 'red';
      case 'warning':
        return 'yellow';
      case 'archived':
      case 'suspended':
        return 'gray';
      default:
        return 'gray';
    }
  }

  /**
   * Get project framework icon
   */
  static getFrameworkIcon(framework: string): string {
    switch (framework?.toLowerCase()) {
      case 'nextjs':
        return '⚡';
      case 'react':
        return '⚛️';
      case 'vue':
        return '💚';
      case 'angular':
        return '🔺';
      case 'svelte':
        return '🔥';
      case 'nuxt':
        return '🥚';
      case 'typescript':
        return '🔷';
      default:
        return '📦';
    }
  }

  /**
   * Filter projects by search term
   */
  static filterProjects(projects: NextjsProject[], searchTerm: string): NextjsProject[] {
    if (!searchTerm) return projects;
    
    const lowercaseTerm = searchTerm.toLowerCase();
    return projects.filter(project => 
      project.name.toLowerCase().includes(lowercaseTerm) ||
      project.description?.toLowerCase().includes(lowercaseTerm) ||
      project.domains.some(domain => domain.toLowerCase().includes(lowercaseTerm)) ||
      project.framework.toLowerCase().includes(lowercaseTerm)
    );
  }

  /**
   * Sort projects by various criteria
   */
  static sortProjects(projects: NextjsProject[], sortBy: string, order: 'asc' | 'desc' = 'desc'): NextjsProject[] {
    return [...projects].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'createdAt':
        case 'updatedAt':
          comparison = new Date(a[sortBy as keyof NextjsProject] as string).getTime() - 
                     new Date(b[sortBy as keyof NextjsProject] as string).getTime();
          break;
        case 'status':
          comparison = a.status.localeCompare(b.status);
          break;
        case 'framework':
          comparison = a.framework.localeCompare(b.framework);
          break;
        default:
          comparison = 0;
      }
      
      return order === 'desc' ? -comparison : comparison;
    });
  }

  /**
   * Calculate build success rate
   */
  static calculateBuildSuccessRate(builds: NextjsBuild[]): number {
    if (!builds.length) return 0;
    
    const successfulBuilds = builds.filter(build => build.status === 'ready').length;
    return Math.round((successfulBuilds / builds.length) * 100);
  }

  /**
   * Get most recent build
   */
  static getMostRecentBuild(builds: NextjsBuild[]): NextjsBuild | null {
    if (!builds.length) return null;
    
    return builds.reduce((mostRecent, build) => {
      const buildDate = new Date(build.createdAt);
      const mostRecentDate = new Date(mostRecent.createdAt);
      return buildDate > mostRecentDate ? build : mostRecent;
    });
  }

  /**
   * Get deployment health status
   */
  static getDeploymentHealth(deployments: NextjsDeployment[]): 'healthy' | 'warning' | 'critical' {
    if (!deployments.length) return 'warning';
    
    const recentDeployments = deployments.filter(
      deployment => new Date(deployment.createdAt) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
    );
    
    const failedDeployments = recentDeployments.filter(
      deployment => deployment.status === 'error'
    ).length;
    
    const failureRate = recentDeployments.length > 0 ? (failedDeployments / recentDeployments.length) : 0;
    
    if (failureRate > 0.3) return 'critical';
    if (failureRate > 0.1) return 'warning';
    return 'healthy';
  }

  /**
   * Generate project summary for AI
   */
  static generateProjectSummary(project: NextjsProject, builds?: NextjsBuild[], deployments?: NextjsDeployment[]): string {
    const summary = [
      `Project: ${project.name}`,
      `Framework: ${project.framework}`,
      `Runtime: ${project.runtime}`,
      `Status: ${project.status}`
    ];

    if (project.description) {
      summary.push(`Description: ${project.description}`);
    }

    if (project.domains.length > 0) {
      summary.push(`Domains: ${project.domains.join(', ')}`);
    }

    if (builds && builds.length > 0) {
      const successRate = this.calculateBuildSuccessRate(builds);
      const mostRecent = this.getMostRecentBuild(builds);
      summary.push(`Build Success Rate: ${successRate}%`);
      summary.push(`Recent Build: ${mostRecent?.status || 'None'} (${mostRecent ? new Date(mostRecent.createdAt).toLocaleDateString() : 'N/A'})`);
    }

    if (deployments && deployments.length > 0) {
      const health = this.getDeploymentHealth(deployments);
      summary.push(`Deployment Health: ${health}`);
    }

    return summary.join('\n');
  }

  /**
   * Parse Vercel log entry
   */
  static parseLogEntry(log: string): {
    timestamp: string;
    level: string;
    message: string;
  } | null {
    try {
      // Example Vercel log format: [2023-10-15T10:30:00.000Z] INFO: Build started
      const match = log.match(/^\[([^\]]+)\]\s*(\w+):\s*(.+)$/);
      
      if (!match) return null;
      
      return {
        timestamp: match[1],
        level: match[2],
        message: match[3]
      };
    } catch {
      return null;
    }
  }

  /**
   * Estimate build time based on historical data
   */
  static estimateBuildTime(builds: NextjsBuild[]): number {
    if (!builds.length) return 0;
    
    const recentBuilds = builds
      .filter(build => build.status === 'ready' && build.duration)
      .slice(-10); // Last 10 successful builds
    
    if (!recentBuilds.length) return 0;
    
    const averageTime = recentBuilds.reduce((sum, build) => sum + (build.duration || 0), 0) / recentBuilds.length;
    return Math.round(averageTime);
  }

  /**
   * Get performance grade from metrics
   */
  static getPerformanceGrade(metrics: NextjsAnalytics['metrics']): 'A' | 'B' | 'C' | 'D' | 'F' {
    let score = 100;
    
    // Deduct points for poor performance
    if (metrics.avgLoadTime > 3000) score -= 30;
    else if (metrics.avgLoadTime > 2000) score -= 20;
    else if (metrics.avgLoadTime > 1000) score -= 10;
    
    if (metrics.bounceRate > 0.7) score -= 20;
    else if (metrics.bounceRate > 0.5) score -= 10;
    
    if (metrics.largestContentfulPaint > 4000) score -= 30;
    else if (metrics.largestContentfulPaint > 2500) score -= 20;
    else if (metrics.largestContentfulPaint > 1500) score -= 10;
    
    if (metrics.cumulativeLayoutShift > 0.3) score -= 20;
    else if (metrics.cumulativeLayoutShift > 0.2) score -= 10;
    else if (metrics.cumulativeLayoutShift > 0.1) score -= 5;
    
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    if (score >= 70) return 'C';
    if (score >= 60) return 'D';
    return 'F';
  }

  /**
   * Format date for display
   */
  static formatDate(date: string | Date): string {
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Get relative time (e.g., "2 hours ago")
   */
  static getRelativeTime(date: string | Date): string {
    const now = new Date();
    const target = new Date(date);
    const diffMs = now.getTime() - target.getTime();
    
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSeconds < 60) return `${diffSeconds} seconds ago`;
    if (diffMinutes < 60) return `${diffMinutes} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays < 30) return `${diffDays} days ago`;
    
    return this.formatDate(date);
  }

  /**
   * Validate webhook event
   */
  static validateWebhookEvent(event: any, secret: string): boolean {
    // Implement Vercel webhook signature validation
    // Vercel uses a signature header that can be verified with the webhook secret
    try {
      const signature = event.headers['x-vercel-signature'];
      if (!signature) return false;
      
      // In a real implementation, you would:
      // 1. Extract the signature from the header
      // 2. Compute HMAC using the webhook secret
      // 3. Compare with the received signature
      
      return true; // Placeholder for actual implementation
    } catch {
      return false;
    }
  }

  /**
   * Extract error message from build logs
   */
  static extractErrorMessage(logs: string[]): string | null {
    if (!logs.length) return null;
    
    // Look for common error patterns
    const errorPatterns = [
      /error[:\s]*(.+)/i,
      /failed[:\s]*(.+)/i,
      /build error[:\s]*(.+)/i,
      /compilation error[:\s]*(.+)/i,
      /exception[:\s]*(.+)/i
    ];
    
    for (const log of logs.reverse()) { // Check from the end
      for (const pattern of errorPatterns) {
        const match = log.match(pattern);
        if (match && match[1]) {
          return match[1].trim();
        }
      }
    }
    
    return null;
  }

  /**
   * Generate deployment URL
   */
  static generateDeploymentUrl(deployment: NextjsDeployment): string {
    return deployment.url || `https://${deployment.id}.vercel.app`;
  }

  /**
   * Check if project uses specific features
   */
  static checkProjectFeatures(project: NextjsProject): string[] {
    const features: string[] = [];
    
    if (project.runtime === 'edge') {
      features.push('Edge Runtime');
    }
    
    if (project.deployment?.platform === 'vercel') {
      features.push('Vercel Platform');
    }
    
    if (project.framework === 'nextjs') {
      features.push('Next.js Framework');
    }
    
    if (project.domains.length > 1) {
      features.push('Multiple Domains');
    }
    
    if (project.metrics?.errors === 0) {
      features.push('Error-Free');
    }
    
    return features;
  }
}