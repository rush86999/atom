import nodemailer from 'nodemailer';

export const sendEmail = async (options: { to: string, subject: string, html: string }) => {
    // Check if SMTP configuration is present
    if (!process.env.SMTP_HOST || !process.env.SMTP_USER || !process.env.SMTP_PASS) {
        console.warn('⚠️ SMTP configuration missing. Email not sent.');
        console.log(`[Mock Email] To: ${options.to}, Subject: ${options.subject}`);
        return false;
    }

    try {
        const transporter = nodemailer.createTransport({
            host: process.env.SMTP_HOST,
            port: parseInt(process.env.SMTP_PORT || '587'),
            secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
            auth: {
                user: process.env.SMTP_USER,
                pass: process.env.SMTP_PASS,
            },
        });

        const info = await transporter.sendMail({
            from: process.env.EMAIL_FROM || '"Atom Platform" <noreply@atom.ai>',
            to: options.to,
            subject: options.subject,
            html: options.html,
        });

        console.log(`Email sent: ${info.messageId}`);
        return true;
    } catch (error) {
        console.error('Error sending email:', error);
        return false;
    }
};

export const generateVerificationEmailHTML = (code: string, name: string) => {
    return `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Hello ${name},</h2>
        <p>Your verification code for Atom Platform is:</p>
        <div style="background-color: #f4f4f4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
            <strong style="font-size: 24px; letter-spacing: 5px; color: #0070f3;">${code}</strong>
        </div>
        <p>This code will expire in 15 minutes.</p>
        <hr style="border: 1px solid #eee; margin-top: 30px;" />
        <p style="color: #888; font-size: 12px;">If you didn't request this code, you can safely ignore this email.</p>
    </div>
    `;
};
