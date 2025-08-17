import { AutonomousCommunicationOrchestrator } from './autonomousCommunicationOrchestrator';
import { CommunicationAnalyzer } from './communicationAnalyzer';
import { CommunicationScheduler } from './communicationScheduler';
import { PlatformRouter } from './platformRouter';
import { CommunicationMemory } from './communicationMemory';
import { RelationshipTracker } from './relationshipTracker';
import { CommunicationTypes, CommunicationContext, ScheduledCommunication, AutonomousCommunications } from './types';

export {
  AutonomousCommunicationOrchestrator,
  CommunicationAnalyzer,
  CommunicationScheduler,
  PlatformRouter,
  CommunicationMemory,
  RelationshipTracker
};

export type {
  CommunicationTypes,
  CommunicationContext,
  ScheduledCommunication,
  AutonomousCommunications
};

// Quick-start function
export async function createAutonomousCommunicationSystem(userId: string) {
  const system = new AutonomousCommunicationOrchestrator(userId);
  return system;
}

// Example usage:
// const commSystem = await createAutonomousCommunicationSystem('user123');
// await commSystem.start();
