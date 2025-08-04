/**
 * Reusable email client.
 */
export declare const emailClient: any;
export declare const sendEmail: (options: Parameters<(typeof emailClient)["send"]>[0]) => Promise<void>;
