// Helper script to test email sending functionality

// Adjust the path as necessary if this script is moved
const { sendEmail } = require('./_utils/email/email');
const { ENV } = require('./_utils/env');
const { logger } = require('./_utils/logger');

async function testEmail() {
  logger.info('Attempting to send a test email...');

  // Ensure environment variables are loaded (they should be when running via docker-compose)
  logger.info(`SMTP Host: ${ENV.AUTH_SMTP_HOST}`);
  logger.info(`SMTP Port: ${ENV.AUTH_SMTP_PORT}`);
  logger.info(`SMTP User: ${ENV.AUTH_SMTP_USER}`);
  logger.info(`SMTP Sender: ${ENV.AUTH_SMTP_SENDER}`);

  try {
    await sendEmail({
      template: '', // Not using a template for this simple test
      message: {
        to: 'test@example.com',
        subject: 'Test Email from Atomic Agent',
        html: '<p>This is a test email sent by the Atomic Agent.</p>',
        text: 'This is a test email sent by the Atomic Agent.',
      },
      locals: {}, // No locals needed without a template
    });
    logger.info(
      'Test email sent successfully (according to the sendEmail function).'
    );
    logger.info(
      'Please check MailHog UI (usually http://localhost:8025) to verify receipt.'
    );
  } catch (error) {
    logger.error('Failed to send test email:', error);
    // Log specific details from the error if available
    if (error.response) {
      logger.error('SMTP Response:', error.response);
    }
    if (error.rejected) {
      logger.error('Rejected recipients:', error.rejected);
    }
    if (error.rejectedErrors) {
      logger.error('Rejected errors:', error.rejectedErrors);
    }
  }
}

// Run the test
testEmail()
  .then(() => {
    logger.info('Test email script finished.');
  })
  .catch((e) => {
    logger.error('Unhandled error in testEmail script:', e);
  });
