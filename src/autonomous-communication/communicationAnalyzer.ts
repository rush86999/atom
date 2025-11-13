import { CommunicationContext, CommunicationRecord } from './types';

interface CommunicationInsights {
  relationshipHealth: Record<string, number>;
  engagementTrends: string[];
  risks: string[];
  opportunities: string[];
  recommendations: string[];
}

export class CommunicationAnalyzer {
  public async analyzeCommunicationPatterns(context: CommunicationContext): Promise<{
    patterns: any;
    insights: CommunicationInsights;
    recommendations: string[];
    anomalies: any[];
  }> {
    const records = context.recentCommunications;

    if (records.length === 0) {
      return {
        patterns: {},
        insights: this.getEmptyInsights(),
        recommendations: [],
        anomalies: []
      };
    }

    const patterns = this.extractPatterns(records);
    const insights = this.generateInsights(records, patterns);
    const recommendations = this.generateRecommendations(context, insights);
    const anomalies = this.detectAnomalies(records, patterns);

    return {
      patterns,
      insights,
      recommendations,
      anomalies
    };
  }

  private extractPatterns(records: CommunicationRecord[]): any {
    return {
      timing: this.analyzeTiming(records),
      sentiment: this.analyzeSentiment(records),
      channel: this.analyzeChannelUsage(records),
      response: this.analyzeResponsePatterns(records),
      relationship: this.analyzeRelationships(records)
    };
  }

  private analyzeTiming(records: CommunicationRecord[]): {
    peakHours: number[];
    weekdayDistribution: number[];
    responseTimeEvolution: number[];
    cadenceByRelationship: Record<string, number>;
  } {
    const hours = Array(24).fill(0);
    const weekdays = Array(7).fill(0);
    const responseTimesByRelationship: Record<string, number[]> = {};

    for (const record of records) {
      const hour = record.timestamp.getHours();
      const weekday = record.timestamp.getDay();

      hours[hour]++;
      weekdays[weekday]++;

      if (record.recipientId && record.performance.replyTime !== undefined) {
        if (!responseTimesByRelationship[record.recipientId]) {
          responseTimesByRelationship[record.recipientId] = [];
        }
        responseTimesByRelationship[record.recipientId].push(record.performance.replyTime);
      }
    }

    const sortedRecords = records.sort((a: CommunicationRecord, b: CommunicationRecord) => a.timestamp.getTime() - b.timestamp.getTime());
    const responseTimeEvolution = sortedRecords.map((r: CommunicationRecord) => r.performance.replyTime || 0);

    return {
      peakHours: this.findPeakHours(hours),
      weekdayDistribution: weekdays,
      responseTimeEvolution,
      cadenceByRelationship: Object.fromEntries(
        Object.entries(responseTimesByRelationship).map(([key, times]) =>
          [key, times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0]
        )
      )
    };
  }

  private analyzeSentiment(records: CommunicationRecord[]): {
    overallTrend: number;
    sentimentByContact: Record<string, number>;
    emotionalHighlights: string[];
  } {
    const sentimentByContact: Record<string, number[]> = {};

    for (const record of records) {
      if (record.sentimentScore !== undefined) {
        const contact = record.recipientId || record.senderId;
        if (!sentimentByContact[contact]) {
          sentimentByContact[contact] = [];
        }
        sentimentByContact[contact].push(record.sentimentScore);
      }
    }

    const avgSentimentByContact = Object.fromEntries(
      Object.entries(sentimentByContact).map(([key, scores]) =>
        [key, scores.reduce((a, b) => a + b, 0) / scores.length]
      )
    );

    return {
      overallTrend: records.reduce((sum, r) => sum + (r.sentimentScore || 0), 0) / records.length,
      sentimentByContact: avgSentimentByContact,
      emotionalHighlights: this.extractEmotionalHighlights(records)
    };
  }

