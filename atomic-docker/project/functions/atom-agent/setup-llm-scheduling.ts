import { initializeMeetingPrepScheduler } from './meetingPrepScheduler';
import { logger } from './_utils/logger';

async function setupLLMPoweredScheduling() {
  try {
    logger.info('🚀 Starting LLM-powered scheduling setup...');

    // Initialize the enhanced scheduler with LLM capabilities
    await initializeMeetingPrepScheduler();

    logger.info('✅ LLM-powered scheduling and meeting preparation system initialized');
    logger.info('📅 Daily briefings scheduled at 7:00 AM');
    logger.info('🔍 Meeting prep generation scheduled at 8:30 AM');
    logger.info('🧠 Intelligent rescheduling scheduled every Monday at 6:00 AM');

  } catch (error) {
    logger.error('❌ Failed to initialize LLM-powered scheduling:', error);
    process.exit(1);
  }
}

// Run the setup if this file is executed directly
if (require.main === module) {
  setupLLMPoweredScheduling();
}

export { setupLLMPoweredScheduling };
