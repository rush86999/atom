import Stripe from 'stripe';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
let stripeClient = null;
export function resetStripeClientCache() {
    stripeClient = null;
}
async function getStripeApiKey(userId) {
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
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
async function getStripeClient(userId) {
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
function mapStripePaymentIntentToInternal(pi) {
    let latestChargeMapped = null;
    if (pi.latest_charge) {
        // latest_charge can be a string (ID) or an expanded Charge object
        if (typeof pi.latest_charge === 'string') {
            // If it's just an ID, we can't populate details without another API call.
            // For this skill, we'll assume it's expanded or leave it minimal.
            latestChargeMapped = {
                id: pi.latest_charge,
                amount: 0,
                currency: '',
                status: 'pending',
                created: 0,
            }; // Default/placeholder
        }
        else if (typeof pi.latest_charge === 'object') {
            const charge = pi.latest_charge; // Cast to Stripe.Charge
            latestChargeMapped = {
                id: charge.id,
                amount: charge.amount,
                currency: charge.currency,
                status: charge.status, // Cast to our more limited status set if necessary
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
        status: pi.status, // Cast to our status set
        created: pi.created,
        customer: typeof pi.customer === 'string' ? pi.customer : pi.customer?.id || null,
        description: pi.description,
        latest_charge: latestChargeMapped,
    };
}
export async function listStripePayments(userId, options) {
    const client = await getStripeClient(userId);
    if (!client) {
        return {
            ok: false,
            error: {
                code: 'STRIPE_CONFIG_ERROR',
                message: 'Stripe Secret Key not configured.',
            },
        };
    }
    try {
        const params = {
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
            },
        };
    }
    catch (error) {
        console.error('Error listing Stripe payments:', error);
        const stripeError = error;
        return {
            ok: false,
            error: {
                code: stripeError.code || 'STRIPE_API_ERROR',
                message: stripeError.message || 'Failed to list Stripe payments.',
                details: stripeError.raw, // Include raw error for more context
            },
        };
    }
}
export async function getStripePaymentDetails(userId, paymentIntentId) {
    // Data can be null if not found
    const client = await getStripeClient(userId);
    if (!client) {
        return {
            ok: false,
            error: {
                code: 'STRIPE_CONFIG_ERROR',
                message: 'Stripe Secret Key not configured.',
            },
        };
    }
    if (!paymentIntentId || paymentIntentId.trim() === '') {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'PaymentIntent ID is required.',
            },
        };
    }
    try {
        const params = {
            expand: ['latest_charge', 'customer'],
        };
        const paymentIntent = await client.paymentIntents.retrieve(paymentIntentId, params);
        // retrieve doesn't typically return null for a found resource, it throws a resource_missing error.
        // So, if no error is thrown, paymentIntent should exist.
        return {
            ok: true,
            data: mapStripePaymentIntentToInternal(paymentIntent),
        };
    }
    catch (error) {
        console.error(`Error getting Stripe payment details for ID ${paymentIntentId}:`, error);
        if (error instanceof Stripe.errors.StripeError) {
            if (error.code === 'resource_missing') {
                return {
                    ok: false, // Or ok:true, data:null if you prefer to indicate "found nothing" as success
                    error: {
                        code: 'PAYMENT_INTENT_NOT_FOUND',
                        message: `PaymentIntent with ID ${paymentIntentId} not found.`,
                        details: error.raw,
                    },
                };
            }
            return {
                ok: false,
                error: {
                    code: error.code || 'STRIPE_API_ERROR',
                    message: error.message || 'Stripe API Error',
                    details: error.raw,
                },
            };
        }
        return {
            ok: false,
            error: {
                code: 'INTERNAL_ERROR',
                message: error.message ||
                    `Failed to get Stripe payment details for ID ${paymentIntentId}.`,
                details: error,
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RyaXBlU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3RyaXBlU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQUM1QixPQUFPLEVBQUUsT0FBTyxFQUFFLE1BQU0saUJBQWlCLENBQUM7QUFDMUMsT0FBTyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sd0JBQXdCLENBQUM7QUFTN0QsSUFBSSxZQUFZLEdBQWtCLElBQUksQ0FBQztBQUV2QyxNQUFNLFVBQVUsc0JBQXNCO0lBQ3BDLFlBQVksR0FBRyxJQUFJLENBQUM7QUFDdEIsQ0FBQztBQUVELEtBQUssVUFBVSxlQUFlLENBQUMsTUFBYztJQUMzQyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixXQUFXLEVBQUUsZ0JBQWdCO0tBQzlCLENBQUM7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLG1CQUFtQixDQUV2QyxLQUFLLEVBQUUsU0FBUyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQ2xELElBQUksUUFBUSxDQUFDLGdCQUFnQixJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDdEUsT0FBTyxPQUFPLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUNELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQztBQUVELEtBQUssVUFBVSxlQUFlLENBQUMsTUFBYztJQUMzQyxJQUFJLFlBQVksRUFBRSxDQUFDO1FBQ2pCLE9BQU8sWUFBWSxDQUFDO0lBQ3RCLENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUM3QyxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFD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O2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUsS0FBSyxDQUFDLElBQUksSUFBSSxrQkFBa0I7b0JBQ3RDLE9BQU8sRUFBRSxLQUFLLENBQUMsT0FBTyxJQUFJLGtCQUFrQjtvQkFDNUMsT0FBTyxFQUFFLEtBQUssQ0FBQyxHQUFHO2lCQUNuQjthQUNGLENBQUM7UUFDSixDQUFDO1FBQ0QsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxnQkFBZ0I7Z0JBQ3RCLE9BQU8sRUFDTCxLQUFLLENBQUMsT0FBTztvQkFDYiwrQ0FBK0MsZUFBZSxHQUFHO2dCQUNuRSxPQUFPLEVBQUUsS0FBSzthQUNmO1NBQ0YsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFN0cmlwZSBmcm9tICdzdHJpcGUnO1xuaW1wb3J0IHsgZGVjcnlwdCB9IGZyb20gJy4uL19saWJzL2NyeXB0byc7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQge1xuICBTdHJpcGVDaGFyZ2UsXG4gIFN0cmlwZVBheW1lbnRJbnRlbnQsXG4gIFN0cmlwZVNraWxsUmVzcG9uc2UsXG4gIExpc3RTdHJpcGVQYXltZW50c0RhdGEsXG4gIFNraWxsRXJyb3IsXG59IGZyb20gJy4uL3R5cGVzJztcblxubGV0IHN0cmlwZUNsaWVudDogU3RyaXBlIHwgbnVsbCA9IG51bGw7XG5cbmV4cG9ydCBmdW5jdGlvbiByZXNldFN0cmlwZUNsaWVudENhY2hlKCkge1xuICBzdHJpcGVDbGllbnQgPSBudWxsO1xufVxuXG5hc3luYyBmdW5jdGlvbiBnZXRTdHJpcGVBcGlLZXkodXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJDcmVkZW50aWFsKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9jcmVkZW50aWFscyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlX25hbWU6IHtfZXE6ICRzZXJ2aWNlTmFtZX19KSB7XG4gICAgICAgICAgICAgICAgZW5jcnlwdGVkX3NlY3JldFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBzZXJ2aWNlTmFtZTogJ3N0cmlwZV9hcGlfa2V5JyxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX2NyZWRlbnRpYWxzOiB7IGVuY3J5cHRlZF9zZWNyZXQ6IHN0cmluZyB9W107XG4gIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyQ3JlZGVudGlhbCcsIHVzZXJJZCk7XG4gIGlmIChyZXNwb25zZS51c2VyX2NyZWRlbnRpYWxzICYmIHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMubGVuZ3RoID4gMCkge1xuICAgIHJldHVybiBkZWNyeXB0KHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHNbMF0uZW5jcnlwdGVkX3NlY3JldCk7XG4gIH1cbiAgcmV0dXJuIG51bGw7XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFN0cmlwZUNsaWVudCh1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8U3RyaXBlIHwgbnVsbD4ge1xuICBpZiAoc3RyaXBlQ2xpZW50KSB7XG4gICAgcmV0dXJuIHN0cmlwZUNsaWVudDtcbiAgfVxuXG4gIGNvbnN0IGFwaUtleSA9IGF3YWl0IGdldFN0cmlwZUFwaUtleSh1c2VySWQpO1xuICBpZiAoIWFwaUtleSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ1N0cmlwZSBTZWNyZXQgS2V5IG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBzdHJpcGVDbGllbnQgPSBuZXcgU3RyaXBlKGFwaUtleSwge1xuICAgIGFwaVZlcnNpb246ICcyMDI0LTA0LTEwJyxcbiAgICB0eXBlc2NyaXB0OiB0cnVlLFxuICB9KTtcblxuICByZXR1cm4gc3RyaXBlQ2xpZW50O1xufVxuXG4vLyBQcml2YXRlIGhlbHBlciBmdW5jdGlvbiB0byBtYXAgU3RyaXBlJ3MgUGF5bWVudEludGVudCB0byBvdXIgaW50ZXJuYWwgU3RyaXBlUGF5bWVudEludGVudCB0eXBlXG5mdW5jdGlvbiBtYXBTdHJpcGVQYXltZW50SW50ZW50VG9JbnRlcm5hbChcbiAgcGk6IFN0cmlwZS5QYXltZW50SW50ZW50XG4pOiBTdHJpcGVQYXltZW50SW50ZW50IHtcbiAgbGV0IGxhdGVzdENoYXJnZU1hcHBlZDogU3RyaXBlQ2hhcmdlIHwgbnVsbCA9IG51bGw7XG4gIGlmIChwaS5sYXRlc3RfY2hhcmdlKSB7XG4gICAgLy8gbGF0ZXN0X2NoYXJnZSBjYW4gYmUgYSBzdHJpbmcgKElEKSBvciBhbiBleHBhbmRlZCBDaGFyZ2Ugb2JqZWN0XG4gICAgaWYgKHR5cGVvZiBwaS5sYXRlc3RfY2hhcmdlID09PSAnc3RyaW5nJykge1xuICAgICAgLy8gSWYgaXQncyBqdXN0IGFuIElELCB3ZSBjYW4ndCBwb3B1bGF0ZSBkZXRhaWxzIHdpdGhvdXQgYW5vdGhlciBBUEkgY2FsbC5cbiAgICAgIC8vIEZvciB0aGlzIHNraWxsLCB3ZSdsbCBhc3N1bWUgaXQncyBleHBhbmRlZCBvciBsZWF2ZSBpdCBtaW5pbWFsLlxuICAgICAgbGF0ZXN0Q2hhcmdlTWFwcGVkID0ge1xuICAgICAgICBpZDogcGkubGF0ZXN0X2NoYXJnZSxcbiAgICAgICAgYW1vdW50OiAwLFxuICAgICAgICBjdXJyZW5jeTogJycsXG4gICAgICAgIHN0YXR1czogJ3BlbmRpbmcnLFxuICAgICAgICBjcmVhdGVkOiAwLFxuICAgICAgfTsgLy8gRGVmYXVsdC9wbGFjZWhvbGRlclxuICAgIH0gZWxzZSBpZiAodHlwZW9mIHBpLmxhdGVzdF9jaGFyZ2UgPT09ICdvYmplY3QnKSB7XG4gICAgICBjb25zdCBjaGFyZ2UgPSBwaS5sYXRlc3RfY2hhcmdlIGFzIFN0cmlwZS5DaGFyZ2U7IC8vIENhc3QgdG8gU3RyaXBlLkNoYXJnZVxuICAgICAgbGF0ZXN0Q2hhcmdlTWFwcGVkID0ge1xuICAgICAgICBpZDogY2hhcmdlLmlkLFxuICAgICAgICBhbW91bnQ6IGNoYXJnZS5hbW91bnQsXG4gICAgICAgIGN1cnJlbmN5OiBjaGFyZ2UuY3VycmVuY3ksXG4gICAgICAgIHN0YXR1czogY2hhcmdlLnN0YXR1cyBhcyBTdHJpcGVDaGFyZ2VbJ3N0YXR1cyddLCAvLyBDYXN0IHRvIG91ciBtb3JlIGxpbWl0ZWQgc3RhdHVzIHNldCBpZiBuZWNlc3NhcnlcbiAgICAgICAgY3JlYXRlZDogY2hhcmdlLmNyZWF0ZWQsXG4gICAgICAgIHJlY2VpcHRfdXJsOiBjaGFyZ2UucmVjZWlwdF91cmwsXG4gICAgICAgIGRlc2NyaXB0aW9uOiBjaGFyZ2UuZGVzY3JpcHRpb24sXG4gICAgICB9O1xuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgaWQ6IHBpLmlkLFxuICAgIGFtb3VudDogcGkuYW1vdW50LFxuICAgIGN1cnJlbmN5OiBwaS5jdXJyZW5jeSxcbiAgICBzdGF0dXM6IHBpLnN0YXR1cyBhcyBTdHJpcGVQYXltZW50SW50ZW50WydzdGF0dXMnXSwgLy8gQ2FzdCB0byBvdXIgc3RhdHVzIHNldFxuICAgIGNyZWF0ZWQ6IHBpLmNyZWF0ZWQsXG4gICAgY3VzdG9tZXI6XG4gICAgICB0eXBlb2YgcGkuY3VzdG9tZXIgPT09ICdzdHJpbmcnID8gcGkuY3VzdG9tZXIgOiBwaS5jdXN0b21lcj8uaWQgfHwgbnVsbCxcbiAgICBkZXNjcmlwdGlvbjogcGkuZGVzY3JpcHRpb24sXG4gICAgbGF0ZXN0X2NoYXJnZTogbGF0ZXN0Q2hhcmdlTWFwcGVkLFxuICB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbGlzdFN0cmlwZVBheW1lbnRzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgb3B0aW9ucz86IHtcbiAgICBsaW1pdD86IG51bWJlcjtcbiAgICBzdGFydGluZ19hZnRlcj86IHN0cmluZztcbiAgICBjdXN0b21lcj86IHN0cmluZztcbiAgfVxuKTogUHJvbWlzZTxTdHJpcGVTa2lsbFJlc3BvbnNlPExpc3RTdHJpcGVQYXltZW50c0RhdGE+PiB7XG4gIGNvbnN0IGNsaWVudCA9IGF3YWl0IGdldFN0cmlwZUNsaWVudCh1c2VySWQpO1xuICBpZiAoIWNsaWVudCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnU1RSSVBFX0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdTdHJpcGUgU2VjcmV0IEtleSBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBwYXJhbXM6IFN0cmlwZS5QYXltZW50SW50ZW50TGlzdFBhcmFtcyA9IHtcbiAgICAgIGxpbWl0OiBvcHRpb25zPy5saW1pdCB8fCAxMCxcbiAgICAgIGV4cGFuZDogWydkYXRhLmxhdGVzdF9jaGFyZ2UnXSxcbiAgICB9O1xuXG4gICAgaWYgKG9wdGlvbnM/LnN0YXJ0aW5nX2FmdGVyKSB7XG4gICAgICBwYXJhbXMuc3RhcnRpbmdfYWZ0ZXIgPSBvcHRpb25zLnN0YXJ0aW5nX2FmdGVyO1xuICAgIH1cbiAgICBpZiAob3B0aW9ucz8uY3VzdG9tZXIpIHtcbiAgICAgIHBhcmFtcy5jdXN0b21lciA9IG9wdGlvbnMuY3VzdG9tZXI7XG4gICAgfVxuXG4gICAgY29uc3QgcGF5bWVudEludGVudHNSZXNwb25zZSA9IGF3YWl0IGNsaWVudC5wYXltZW50SW50ZW50cy5saXN0KHBhcmFtcyk7XG4gICAgY29uc3QgbWFwcGVkUGF5bWVudHMgPSBwYXltZW50SW50ZW50c1Jlc3BvbnNlLmRhdGEubWFwKFxuICAgICAgbWFwU3RyaXBlUGF5bWVudEludGVudFRvSW50ZXJuYWxcbiAgICApO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YToge1xuICAgICAgICBwYXltZW50czogbWFwcGVkUGF5bWVudHMsXG4gICAgICAgIGhhc19tb3JlOiBwYXltZW50SW50ZW50c1Jlc3BvbnNlLmhhc19tb3JlLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgbGlzdGluZyBTdHJpcGUgcGF5bWVudHM6JywgZXJyb3IpO1xuICAgIGNvbnN0IHN0cmlwZUVycm9yID0gZXJyb3IgYXMgU3RyaXBlLmVycm9ycy5TdHJpcGVFcnJvcjtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogc3RyaXBlRXJyb3IuY29kZSB8fCAnU1RSSVBFX0FQSV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IHN0cmlwZUVycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBsaXN0IFN0cmlwZSBwYXltZW50cy4nLFxuICAgICAgICBkZXRhaWxzOiBzdHJpcGVFcnJvci5yYXcsIC8vIEluY2x1ZGUgcmF3IGVycm9yIGZvciBtb3JlIGNvbnRleHRcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U3RyaXBlUGF5bWVudERldGFpbHMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwYXltZW50SW50ZW50SWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTdHJpcGVTa2lsbFJlc3BvbnNlPFN0cmlwZVBheW1lbnRJbnRlbnQgfCBudWxsPj4ge1xuICAvLyBEYXRhIGNhbiBiZSBudWxsIGlmIG5vdCBmb3VuZFxuICBjb25zdCBjbGllbnQgPSBhd2FpdCBnZXRTdHJpcGVDbGllbnQodXNlcklkKTtcbiAgaWYgKCFjbGllbnQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1NUUklQRV9DT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnU3RyaXBlIFNlY3JldCBLZXkgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmICghcGF5bWVudEludGVudElkIHx8IHBheW1lbnRJbnRlbnRJZC50cmltKCkgPT09ICcnKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1BheW1lbnRJbnRlbnQgSUQgaXMgcmVxdWlyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcGFyYW1zOiBTdHJpcGUuUGF5bWVudEludGVudFJldHJpZXZlUGFyYW1zID0ge1xuICAgICAgZXhwYW5kOiBbJ2xhdGVzdF9jaGFyZ2UnLCAnY3VzdG9tZXInXSxcbiAgICB9O1xuICAgIGNvbnN0IHBheW1lbnRJbnRlbnQgPSBhd2FpdCBjbGllbnQucGF5bWVudEludGVudHMucmV0cmlldmUoXG4gICAgICBwYXltZW50SW50ZW50SWQsXG4gICAgICBwYXJhbXNcbiAgICApO1xuXG4gICAgLy8gcmV0cmlldmUgZG9lc24ndCB0eXBpY2FsbHkgcmV0dXJuIG51bGwgZm9yIGEgZm91bmQgcmVzb3VyY2UsIGl0IHRocm93cyBhIHJlc291cmNlX21pc3NpbmcgZXJyb3IuXG4gICAgLy8gU28sIGlmIG5vIGVycm9yIGlzIHRocm93biwgcGF5bWVudEludGVudCBzaG91bGQgZXhpc3QuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YTogbWFwU3RyaXBlUGF5bWVudEludGVudFRvSW50ZXJuYWwocGF5bWVudEludGVudCksXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgZ2V0dGluZyBTdHJpcGUgcGF5bWVudCBkZXRhaWxzIGZvciBJRCAke3BheW1lbnRJbnRlbnRJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBpZiAoZXJyb3IgaW5zdGFuY2VvZiBTdHJpcGUuZXJyb3JzLlN0cmlwZUVycm9yKSB7XG4gICAgICBpZiAoZXJyb3IuY29kZSA9PT0gJ3Jlc291cmNlX21pc3NpbmcnKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgb2s6IGZhbHNlLCAvLyBPciBvazp0cnVlLCBkYXRhOm51bGwgaWYgeW91IHByZWZlciB0byBpbmRpY2F0ZSBcImZvdW5kIG5vdGhpbmdcIiBhcyBzdWNjZXNzXG4gICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgIGNvZGU6ICdQQVlNRU5UX0lOVEVOVF9OT1RfRk9VTkQnLFxuICAgICAgICAgICAgbWVzc2FnZTogYFBheW1lbnRJbnRlbnQgd2l0aCBJRCAke3BheW1lbnRJbnRlbnRJZH0gbm90IGZvdW5kLmAsXG4gICAgICAgICAgICBkZXRhaWxzOiBlcnJvci5yYXcsXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiBlcnJvci5jb2RlIHx8ICdTVFJJUEVfQVBJX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiBlcnJvci5tZXNzYWdlIHx8ICdTdHJpcGUgQVBJIEVycm9yJyxcbiAgICAgICAgICBkZXRhaWxzOiBlcnJvci5yYXcsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICBlcnJvci5tZXNzYWdlIHx8XG4gICAgICAgICAgYEZhaWxlZCB0byBnZXQgU3RyaXBlIHBheW1lbnQgZGV0YWlscyBmb3IgSUQgJHtwYXltZW50SW50ZW50SWR9LmAsXG4gICAgICAgIGRldGFpbHM6IGVycm9yLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG4iXX0=