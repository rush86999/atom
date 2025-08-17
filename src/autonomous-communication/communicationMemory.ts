import { EventEmitter } from 'events';
import { CommunicationRecord, CommunicationPreferences, AutonomousCommunications, LearningPoint } from './types';
import { LanceDBStorage } from '../skills/lanceDbStorageSkills';

export class CommunicationMemory extends EventEmitter {
  private userId: string;
  private storage: LanceDBStorage;
  private preferences: CommunicationPreferences;
  private learningHistory: LearningPoint[] = [];
  private recentCommunications: CommunicationRecord[] = [];

  constructor(userId: string) {
    super();
    this.userId = userId;
    this.storage = new LanceDBStorage();
    this.preferences = this.getDefaultPreferences();
  }

  private getDefaultPreferences(): CommunicationPreferences {
    return {
      preferredChannels: {},
      nonWorkingHours: { start: 18, end: 9 },
      responseTimeExpectations: {},
      autoResponseTriggers: ['urgent', 'follow-up'],
      doNotDisturbList: [],
      tonePreferences: {},
      messageLengthPreference: 'medium',
      emojiUsage: false
    };
  }

  public async loadAll(): Promise<void> {
    await this.loadPreferences();
    await this.loadCommunicationHistory();
    await this.loadLearningHistory();
  }

  private async loadPreferences(): Promise<void> {
    try {
      const savedPrefs = await this.storage.retrieve('communication_preferences', { userId: this.userId });
      if (savedPrefs) {
        this.preferences = { ...this.preferences, ...savedPrefs };
      }
    } catch (error) {
      console.warn('Could not load preferences:', error);
    }
  }

  private async loadCommunicationHistory(): Promise<void> {
    try {
      const history = await this.storage.retrieve('communication_history', { userId: this.userId });
      if (history && Array.isArray(history.records)) {
        this.recentCommunications = history.records.slice(-1000);
      }
    } catch (error) {
      console.warn('Could not load communication history:', error);
+    }
+  }
+
+  private async loadLearningHistory(): Promise<void> {
+    try {
+      const learningData = await this.storage.retrieve('learning_history', { userId: this.userId });
+      if (learningData && Array.isArray(learningData.points)) {
+        this.learningHistory = learningData.points.slice(-100);
+      }
+    } catch (error) {
+      console.warn('Could not load learning history:', error);
+    }
+  }
+
+  public async recordCommunication(communication: CommunicationRecord): Promise<void> {
+    this.recentCommunications.push(communication);
+
+    // Keep only last 1000 records in memory
+    if (this.recentCommunications.length > 1000) {
+      this.recentCommunications = this.recentCommunications.slice(-1000);
+    }
+
+    // Save to persistent storage
+    await this.storage.store('communication_history', {
+      userId: this.userId,
+      records: this.recentCommunications,
+      lastUpdated: new Date()
+    });
+
+    this.emit('new-communication', communication);
+  }
+
+  public async getRecentCommunications(hours: number = 24): Promise<CommunicationRecord[]> {
+    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000);
+    return this.recentCommunications.filter(c => c.timestamp > cutoff);
+  }
+
+  public async getLastCommunicationWith(contactId: string): Promise<CommunicationRecord | null> {
+    const contactComms = this.recentCommunications
+      .filter(c => c.recipientId === contactId || c.senderId === contactId)
+      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
+
+    return contactComms[0] || null;
+  }
+
+  public async getCommunicationPreferences(): Promise<CommunicationPreferences> {
+    return { ...this.preferences };
+  }
+
+  public async updatePreferences(newPreferences: Partial<CommunicationPreferences>): Promise<void> {
+    this.preferences = { ...this.preferences, ...newPreferences };
+
+    await this.storage.store('communication_preferences', {
+      userId: this.userId,
+      ...this.preferences,
+      lastUpdated: new Date()
+    });
+
+    this.emit('preferences-updated', this.preferences);
+  }
+
+  public async updatePreferencesFromContext(context: any): Promise<void> {
+    // Learn from actual behavior patterns
+    const recentComms = await this.getRecentCommunications(7 * 24); // 7 days
+
+    const channelUsage: Record<string, number> = {};
+    const responsePatterns: Record<string, any> = {};
+
+    for
