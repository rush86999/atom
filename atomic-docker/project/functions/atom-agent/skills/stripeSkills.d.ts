import { StripePaymentIntent, StripeSkillResponse, ListStripePaymentsData } from '../types';
export declare function resetStripeClientCache(): void;
export declare function listStripePayments(userId: string, options?: {
    limit?: number;
    starting_after?: string;
    customer?: string;
}): Promise<StripeSkillResponse<ListStripePaymentsData>>;
export declare function getStripePaymentDetails(userId: string, paymentIntentId: string): Promise<StripeSkillResponse<StripePaymentIntent | null>>;