  private analyzeChannelUsage(records: CommunicationRecord[]): {
    distribution: Record<string, number>;
  } {
    const channelCount: Record<string, number> = {};

    for (const record of records) {
      const channel = record.channel;
      channelCount[channel] = (channelCount[channel] || 0) + 1;
    }

    const total = records.length;
    const distribution = Object.fromEntries(
      Object.entries(channelCount).map(([channel, count]) =>
        [channel, count / total]
      )
    );

    return { distribution };
  }

  private analyzeResponsePatterns(records: CommunicationRecord[]): {
    averageResponseTime: number;
    responseByChannel: Record<string, number>;
    noResponseRate: number;
    escalationRate: number;
  } {
    const responded = records.filter(r => r.responseReceived);
    const noResponded = records.length - responded.length;

    const responseByChannel: Record<string, number[]> = {};

    for (const record of records) {
      if (record.responseReceived && record.performance.replyTime !== undefined) {
        if (!responseByChannel[record.channel]) {
          responseByChannel[record.channel] = [];
        }
        responseByChannel[record.channel].push(record.performance.replyTime);
      }
    }

    const averageResponseTime = responded.length > 0
      ? responded.reduce((sum, r) => sum + (r.performance.replyTime || 0), 0) / responded.length
      : 0;

    const responseByChannelAvg = Object.fromEntries(
      Object.entries(responseByChannel).map(([channel, times]) =>
        [channel, times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0]
      )
    );

    const noResponseRate = records.length > 0 ? (noResponded / records.length) * 100 : 0;

    const escalated = records.filter(r => r.priority === 'urgent' || r.priority === 'high').length;
    const escalationRate = records.length > 0 ? (escalated / records.length) * 100 : 0;

    return {
      averageResponseTime,
      responseByChannel: responseByChannelAvg,
      noResponseRate,
      escalationRate
    };
  }

  private analyzeRelationships(records: CommunicationRecord[]): {
    communicationCountByRecipient: Record<string, number>;
    lastCommunicationByRecipient: Record<string, Date>;
  } {
    const countByRecipient: Record<string, number> = {};
    const lastCommByRecipient: Record<string, Date> = {};

    for (const record of records) {
      const recipient = record.recipientId;
      countByRecipient[recipient] = (countByRecipient[recipient] || 0) + 1;
      if (!lastCommByRecipient[recipient] || record.timestamp > lastCommByRecipient[recipient]) {
        lastCommByRecipient[recipient] = record.timestamp;
      }
    }

    return {
      communicationCountByRecipient: countByRecipient,
      lastCommunicationByRecipient: lastCommByRecipient
    };
  }

  private generateInsights(records: CommunicationRecord[], patterns: any): CommunicationInsights {
    const relationshipHealth: Record<string, number> = {};
    const engagementTrends: string[] = [];
    const risks: string[] = [];
    const opportunities: string[] = [];
    const recommendations: string[] = [];

    // Calculate relationship health based on sentiment and response rates
    for (const [contact, sentiment] of Object.entries(patterns.sentiment.sentimentByContact)) {
      const responseRate = patterns.response.responseByChannel[contact] || 0; // Assuming contact is channel, but adjust if needed
      relationshipHealth[contact] = (sentiment as number + (1 - responseRate / 100)) / 2 * 100; // Simple formula
    }

    // Engagement trends
    if (patterns.timing.responseTimeEvolution.length > 1) {
      const recent = patterns.timing.responseTimeEvolution.slice(-5);
      const avgRecent = recent.reduce((a: number, b: number) => a + b, 0) / recent.length;
      const earlier = patterns.timing.responseTimeEvolution.slice(0, -5);
      const avgEarlier = earlier.length > 0 ? earlier.reduce((a: number, b: number) => a + b, 0) / earlier.length : avgRecent;
      if (avgRecent < avgEarlier) {
        engagementTrends.push('Response times are improving');
      } else {
        engagementTrends.push('Response times are increasing');
      }
    }

    // Risks
    if (patterns.response.noResponseRate > 50) {
      risks.push('High no-response rate indicates potential communication issues');
    }
    if (patterns.sentiment.overallTrend < 0) {
      risks.push('Overall sentiment is negative');
    }

    // Opportunities
    if (patterns.response.noResponseRate < 20) {
      opportunities.push('Low no-response rate suggests strong engagement');
    }
    if (patterns.sentiment.overallTrend > 0.5) {
      opportunities.push('Positive sentiment indicates healthy relationships');
    }

    // Recommendations
    if (patterns.timing.peakHours.length > 0) {
      recommendations.push(`Schedule communications during peak hours: ${patterns.timing.peakHours.join(', ')}`);
    }
    if (patterns.response.averageResponseTime > 24) {
      recommendations.push('Consider improving response times to maintain engagement');
    }

    return {
      relationshipHealth,
      engagementTrends,
      risks,
      opportunities,
      recommendations
    };
  }

