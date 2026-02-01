/**
 * Advanced Orchestration Skills Index
 * Registers orchestration capabilities with Atom's skill system
 */

import { registerSkill, SkillDefinition } from '../services/agentSkillRegistry';
import { OrchestrationSkill } from './orchestrationSkill';
import { ConversationalOrchestration } from '../orchestration/ConversationalOrchestration';

// Orchestration skill activation triggers for wake word and natural language
const orchestrationSkillConfig = {
  wakeWordTriggers: [
    'orchestrate',
    'automate',
    'set up',
    'workflow',
    'business process',
    'ai team',
    'multi-agent',
    'automated system'
  ],

  activationPatterns: [
    '^i want to automate .*',
    '^set up.*system for',
    '^create.*workflow for',
    '^need help with.*business',
    '^how[^.]*retire at',
    '^want to automate.*customer',
    '^spend.*hours on receipts',
    '^customer.*never.*come.*back',
    '^marketing.*inconsistent'
  ],

  naturalLanguagePatterns: [
    'I want to retire by [age]',
    'Customers stop buying after first purchase',
    'Spending too much time on [business task]',
    'Need to automate customer follow-up',
    'Help with receipt categorization',
    'Want to plan retirement while running business',
    'Inconsistent marketing affecting sales',
    'Looking for complete business automation',
    'Need better customer retention',
    'Want to save time on manual tasks'
  ],

  businessContextPatterns: {
    financial: ['retirement', 'invest', 'tax', 'money goal', 'savings', 'financial planning'],
    customer: ['retention', 'repeat sales', 'loyal customers', 'follow-up', 'customer automation'],
    marketing: ['social media', 'content creation', 'campaigns', 'inconsistent'],
    automation: ['automation', 'reduce work', 'save time', 'eliminate manual'],
    financial: ['receipts', 'taxes', 'expenses', 'deduction tracking']
+  }
 };

 /**
  * Register orchestration skills with Atom's skill system
  */
 export async function registerOrchestrationSkills() {
   console.log('🤖 Registering ATOM Advanced Orchestration Skills');

   try {
     const orchestrationSkill = new OrchestrationSkill();

     // Register the main orchestration skill
     await registerSkill(orchestrationSkill);

     console.log('✅ Orchestration skills registered successfully');

     return {
       success: true,
       registeredSkills: 1,
       wakeWordTriggers: orchestrationSkillConfig.wakeWordTriggers,
+      naturalLanguageSupport: true,
+      patternsRegistered: orchestrationSkillConfig.naturalLanguagePatterns.length
     };

   } catch (error) {
     console.error('❌ Failed to register orchestration skills:', error);
+    return {
+      success: false,
+      error: error.message
+    };
   }
 }

 /**
  * Auto-registration on import
+ * This ensures orchestration is available immediately when the module is imported
  */
 registerOrchestrationSkills().catch(console.error);

 // Voice command handler for orchestration
 export class OrchestrationVoiceHandler {
   private isActive = false;
+  private orchestrationService = new ConversationalOrchestration();

   async handleWakeWordActivation(context: any) {
     this.isActive = true;

     return {
-      message: '🤖 Orchestration system activated! Just tell me what you want to automate like "I want to retire by 55" or "My customers never buy again".',
-      examples: orchestrationSkillConfig.naturalLanguagePatterns.slice(0, 5),
+      message: "🤖 I'm your complete AI business team! Just tell me what challenge you're facing - like 'I want to retire by 55 while growing my business' or 'My customers shop once and leave' - and I'll automatically organize the perfect solution.",
+      actionDescription: 'Complete business automation setup',
+      patterns: orchestrationSkillConfig.naturalLanguagePatterns.slice(0, 5),
       isOrchestrationMode: true,
     };
   }

-  async processOrchestrationCommand(voiceText: string, context: any) {
+  async processCommand(voiceText: string, context: any) {
     try {
+      // Clean wake word if present
+      const cleanedText = voiceText
+        .replace(/^(atom|hey atom|orchestration|automate)\s*/gi, '')
+        .trim();
+
+      const result = await this.orchestrationService.processUserMessage(
+        context?.userId || 'current-user',
+        cleanedText,
+        {
+          companySize: this.mapToAtomSize(context?.userData?.type || 'solo'),
+          industry
