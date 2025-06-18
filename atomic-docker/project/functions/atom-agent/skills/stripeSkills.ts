import Stripe from 'stripe';
import { ATOM_STRIPE_SECRET_KEY } from '../_libs/constants';
import {
  StripeCharge,
  StripePaymentIntent,
  ListStripePaymentsResponse,
  GetStripePaymentDetailsResponse,
} from '../types';

let stripeClient: Stripe | null = null;

// Export for testing purposes, to reset the client instance if needed.
export function resetStripeClientCache() {
  stripeClient = null;
}

function getStripeClient(): Stripe | null {
  if (stripeClient) {
    return stripeClient;
  }

  if (!ATOM_STRIPE_SECRET_KEY) {
    console.error('Stripe Secret Key not configured.');
    return null;
  }

  // Initialize Stripe with a specific API version for stability and enable TypeScript.
  // The Stripe SDK automatically uses the latest API version by default, but pinning it is good practice.
  stripeClient = new Stripe(ATOM_STRIPE_SECRET_KEY, {
    apiVersion: '2024-04-10', // Specify the API version you are developing against
    typescript: true, // Enable TypeScript specific features from the SDK
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
  options?: {
    limit?: number;
    starting_after?: string; // For pagination: ID of the last object on the previous page
    customer?: string; // Filter by customer ID
  }
): Promise<ListStripePaymentsResponse> {
  const client = getStripeClient();
  if (!client) {
    return { ok: false, error: 'Stripe Secret Key not configured.' };
  }

  try {
    const params: Stripe.PaymentIntentListParams = {
      limit: options?.limit || 10,
      expand: ['data.latest_charge'], // Expand latest_charge to get details like receipt_url
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
      payments: mappedPayments,
      has_more: paymentIntentsResponse.has_more,
    };
  } catch (error: any) {
    console.error('Error listing Stripe payments:', error.message);
    // Stripe errors often have a 'code' and 'message' property.
    // error.raw?.code, error.raw?.message might also be useful.
    return { ok: false, error: error.message || 'Failed to list Stripe payments.' };
  }
}

export async function getStripePaymentDetails(
  paymentIntentId: string
): Promise<GetStripePaymentDetailsResponse> {
  const client = getStripeClient();
  if (!client) {
    return { ok: false, error: 'Stripe Secret Key not configured.' };
  }

  if (!paymentIntentId) {
    return { ok: false, error: 'PaymentIntent ID is required.' };
  }

  try {
    const params: Stripe.PaymentIntentRetrieveParams = {
      expand: ['latest_charge', 'customer'], // Expand for more details
    };
    const paymentIntent = await client.paymentIntents.retrieve(paymentIntentId, params);

    if (!paymentIntent) {
      // This case should ideally be caught by StripeError (e.g., resource_missing)
      return { ok: false, error: 'PaymentIntent not found.' };
    }

    return {
      ok: true,
      payment: mapStripePaymentIntentToInternal(paymentIntent),
    };
  } catch (error: any) {
    console.error(`Error getting Stripe payment details for ID ${paymentIntentId}:`, error.message);
    if (error instanceof Stripe.errors.StripeError) {
      // Handle specific Stripe error codes
      if (error.code === 'resource_missing') {
        return { ok: false, error: `PaymentIntent with ID ${paymentIntentId} not found.` };
      }
      // You can add more specific Stripe error code handling here
      return { ok: false, error: `Stripe API Error: ${error.message} (Code: ${error.code || 'N/A'})` };
    }
    return { ok: false, error: error.message || `Failed to get Stripe payment details for ID ${paymentIntentId}.` };
  }
}
