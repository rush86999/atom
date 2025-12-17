export const sendEmail = async (options: { to: string, subject: string, html: string }) => {
    console.log(`Sending email to ${options.to} with subject: ${options.subject}`);
    return true;
};

export const generateVerificationEmailHTML = (code: string, name: string) => {
    return `<h1>Hello ${name},</h1><p>Your verification code is: <strong>${code}</strong></p>`;
};
