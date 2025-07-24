import Stripe from 'stripe';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import {
  StripeCharge,
  StripePaymentIntent,
  StripeSkillResponse,
  ListStripePaymentsData,
  SkillError,
} from '../types';

let stripeClient: Stripe | null = null;

export function resetStripeClientCache() {
  stripeClient = null;
}

async function getStripeApiKey(userId: string): Promise<string | null> {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'stripe_api_key',
    };
    const response = await executeGraphQLQuery<{ user_credentials: { encrypted_secret: string }[] }>(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}

async function getStripeClient(userId: string): Promise<Stripe | null> {
  if (stripeClient) {
    return stripeClient;
  }

  const apiKey = await getStripeApiKey(userId);
  if (!apiKey) {
    console.error('Stripe Secret Key not configured for this user.');
    return null;
  }

  stripeClient = new Stripe(apiKey, {
    apiVersion: '2024-04-10',
    typescript: true,
  });

  return stripeClient;
}

// Private helper function to map Stripe's PaymentIntent to our internal StripePaymentIntent type
function mapStripePaymentIntentToInternal(pi: Stripe.PaymentIntent): StripePaymentIntent {
  let latestChargeMapped: StripeCharge | null = null;
  if (pi.latest_charge) {
    // latest_charge can be a string (ID) or an expanded Charge object
    if (typeof pi.latest_charge === 'string') {
      // If it's just an ID, we can't populate details without another API call.
      // For this skill, we'll assume it's expanded or leave it minimal.
      latestChargeMapped = { id: pi.latest_charge, amount: 0, currency: '', status: 'pending', created: 0 }; // Default/placeholder
    } else if (typeof pi.latest_charge === 'object') {
      const charge = pi.latest_charge as Stripe.Charge; // Cast to Stripe.Charge
      latestChargeMapped = {
        id: charge.id,
        amount: charge.amount,
        currency: charge.currency,
        status: charge.status as StripeCharge['status'], // Cast to our more limited status set if necessary
        created: charge.created,
        receipt_url: charge.receipt_url,
        description: charge.description,
      };
    }
  }

  return {
    id: pi.id,
    amount: pi.amount,
    currency: pi.currency,
    status: pi.status as StripePaymentIntent['status'], // Cast to our status set
    created: pi.created,
    customer: typeof pi.customer === 'string' ? pi.customer : pi.customer?.id || null,
    description: pi.description,
    latest_charge: latestChargeMapped,
  };
}

export async function listStripePayments(
  userId: string,
  options?: {
    limit?: number;
    starting_after?: string;
    customer?: string;
  }
): Promise<StripeSkillResponse<ListStripePaymentsData>> {
  const client = await getStripeClient(userId);
  if (!client) {
    return { ok: false, error: { code: 'STRIPE_CONFIG_ERROR', message: 'Stripe Secret Key not configured.' } };
  }

  try {
    const params: Stripe.PaymentIntentListParams = {
      limit: options?.limit || 10,
      expand: ['data.latest_charge'],
    };

    if (options?.starting_after) {
      params.starting_after = options.starting_after;
    }
    if (options?.customer) {
      params.customer = options.customer;
    }

    const paymentIntentsResponse = await client.paymentIntents.list(params);
    const mappedPayments = paymentIntentsResponse.data.map(mapStripePaymentIntentToInternal);

    return {
      ok: true,
      data: {
        payments: mappedPayments,
        has_more: paymentIntentsResponse.has_more,
      }
    };
  } catch (error: any) {
    console.error('Error listing Stripe payments:', error);
    const stripeError = error as Stripe.errors.StripeError;
    return {
        ok: false,
        error: {
            code: stripeError.code || 'STRIPE_API_ERROR',
            message: stripeError.message || 'Failed to list Stripe payments.',
            details: stripeError.raw // Include raw error for more context
        }
    };
  }
}

export async function getStripePaymentDetails(
  userId: string,
  paymentIntentId: string
): Promise<StripeSkillResponse<StripePaymentIntent | null>> { // Data can be null if not found
  const client = await getStripeClient(userId);
  if (!client) {
    return { ok: false, error: { code: 'STRIPE_CONFIG_ERROR', message: 'Stripe Secret Key not configured.' } };
  }

  if (!paymentIntentId || paymentIntentId.trim() === '') {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'PaymentIntent ID is required.' } };
  }

  try {
    const params: Stripe.PaymentIntentRetrieveParams = {
      expand: ['latest_charge', 'customer'],
    };
    const paymentIntent = await client.paymentIntents.retrieve(paymentIntentId, params);

    // retrieve doesn't typically return null for a found resource, it throws a resource_missing error.
    // So, if no error is thrown, paymentIntent should exist.
    return {
      ok: true,
      data: mapStripePaymentIntentToInternal(paymentIntent),
    };
  } catch (error: any) {
    console.error(`Error getting Stripe payment details for ID ${paymentIntentId}:`, error);
    if (error instanceof Stripe.errors.StripeError) {
      if (error.code === 'resource_missing') {
        return {
            ok: false, // Or ok:true, data:null if you prefer to indicate "found nothing" as success
            error: {
                code: 'PAYMENT_INTENT_NOT_FOUND',
                message: `PaymentIntent with ID ${paymentIntentId} not found.`,
                details: error.raw
            }
        };
      }
      return {
          ok: false,
          error: {
              code: error.code || 'STRIPE_API_ERROR',
              message: error.message || 'Stripe API Error',
              details: error.raw
          }
      };
    }
    return {
        ok: false,
        error: {
            code: 'INTERNAL_ERROR',
            message: error.message || `Failed to get Stripe payment details for ID ${paymentIntentId}.`,
            details: error
        }
    };
  }
}