  private generateRecommendations(context: CommunicationContext, insights: CommunicationInsights): string[] {
    const recommendations: string[] = [...insights.recommendations];

    if (insights.risks.length > 0) {
      recommendations.push('Address identified risks to improve communication health');
    }
    if (insights.opportunities.length > 0) {
      recommendations.push('Leverage opportunities to strengthen relationships');
    }

    // Context-based recommendations
    if (context.userAvailability.busy) {
      recommendations.push('User is currently busy; delay non-urgent communications');
    }
    if (context.emotionalContext.currentMood === 'stressed') {
      recommendations.push('User mood is stressed; avoid high-pressure communications');
    }

    return recommendations;
  }

  private detectAnomalies(records: CommunicationRecord[], patterns: any): any[] {
    const anomalies: any[] = [];

    // Detect unusual response times
    const avgResponseTime = patterns.response.averageResponseTime;
    for (const record of records) {
      if (record.performance.replyTime && Math.abs(record.performance.replyTime - avgResponseTime) > avgResponseTime * 2) {
        anomalies.push({
          type: 'response_time_anomaly',
          recordId: record.id,
          description: `Unusual response time: ${record.performance.replyTime} hours`
        });
      }
    }

    // Detect sentiment anomalies
    const avgSentiment = patterns.sentiment.overallTrend;
    for (const record of records) {
      if (record.sentimentScore && Math.abs(record.sentimentScore - avgSentiment) > 1) {
        anomalies.push({
          type: 'sentiment_anomaly',
          recordId: record.id,
          description: `Extreme sentiment score: ${record.sentimentScore}`
        });
      }
    }

    return anomalies;
  }

  private getEmptyInsights(): CommunicationInsights {
    return {
      relationshipHealth: {},
      engagementTrends: [],
      risks: [],
      opportunities: [],
      recommendations: []
    };
  }

  private findPeakHours(hours: number[]): number[] {
    const maxCount = Math.max(...hours);
    return hours.map((count, hour) => count === maxCount ? hour : -1).filter(h => h !== -1);
  }

  private extractEmotionalHighlights(records: CommunicationRecord[]): string[] {
    const highlights: string[] = [];
    const sortedRecords = records.sort((a: CommunicationRecord, b: CommunicationRecord) => (b.sentimentScore || 0) - (a.sentimentScore || 0));
    const topPositive = sortedRecords.filter((r: CommunicationRecord) => (r.sentimentScore || 0) > 0.5).slice(0, 3);
    const topNegative = sortedRecords.filter((r: CommunicationRecord) => (r.sentimentScore || 0) < -0.5).slice(0, 3);

    for (const record of topPositive) {
      highlights.push(`Positive: ${record.message.substring(0, 50)}...`);
    }
    for (const record of topNegative) {
      highlights.push(`Negative: ${record.message.substring(0, 50)}...`);
    }

    return highlights;
  }
}
