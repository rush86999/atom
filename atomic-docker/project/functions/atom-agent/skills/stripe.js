import { listStripePayments as list, getStripePaymentDetails as getDetails, } from './stripeSkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleListStripePayments(userId, entities) {
    try {
        const { limit, starting_after, customer } = entities;
        const options = {};
        if (limit && typeof limit === 'number')
            options.limit = limit;
        else
            options.limit = 10;
        if (starting_after && typeof starting_after === 'string')
            options.starting_after = starting_after;
        if (customer && typeof customer === 'string')
            options.customer = customer;
        const response = await list(options);
        if (response.ok && response.payments && response.payments.length > 0) {
            let output = 'Stripe Payments (via NLU):\n';
            for (const payment of response.payments) {
                output += `- ID: ${payment.id}, Amount: ${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()}, Status: ${payment.status}, Created: ${new Date(payment.created * 1000).toLocaleDateString()}${payment.latest_charge?.receipt_url ? `, Receipt: ${payment.latest_charge.receipt_url}` : ''}\n`;
            }
            if (response.has_more && response.payments.length > 0) {
                output += `More payments available. For next page, use option: starting_after=${response.payments[response.payments.length - 1].id}\n`;
            }
            return output;
        }
        else if (response.ok) {
            return 'No Stripe payments found matching your criteria (via NLU).';
        }
        else {
            return `Error fetching Stripe payments (via NLU): ${response.error || 'Unknown error'}`;
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).');
    }
}
export async function handleGetStripePaymentDetails(userId, entities) {
    try {
        const { payment_intent_id } = entities;
        if (!payment_intent_id || typeof payment_intent_id !== 'string') {
            return 'Stripe PaymentIntent ID is required to get details via NLU.';
        }
        else {
            const response = await getDetails(payment_intent_id);
            if (response.ok && response.payment) {
                const p = response.payment;
                let output = `Stripe Payment Details (ID: ${p.id}, via NLU):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
                if (p.customer)
                    output += `\nCustomer ID: ${p.customer}`;
                if (p.latest_charge?.receipt_url)
                    output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
                return output;
            }
            else {
                return `Error fetching Stripe payment details (via NLU): ${response.error || `PaymentIntent with ID ${payment_intent_id} not found or an unknown error occurred.`}`;
            }
        }
    }
    catch (error) {
        return handleError(error, `Sorry, an unexpected error occurred while fetching Stripe payment details for ${entities.payment_intent_id} (NLU path).`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RyaXBlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3RyaXBlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUlBLE9BQU8sRUFDTCxrQkFBa0IsSUFBSSxJQUFJLEVBQzFCLHVCQUF1QixJQUFJLFVBQVUsR0FDdEMsTUFBTSxnQkFBZ0IsQ0FBQztBQUN4QixPQUFPLEVBQUUsV0FBVyxFQUFFLE1BQU0sMkJBQTJCLENBQUM7QUFFeEQsTUFBTSxDQUFDLEtBQUssVUFBVSx3QkFBd0IsQ0FDNUMsTUFBYyxFQUNkLFFBQWE7SUFFYixJQUFJLENBQUM7UUFDSCxNQUFNLEVBQUUsS0FBSyxFQUFFLGNBQWMsRUFBRSxRQUFRLEVBQUUsR0FBRyxRQUFRLENBQUM7UUFDckQsTUFBTSxPQUFPLEdBSVQsRUFBRSxDQUFDO1FBQ1AsSUFBSSxLQUFLLElBQUksT0FBTyxLQUFLLEtBQUssUUFBUTtZQUFFLE9BQU8sQ0FBQyxLQUFLLEdBQUcsS0FBSyxDQUFDOztZQUN6RCxPQUFPLENBQUMsS0FBSyxHQUFHLEVBQUUsQ0FBQztRQUN4QixJQUFJLGNBQWMsSUFBSSxPQUFPLGNBQWMsS0FBSyxRQUFRO1lBQ3RELE9BQU8sQ0FBQyxjQUFjLEdBQUcsY0FBYyxDQUFDO1FBQzFDLElBQUksUUFBUSxJQUFJLE9BQU8sUUFBUSxLQUFLLFFBQVE7WUFBRSxPQUFPLENBQUMsUUFBUSxHQUFHLFFBQVEsQ0FBQztRQUMxRSxNQUFNLFFBQVEsR0FBK0IsTUFBTSxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUM7UUFDakUsSUFBSSxRQUFRLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxRQUFRLElBQUksUUFBUSxDQUFDLFFBQVEsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDckUsSUFBSSxNQUFNLEdBQUcsOEJBQThCLENBQUM7WUFDNUMsS0FBSyxNQUFNLE9BQU8sSUFBSSxRQUFRLENBQUMsUUFBUSxFQUFFLENBQUM7Z0JBQ3hDLE1BQU0sSUFBSSxTQUFTLE9BQU8s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RixRQUFRLENBQUMsaUJBQWlCLGNBQWMsQ0FDMUgsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgTGlzdFN0cmlwZVBheW1lbnRzUmVzcG9uc2UsXG4gIEdldFN0cmlwZVBheW1lbnREZXRhaWxzUmVzcG9uc2UsXG59IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7XG4gIGxpc3RTdHJpcGVQYXltZW50cyBhcyBsaXN0LFxuICBnZXRTdHJpcGVQYXltZW50RGV0YWlscyBhcyBnZXREZXRhaWxzLFxufSBmcm9tICcuL3N0cmlwZVNraWxscyc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlTGlzdFN0cmlwZVBheW1lbnRzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGxpbWl0LCBzdGFydGluZ19hZnRlciwgY3VzdG9tZXIgfSA9IGVudGl0aWVzO1xuICAgIGNvbnN0IG9wdGlvbnM6IHtcbiAgICAgIGxpbWl0PzogbnVtYmVyO1xuICAgICAgc3RhcnRpbmdfYWZ0ZXI/OiBzdHJpbmc7XG4gICAgICBjdXN0b21lcj86IHN0cmluZztcbiAgICB9ID0ge307XG4gICAgaWYgKGxpbWl0ICYmIHR5cGVvZiBsaW1pdCA9PT0gJ251bWJlcicpIG9wdGlvbnMubGltaXQgPSBsaW1pdDtcbiAgICBlbHNlIG9wdGlvbnMubGltaXQgPSAxMDtcbiAgICBpZiAoc3RhcnRpbmdfYWZ0ZXIgJiYgdHlwZW9mIHN0YXJ0aW5nX2FmdGVyID09PSAnc3RyaW5nJylcbiAgICAgIG9wdGlvbnMuc3RhcnRpbmdfYWZ0ZXIgPSBzdGFydGluZ19hZnRlcjtcbiAgICBpZiAoY3VzdG9tZXIgJiYgdHlwZW9mIGN1c3RvbWVyID09PSAnc3RyaW5nJykgb3B0aW9ucy5jdXN0b21lciA9IGN1c3RvbWVyO1xuICAgIGNvbnN0IHJlc3BvbnNlOiBMaXN0U3RyaXBlUGF5bWVudHNSZXNwb25zZSA9IGF3YWl0IGxpc3Qob3B0aW9ucyk7XG4gICAgaWYgKHJlc3BvbnNlLm9rICYmIHJlc3BvbnNlLnBheW1lbnRzICYmIHJlc3BvbnNlLnBheW1lbnRzLmxlbmd0aCA+IDApIHtcbiAgICAgIGxldCBvdXRwdXQgPSAnU3RyaXBlIFBheW1lbnRzICh2aWEgTkxVKTpcXG4nO1xuICAgICAgZm9yIChjb25zdCBwYXltZW50IG9mIHJlc3BvbnNlLnBheW1lbnRzKSB7XG4gICAgICAgIG91dHB1dCArPSBgLSBJRDogJHtwYXltZW50LmlkfSwgQW1vdW50OiAkeyhwYXltZW50LmFtb3VudCAvIDEwMCkudG9GaXhlZCgyKX0gJHtwYXltZW50LmN1cnJlbmN5LnRvVXBwZXJDYXNlKCl9LCBTdGF0dXM6ICR7cGF5bWVudC5zdGF0dXN9LCBDcmVhdGVkOiAke25ldyBEYXRlKHBheW1lbnQuY3JlYXRlZCAqIDEwMDApLnRvTG9jYWxlRGF0ZVN0cmluZygpfSR7cGF5bWVudC5sYXRlc3RfY2hhcmdlPy5yZWNlaXB0X3VybCA/IGAsIFJlY2VpcHQ6ICR7cGF5bWVudC5sYXRlc3RfY2hhcmdlLnJlY2VpcHRfdXJsfWAgOiAnJ31cXG5gO1xuICAgICAgfVxuICAgICAgaWYgKHJlc3BvbnNlLmhhc19tb3JlICYmIHJlc3BvbnNlLnBheW1lbnRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgb3V0cHV0ICs9IGBNb3JlIHBheW1lbnRzIGF2YWlsYWJsZS4gRm9yIG5leHQgcGFnZSwgdXNlIG9wdGlvbjogc3RhcnRpbmdfYWZ0ZXI9JHtyZXNwb25zZS5wYXltZW50c1tyZXNwb25zZS5wYXltZW50cy5sZW5ndGggLSAxXS5pZH1cXG5gO1xuICAgICAgfVxuICAgICAgcmV0dXJuIG91dHB1dDtcbiAgICB9IGVsc2UgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICByZXR1cm4gJ05vIFN0cmlwZSBwYXltZW50cyBmb3VuZCBtYXRjaGluZyB5b3VyIGNyaXRlcmlhICh2aWEgTkxVKS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICByZXR1cm4gYEVycm9yIGZldGNoaW5nIFN0cmlwZSBwYXltZW50cyAodmlhIE5MVSk6ICR7cmVzcG9uc2UuZXJyb3IgfHwgJ1Vua25vd24gZXJyb3InfWA7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICAnU29ycnksIGFuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgU3RyaXBlIHBheW1lbnRzIChOTFUgcGF0aCkuJ1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUdldFN0cmlwZVBheW1lbnREZXRhaWxzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IHBheW1lbnRfaW50ZW50X2lkIH0gPSBlbnRpdGllcztcbiAgICBpZiAoIXBheW1lbnRfaW50ZW50X2lkIHx8IHR5cGVvZiBwYXltZW50X2ludGVudF9pZCAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnU3RyaXBlIFBheW1lbnRJbnRlbnQgSUQgaXMgcmVxdWlyZWQgdG8gZ2V0IGRldGFpbHMgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCByZXNwb25zZTogR2V0U3RyaXBlUGF5bWVudERldGFpbHNSZXNwb25zZSA9XG4gICAgICAgIGF3YWl0IGdldERldGFpbHMocGF5bWVudF9pbnRlbnRfaWQpO1xuICAgICAgaWYgKHJlc3BvbnNlLm9rICYmIHJlc3BvbnNlLnBheW1lbnQpIHtcbiAgICAgICAgY29uc3QgcCA9IHJlc3BvbnNlLnBheW1lbnQ7XG4gICAgICAgIGxldCBvdXRwdXQgPSBgU3RyaXBlIFBheW1lbnQgRGV0YWlscyAoSUQ6ICR7cC5pZH0sIHZpYSBOTFUpOlxcbkFtb3VudDogJHsocC5hbW91bnQgLyAxMDApLnRvRml4ZWQoMil9ICR7cC5jdXJyZW5jeS50b1VwcGVyQ2FzZSgpfVxcblN0YXR1czogJHtwLnN0YXR1c31cXG5DcmVhdGVkOiAke25ldyBEYXRlKHAuY3JlYXRlZCAqIDEwMDApLnRvTG9jYWxlU3RyaW5nKCl9XFxuRGVzY3JpcHRpb246ICR7cC5kZXNjcmlwdGlvbiB8fCAnTi9BJ31gO1xuICAgICAgICBpZiAocC5jdXN0b21lcikgb3V0cHV0ICs9IGBcXG5DdXN0b21lciBJRDogJHtwLmN1c3RvbWVyfWA7XG4gICAgICAgIGlmIChwLmxhdGVzdF9jaGFyZ2U/LnJlY2VpcHRfdXJsKVxuICAgICAgICAgIG91dHB1dCArPSBgXFxuUmVjZWlwdCBVUkw6ICR7cC5sYXRlc3RfY2hhcmdlLnJlY2VpcHRfdXJsfWA7XG4gICAgICAgIHJldHVybiBvdXRwdXQ7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4gYEVycm9yIGZldGNoaW5nIFN0cmlwZSBwYXltZW50IGRldGFpbHMgKHZpYSBOTFUpOiAke3Jlc3BvbnNlLmVycm9yIHx8IGBQYXltZW50SW50ZW50IHdpdGggSUQgJHtwYXltZW50X2ludGVudF9pZH0gbm90IGZvdW5kIG9yIGFuIHVua25vd24gZXJyb3Igb2NjdXJyZWQuYH1gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgYFNvcnJ5LCBhbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIFN0cmlwZSBwYXltZW50IGRldGFpbHMgZm9yICR7ZW50aXRpZXMucGF5bWVudF9pbnRlbnRfaWR9IChOTFUgcGF0aCkuYFxuICAgICk7XG4gIH1cbn1cbiJdfQ==