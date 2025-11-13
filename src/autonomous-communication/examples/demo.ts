import { AutonomousCommunicationOrchestrator, RelationshipTracker } from '..';
import { ContactRelationship, CommunicationType } from '../types';

async function demonstrateAutonomousCommunication() {
  console.log('🚀 Testing Autonomous Communication System...');

  const userId = 'demo-user-123';
  const orchestrator = new AutonomousCommunicationOrchestrator(userId);

  try {
    // Step 1: Initialize the system
    console.log('📡 Initializing system...');

    // Step 2: Add some demo relationships
    console.log('📝 Adding demo relationships...');
    const relationshipTracker = new RelationshipTracker(userId);

    const demoContacts: ContactRelationship[] = [
      {
        id: 'contact-1',
        name: 'Sarah Chen',
        email: 'sarah.chen@techcorp.com',
        relationshipType: 'client',
        closenessScore: 85,
        lastCommunicationAt: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000), // 25 days ago
        preferredChannel: 'email',
        timezone: 'America/Los_Angeles',
        lastInteractionType: 'follow-up',
        responseRate: 75,
        averageResponseTime: 12,
        topicsOfInterest: ['AI', 'Product Management', 'Scaling'],
        importantMilestones: [
          {
            type: 'work-anniversary',
            date: new Date('2024-12-15'),
            description: 'Work anniversary at TechCorp',
            importance: 0.9,
            acknowledged: false
          }
        ],
        relationshipHistory: [],
        mutualConnections: []
      },
      {
        id: 'contact-2',
        name: 'Marcus Johnson',
        email: 'marcus.j@gmail.com',
        relationshipType: 'colleague',
        closenessScore: 70,
        lastCommunicationAt: new Date(Date.now() - 40 * 24 * 60 * 60 * 1000), // 40 days ago
        preferredChannel: 'linkedin',
        timezone: 'America/New_York',
        lastInteractionType: 'content-sharing',
        responseRate: 60,
        averageResponseTime: 24,
        topicsOfInterest: ['Open Source', 'Community Building'],
        importantMilestones: [],
        relationshipHistory: [],
        mutualConnections: []
      }
    ];

    // Load relationships
    await relationshipTracker.loadAll();

    // Add demo contacts
    for (const contact of demoContacts) {
      await relationshipTracker.addContact(contact);
    }

    // Step 3: Set up basic preferences
    console.log('⚙️ Setting up preferences...');
    await orchestrator.loadHistoricalContext();

    // Step 4: Schedule some demo communications
    console.log('📅 Scheduling demo communications...');

    // Example of Proactive Relationship Maintenance
    await orchestrator.sendImmediateCommunication({
      type: 'relationship-maintenance',
      priority: 'medium',
      recipient: 'contact-1',
      channel: 'email',
      context: { contact: demoContacts[0] },
      scheduledTime: new Date(Date.now() + 1000), // 1 second exec
      reasoning: 'Sarah hasn\'t been contacted for 25 days. Following up to maintain client relationship and discuss project scaling.',
      message: 'Hi Sarah! I noticed it\'s been a while since we connected. I\'d love to catch up about TechCorp\'s upcoming scaling initiatives and see how our AI solutions might help with your Q4 roadmap.'
    });

    // Example of Milestone Celebration
    await orchestrator.sendImmediateCommunication({
      type: 'celebration',
      priority: 'high',
      recipient: 'contact-1',
      channel: 'email',
      context: { milestone: demoContacts[0].importantMilestones[0] },
      scheduledTime: new Date(Date.now() + 5000), // 5 seconds later
      reasoning: 'Sarah\'s work anniversary is in 3 days. Sending early congratulations and proposing celebratory meeting.',
      message: 'Sarah! 🎉 I just realized your TechCorp work anniversary is coming up. Congratulations on another amazing year! How about we catch up over coffee next week to celebrate your achievements?'
    });

    // Example of Content Sharing
    await orchestrator.sendImmediateCommunication({
      type: 'content-sharing',
      priority: 'low',
      recipient: 'contact-2',
      channel: 'linkedin',
      context: { topics: demoContacts[1].topicsOfInterest },
      scheduledTime: new Date(Date.now() + 10000), // 10 seconds later
      reasoning: 'Marcus is interested in open source and community building. Sending relevant article about open source scaling strategies.',
      message: 'Hey Marcus! Your work on community building reminded me of this great article on scaling open source projects. Thought you might find it interesting. Let\'s catch up soon!'
    });

    // Step 5: Start the autonomous system
    console.log('🚀 Starting autonomous communication system...');
    await orchestrator.start();

    // Step 6: Run demo for 15 seconds to allow scheduled communications to execute
    console.log('⏳ Running demo for 15 seconds...');
    await new Promise(resolve => setTimeout(resolve, 15000));

    // Step 7: Stop the system
    console.log('🛑 Stopping autonomous communication system...');
    await orchestrator.stop();

    console.log('✅ Demo completed successfully!');

  } catch (error) {
    console.error('❌ Error during demo:', error);
  }
}

// Run the demo
demonstrateAutonomousCommunication().catch(console.error);
