import { EventEmitter } from 'events';
import { ContactRelationship, ContactMilestone, RelationshipEvent } from './types';
import { LanceDBStorage } from '../skills/lanceDbStorageSkills';

export class RelationshipTracker extends EventEmitter {
  private userId: string;
  private storage: LanceDBStorage;
  private relationships: Map<string, ContactRelationship> = new Map();
  private staleThresholdDays = 30; // Days before relationship is considered stale

  constructor(userId: string) {
    super();
    this.userId = userId;
    this.storage = new LanceDBStorage();
  }

  public async loadAll(): Promise<void> {
    try {
      const relationships = await this.storage.retrieve('relationships', { userId: this.userId });
      if (relationships) {
        this.relationships = new Map(Object.entries(relationships));
      }
    } catch (error) {
      console.warn('Failed to load relationships:', error);
    }
  }

  public async saveAll(): Promise<void> {
    await this.storage.store('relationships', {
      userId: this.userId,
      relationships: Object.fromEntries(this.relationships)
    });
  }

  public async addContact(contact: ContactRelationship): Promise<void> {
    this.relationships.set(contact.id, {
      ...contact,
      lastCommunicationAt: contact.lastCommunicationAt || new Date(2000, 0, 1),
      importantMilestones: contact.importantMilestones || []
    });

    await this.saveAll();
    this.emit('contact-added', contact);
  }

  public getContactInfo(contactId: string): ContactRelationship | null {
    return this.relationships.get(contactId) || null;
  }

  public async recordInteraction(
    contactId: string,
    type: string,
    sentiment: number = 0,
    channel?: string
  ): Promise<void> {
    const contact = this.relationships.get(contactId);
    if (!contact) return;

    // Update last communication
    contact.lastCommunicationAt = new Date();
    contact.responseRate = Math.min(contact.responseRate + 1, 100);

    // Add relationship event
    const event: RelationshipEvent = {
      type: sentiment >= 0 ? 'positive' : 'negative',
      date: new Date(),
      description: `Last interaction was a ${type} via ${channel || 'unknown'}`,
      channel: channel as any,
      sentiment
    };

    contact.relationshipHistory = [...contact.relationshipHistory.slice(-50), event];

    // Recalculate closeness score
    contact.closenessScore = this.calculateClosenessScore(contact);

    await this.saveAll();
    this.emit('interaction-recorded', { contactId, type, sentiment });
  }

  public async getActiveRelationships(): Promise<ContactRelationship[]> {
    return Array.from(this.relationships.values())
      .filter(r => new Date(r.lastCommunicationAt).getTime() > Date.now() - (90 * 24 * 60 * 60 * 1000)) // Active in last 90 days
      .sort((a, b) => b.closenessScore - a.closenessScore);
  }

  public async getUpcomingMilestones(): Promise<ContactMilestone[]> {
    const allMilestones: ContactMilestone[] = [];

    for (const [id, contact] of this.relationships) {
      if (contact.importantMilestones) {
        const contactMilestones = contact.importantMilestones.map(m => ({
          ...m,
          contactId: id,
          contactName: contact.name,
          date: this.ensureDate(m.date)
        }));
        allMilestones.push(...contactMilestones);
      }
    }

    return allMilestones
      .filter(m => !m.acknowledged)
      .sort((a, b) => a.date.getTime() - b.date.getTime());
  }

  public async markMilestoneAcknowledged(milestone: ContactMilestone): Promise<void> {
    for (const [id, contact] of this.relationships) {
      const milestoneIndex = contact.importantMilestones.findIndex(
        m => m.date.getTime() === milestone.date.getTime() && m.type === milestone.type
      );

      if (milestoneIndex !== -1) {
        contact.importantMilestones[milestoneIndex].acknowledged = true;
        contact.importantMilestones[milestoneIndex].lastAcknowledged = new Date();
        break;
      }
    }

    await this.saveAll();
  }

  public getContactsNeedingMaintenance(): string[] {
    const staleCutoff = new Date(Date.now() - (this.staleThresholdDays * 24 * 60 * 60 * 1000));

    return Array.from(this.relationships.entries())
      .filter(([_, contact]) => new Date(contact.last
