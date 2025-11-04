import { EventEmitter } from 'events';
import { CommunicationRecord, CommunicationContext } from './types';

export interface ToneAnalysis {
  sentiment: number; // -1 to 1
  emotionalTone: 'positive' | 'neutral' | 'negative' | 'stressed' | 'excited' | 'calm';
  urgency: 'low' | 'medium' | 'high';
  formality: 'formal' | 'casual' | 'friendly' | 'professional';
  keywords: string[];
  suggestedTone: 'formal' | 'casual' | 'friendly' | 'professional';
}

export class ToneAnalyzer extends EventEmitter {
  public async analyzeTone(record: CommunicationRecord): Promise<ToneAnalysis> {
    // Simple sentiment analysis based on keywords
    const positiveWords = ['great', 'thanks', 'appreciate', 'excellent', 'wonderful', 'happy'];
    const negativeWords = ['urgent', 'problem', 'issue', 'concern', 'disappointed', 'sorry'];
    
    const message = record.message.toLowerCase();
    const positiveCount = positiveWords.filter(w => message.includes(w)).length;
    const negativeCount = negativeWords.filter(w => message.includes(w)).length;
    
    const sentiment = (positiveCount - negativeCount) / Math.max(positiveCount + negativeCount, 1);
    
    let emotionalTone: ToneAnalysis['emotionalTone'] = 'neutral';
    if (sentiment > 0.3) emotionalTone = 'positive';
    else if (sentiment > 0.1) emotionalTone = 'excited';
    else if (sentiment < -0.3) emotionalTone = 'negative';
    else if (sentiment < -0.1) emotionalTone = 'stressed';
    else emotionalTone = 'calm';
    
    const urgency: 'low' | 'medium' | 'high' = 
      record.priority === 'urgent' ? 'high' :
      record.priority === 'high' ? 'medium' : 'low';
    
    const formality = record.channel === 'email' ? 'professional' : 'casual';
    
    return {
      sentiment,
      emotionalTone,
      urgency,
      formality,
      keywords: this.extractKeywords(message),
      suggestedTone: formality
    };
  }

  public async analyzeContext(context: CommunicationContext): Promise<ToneAnalysis> {
    if (context.recentCommunications.length === 0) {
      return {
        sentiment: 0,
        emotionalTone: 'neutral',
        urgency: 'low',
        formality: 'professional',
        keywords: [],
        suggestedTone: 'professional'
      };
    }

    const latest = context.recentCommunications[context.recentCommunications.length - 1];
    return await this.analyzeTone(latest);
  }

  private extractKeywords(text: string): string[] {
    const words = text.toLowerCase().split(/\s+/);
    const commonWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were']);
    return words.filter(w => w.length > 3 && !commonWords.has(w)).slice(0, 10);
  }
}
