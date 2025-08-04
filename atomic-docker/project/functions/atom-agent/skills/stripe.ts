import {
  ListStripePaymentsResponse,
  GetStripePaymentDetailsResponse,
} from '../../types';
import {
  listStripePayments as list,
  getStripePaymentDetails as getDetails,
} from './stripeSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListStripePayments(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const { limit, starting_after, customer } = entities;
    const options: {
      limit?: number;
      starting_after?: string;
      customer?: string;
    } = {};
    if (limit && typeof limit === 'number') options.limit = limit;
    else options.limit = 10;
    if (starting_after && typeof starting_after === 'string')
      options.starting_after = starting_after;
    if (customer && typeof customer === 'string') options.customer = customer;
    const response: ListStripePaymentsResponse = await list(options);
    if (response.ok && response.payments && response.payments.length > 0) {
      let output = 'Stripe Payments (via NLU):\n';
      for (const payment of response.payments) {
        output += `- ID: ${payment.id}, Amount: ${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()}, Status: ${payment.status}, Created: ${new Date(payment.created * 1000).toLocaleDateString()}${payment.latest_charge?.receipt_url ? `, Receipt: ${payment.latest_charge.receipt_url}` : ''}\n`;
      }
      if (response.has_more && response.payments.length > 0) {
        output += `More payments available. For next page, use option: starting_after=${response.payments[response.payments.length - 1].id}\n`;
      }
      return output;
    } else if (response.ok) {
      return 'No Stripe payments found matching your criteria (via NLU).';
    } else {
      return `Error fetching Stripe payments (via NLU): ${response.error || 'Unknown error'}`;
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).'
    );
  }
}

export async function handleGetStripePaymentDetails(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const { payment_intent_id } = entities;
    if (!payment_intent_id || typeof payment_intent_id !== 'string') {
      return 'Stripe PaymentIntent ID is required to get details via NLU.';
    } else {
      const response: GetStripePaymentDetailsResponse =
        await getDetails(payment_intent_id);
      if (response.ok && response.payment) {
        const p = response.payment;
        let output = `Stripe Payment Details (ID: ${p.id}, via NLU):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
        if (p.customer) output += `\nCustomer ID: ${p.customer}`;
        if (p.latest_charge?.receipt_url)
          output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
        return output;
      } else {
        return `Error fetching Stripe payment details (via NLU): ${response.error || `PaymentIntent with ID ${payment_intent_id} not found or an unknown error occurred.`}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      `Sorry, an unexpected error occurred while fetching Stripe payment details for ${entities.payment_intent_id} (NLU path).`
    );
  }
}
