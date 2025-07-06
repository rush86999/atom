import Email from 'email-templates'
import nodemailer from 'nodemailer'

import { logger } from '@utils/logger'
import { EmailLocals, renderTemplate } from './templates'
import { ENV } from '@utils/env'

/**
 * SMTP transport.
 */
const transport = nodemailer.createTransport({
    host: ENV.AUTH_SMTP_HOST,
    port: Number(ENV.AUTH_SMTP_PORT),
    secure: Boolean(ENV.AUTH_SMTP_SECURE),
    auth: {
      pass: ENV.AUTH_SMTP_PASS,
      user: ENV.AUTH_SMTP_USER,
    },
    authMethod: ENV.AUTH_SMTP_AUTH_METHOD,
  });

/**
 * Reusable email client.
 */
export const emailClient = new Email<EmailLocals>({
    transport,
    message: {
      from: ENV.AUTH_SMTP_SENDER,
    },
    send: true,
    render: renderTemplate,
  });


  export const sendEmail = async (
    options: Parameters<typeof emailClient['send']>[0]
  ) => {
    try {
      let headers: typeof options['message']['headers'] = {
        ...options.message.headers,
      };
  
      if (ENV.AUTH_SMTP_X_SMTPAPI_HEADER) {
        headers = {
          ...headers,
          'X-SMTPAPI': ENV.AUTH_SMTP_X_SMTPAPI_HEADER,
        };
      }
  
      const MAX_RETRIES = 3;
      let attempt = 0;
      let lastError: any = null;

      while (attempt < MAX_RETRIES) {
        try {
          await emailClient.send({
            ...options,
            message: { ...options.message, headers },
          });
          logger.info(`Email sent successfully via SMTP on attempt ${attempt + 1}.`, { template: options.template, to: options.message.to });
          return; // Success
        } catch (err) {
          lastError = err;
          logger.warn(`Attempt ${attempt + 1} to send email via SMTP failed. Retrying...`, {
            errorMessage: (err as Error).message,
            template: options.template,
            to: options.message.to,
            attempt: attempt + 1,
            maxRetries: MAX_RETRIES,
          });
          attempt++;
          if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000; // Exponential backoff: 1s, 2s
            await new Promise(resolve => setTimeout(resolve, delay));
          }
        }
      }
      // If all retries fail, log and rethrow the last error
      const finalError = lastError as Error;
      logger.error( // Changed from logger.warn to logger.error for final failure
        `SMTP error after ${MAX_RETRIES} attempts`,
        Object.entries(error).reduce(
          (acc, [key, value]) => ({
            ...acc,
            [key]: value,
          }),
          {}
        )
      );
      logger.warn(`SMTP error context`, {
        template: options.template,
        to: options.message.to,
      });
      throw err;
    }
  };
