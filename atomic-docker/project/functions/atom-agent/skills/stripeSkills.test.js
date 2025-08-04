import { listStripePayments, getStripePaymentDetails, resetStripeClientCache, } from './stripeSkills';
import Stripe from 'stripe';
import * as constants from '../_libs/constants';
// Mock the Stripe SDK and constants
jest.mock('stripe');
const MockedStripe = Stripe;
const mockPaymentIntentsList = jest.fn();
const mockPaymentIntentsRetrieve = jest.fn();
// Mock the implementation of the Stripe constructor to return our mocked methods
MockedStripe.mockImplementation(() => ({
    paymentIntents: {
        list: mockPaymentIntentsList,
        retrieve: mockPaymentIntentsRetrieve,
    },
    // Add other Stripe services here if they get used (e.g., customers, charges directly)
})); // Use 'as any' to satisfy Stripe's complex type, we only care about what we use
jest.mock('../_libs/constants', () => ({
    ATOM_STRIPE_SECRET_KEY: 'sk_test_default', // Default mock value
}));
// Spy on console.error and console.log
let consoleErrorSpy;
let consoleLogSpy;
describe('stripeSkills', () => {
    beforeEach(() => {
        mockPaymentIntentsList.mockReset();
        mockPaymentIntentsRetrieve.mockReset();
        MockedStripe.mockClear(); // Clears constructor call count and instance mocks
        resetStripeClientCache(); // Reset our internal client cache
        // Set default mock value for the Stripe key
        // Use Object.defineProperty to modify the read-only mocked constant
        Object.defineProperty(constants, 'ATOM_STRIPE_SECRET_KEY', {
            value: 'sk_test_default',
            writable: true, // Important for it to be modifiable in specific tests
            configurable: true,
        });
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => { });
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
    });
    afterEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });
    describe('Stripe Client Initialization', () => {
        it('should initialize Stripe client once and reuse it for multiple calls', async () => {
            mockPaymentIntentsList.mockResolvedValue({ data: [], has_more: false }); // Mock API response
            await listStripePayments();
            await listStripePayments();
            expect(MockedStripe).toHaveBeenCalledTimes(1); // Constructor called only once
        });
        it('should return error if Stripe key is not configured', async () => {
            Object.defineProperty(constants, 'ATOM_STRIPE_SECRET_KEY', { value: '' }); // Simulate missing key
            const result = await listStripePayments();
            expect(result.ok).toBe(false);
            expect(result.error).toEqual('Stripe Secret Key not configured.');
            expect(MockedStripe).not.toHaveBeenCalled();
            expect(consoleErrorSpy).toHaveBeenCalledWith('Stripe Secret Key not configured.');
        });
    });
    describe('listStripePayments', () => {
        it('should list payments successfully and map them', async () => {
            const mockStripePI = {
                id: 'pi_1',
                object: 'payment_intent',
                amount: 1000,
                currency: 'usd',
                status: 'succeeded',
                created: 1678886400,
                latest_charge: {
                    // Assuming latest_charge is an expanded object
                    id: 'ch_1',
                    object: 'charge',
                    amount: 1000,
                    currency: 'usd',
                    status: 'succeeded',
                    created: 1678886400,
                    receipt_url: 'http://receipt.com/1',
                    description: 'Charge for pi_1',
                }, // Cast to ensure type compatibility for the mock
                customer: 'cus_123',
                description: 'PaymentIntent for cus_123',
                // Add any other mandatory fields for Stripe.PaymentIntent
                client_secret: 'pi_1_secret_xyz',
                amount_capturable: 0,
                amount_details: { tip: {} },
                amount_received: 1000,
                automatic_payment_methods: null,
                canceled_at: null,
                cancellation_reason: null,
                capture_method: 'automatic',
                confirmation_method: 'automatic',
                invoice: null,
                last_payment_error: null,
                livemode: false,
                metadata: {},
                next_action: null,
                on_behalf_of: null,
                payment_method: 'pm_123',
                payment_method_configuration_details: null,
                payment_method_options: {},
                payment_method_types: ['card'],
                processing: null,
                receipt_email: null,
                review: null,
                setup_future_usage: null,
                shipping: null,
                source: null,
                statement_descriptor: null,
                statement_descriptor_suffix: null,
                transfer_data: null,
                transfer_group: null,
                application: null,
                application_fee_amount: null,
            };
            mockPaymentIntentsList.mockResolvedValueOnce({
                data: [mockStripePI],
                has_more: true,
            });
            const result = await listStripePayments({ limit: 1 });
            expect(result.ok).toBe(true);
            expect(result.payments).toHaveLength(1);
            const payment = result.payments[0];
            expect(payment.id).toBe('pi_1');
            expect(payment.amount).toBe(1000);
            expect(payment.latest_charge?.id).toBe('ch_1');
            expect(payment.latest_charge?.receipt_url).toBe('http://receipt.com/1');
            expect(result.has_more).toBe(true);
            expect(mockPaymentIntentsList).toHaveBeenCalledWith({
                limit: 1,
                expand: ['data.latest_charge'],
            });
        });
        it('should pass all options to stripe.paymentIntents.list', async () => {
            mockPaymentIntentsList.mockResolvedValueOnce({
                data: [],
                has_more: false,
            });
            const options = {
                limit: 5,
                starting_after: 'pi_prev',
                customer: 'cus_xyz',
            };
            await listStripePayments(options);
            expect(mockPaymentIntentsList).toHaveBeenCalledWith({
                ...options,
                expand: ['data.latest_charge'],
            });
        });
        it('should handle API error from Stripe', async () => {
            const stripeError = new Error('Stripe API Error');
            stripeError.type = 'StripeAPIError'; // Mimic Stripe error structure
            mockPaymentIntentsList.mockRejectedValueOnce(stripeError);
            const result = await listStripePayments();
            expect(result.ok).toBe(false);
            expect(result.error).toBe('Stripe API Error');
            expect(consoleErrorSpy).toHaveBeenCalledWith('Error listing Stripe payments:', 'Stripe API Error');
        });
    });
    describe('getStripePaymentDetails', () => {
        it('should get payment details successfully and map them', async () => {
            const mockDetailedPI = {
                id: 'pi_detailed',
                object: 'payment_intent',
                amount: 2000,
                currency: 'eur',
                status: 'succeeded',
                created: 1678880000,
                latest_charge: {
                    id: 'ch_detailed',
                    object: 'charge',
                    status: 'succeeded',
                    amount: 2000,
                    currency: 'eur',
                    created: 1678880000,
                    receipt_url: 'http://receipt.com/detailed',
                },
                customer: {
                    id: 'cus_123',
                    object: 'customer',
                    livemode: false,
                    created: 123,
                    default_source: null,
                    delinquent: false,
                    metadata: {},
                    subscriptions: {},
                    tax_exempt: 'none',
                    currency: 'eur',
                    invoice_prefix: 'XX',
                    invoice_settings: {},
                    next_invoice_sequence: 1,
                    phone: null,
                    preferred_locales: [],
                    shipping: null,
                    tax_ids: {},
                    address: null,
                    balance: 0,
                    description: 'Test Customer',
                    email: 'test@example.com',
                    name: 'Test Customer',
                },
                client_secret: 'pi_detailed_secret_xyz',
                amount_capturable: 0,
                amount_details: { tip: {} },
                amount_received: 2000,
                automatic_payment_methods: null,
                canceled_at: null,
                cancellation_reason: null,
                capture_method: 'automatic',
                confirmation_method: 'automatic',
                invoice: null,
                last_payment_error: null,
                livemode: false,
                metadata: {},
                next_action: null,
                on_behalf_of: null,
                payment_method: 'pm_123',
                payment_method_configuration_details: null,
                payment_method_options: {},
                payment_method_types: ['card'],
                processing: null,
                receipt_email: null,
                review: null,
                setup_future_usage: null,
                shipping: null,
                source: null,
                statement_descriptor: null,
                statement_descriptor_suffix: null,
                transfer_data: null,
                transfer_group: null,
                application: null,
                application_fee_amount: null,
            };
            mockPaymentIntentsRetrieve.mockResolvedValueOnce(mockDetailedPI);
            const result = await getStripePaymentDetails('pi_detailed');
            expect(result.ok).toBe(true);
            expect(result.payment?.id).toBe('pi_detailed');
            expect(result.payment?.amount).toBe(2000);
            expect(result.payment?.latest_charge?.id).toBe('ch_detailed');
            expect(result.payment?.latest_charge?.receipt_url).toBe('http://receipt.com/detailed');
            expect(result.payment?.customer).toBe('cus_123'); // Check customer ID mapping
            expect(mockPaymentIntentsRetrieve).toHaveBeenCalledWith('pi_detailed', {
                expand: ['latest_charge', 'customer'],
            });
        });
        it('should return error if paymentIntentId is missing', async () => {
            const result = await getStripePaymentDetails('');
            expect(result.ok).toBe(false);
            expect(result.error).toBe('PaymentIntent ID is required.');
            expect(mockPaymentIntentsRetrieve).not.toHaveBeenCalled();
        });
        it('should handle Stripe "resource_missing" error', async () => {
            // Stripe errors are instances of Stripe.errors.StripeError
            // We need to construct an error object that matches this shape for the test.
            const stripeError = new Stripe.errors.StripeInvalidRequestError({
                code: 'resource_missing',
                doc_url: 'https://stripe.com/docs/error-codes/resource-missing',
                message: 'No such payment_intent: pi_not_found',
                param: 'intent',
                type: 'invalid_request_error',
            });
            mockPaymentIntentsRetrieve.mockRejectedValueOnce(stripeError);
            const result = await getStripePaymentDetails('pi_not_found');
            expect(result.ok).toBe(false);
            expect(result.error).toBe('PaymentIntent with ID pi_not_found not found.');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error getting Stripe payment details for ID pi_not_found:`, stripeError.message);
        });
        it('should handle other API errors from Stripe', async () => {
            const genericStripeError = new Stripe.errors.StripeAPIError({
                message: 'Stripe Server Error',
                type: 'api_error',
            });
            mockPaymentIntentsRetrieve.mockRejectedValueOnce(genericStripeError);
            const result = await getStripePaymentDetails('pi_other_error');
            expect(result.ok).toBe(false);
            expect(result.error).toContain('Stripe API Error: Stripe Server Error');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RyaXBlU2tpbGxzLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzdHJpcGVTa2lsbHMudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQ0wsa0JBQWtCLEVBQ2xCLHVCQUF1QixFQUN2QixzQkFBc0IsR0FDdkIsTUFBTSxnQkFBZ0IsQ0FBQztBQUN4QixPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFDNUIsT0FBTyxLQUFLLFNBQVMsTUFBTSxvQkFBb0IsQ0FBQztBQUdoRCxvQ0FBb0M7QUFDcEMsSUFBSSxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUNwQixNQUFNLFlBQVksR0FBRyxNQUF5QyxDQUFDO0FBQy9ELE1BQU0sc0JBQXNCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBQ3pDLE1BQU0sMEJBQTBCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBRTdDLGlGQUFpRjtBQUNqRixZQUFZLENBQUMsa0JBQWtCLENBQzdCLEdBQUcsRUFBRSxDQUNILENBQUM7SUFDQyxjQUFjLEVBQUU7UUFDZCxJQUFJLEVBQUUsc0JBQXNCO1FBQzVCLFFBQVEsRUFBRSwwQkFBMEI7S0FDckM7SUFDRCxzRkFBc0Y7Q0FDdkYsQ0FBUSxDQUNaLENBQUMsQ0FBQyxnRkFBZ0Y7QUFFbkYsSUFBSSxDQUFDLElBQUksQ0FBQyxvQkFBb0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ3JDLHNCQUFzQixFQUFFLGlCQUFpQixFQUFFLHFCQUFxQjtDQUNqRSxDQUFDLENBQUMsQ0FBQztBQUVKLHVDQUF1QztBQUN2QyxJQUFJLGVBQWlDLENBQUM7QUFDdEMsSUFBSSxhQUErQixDQUFDO0FBRXBDLFFBQVEsQ0FBQyxjQUFjLEVBQUUsR0FBRyxFQUFFO0lBQzVCLFVBQVUsQ0FBQyxHQUFHLEVBQUU7UUFDZCxzQkFBc0IsQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNuQywwQkFBMEIsQ0FBQyxTQUFT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QUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgbGlzdFN0cmlwZVBheW1lbnRzLFxuICBnZXRTdHJpcGVQYXltZW50RGV0YWlscyxcbiAgcmVzZXRTdHJpcGVDbGllbnRDYWNoZSxcbn0gZnJvbSAnLi9zdHJpcGVTa2lsbHMnO1xuaW1wb3J0IFN0cmlwZSBmcm9tICdzdHJpcGUnO1xuaW1wb3J0ICogYXMgY29uc3RhbnRzIGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBTdHJpcGVQYXltZW50SW50ZW50LCBTdHJpcGVDaGFyZ2UgfSBmcm9tICcuLi90eXBlcyc7IC8vIFVzaW5nIG91ciB0eXBlcyBmb3IgZXhwZWN0ZWQgcmVzdWx0c1xuXG4vLyBNb2NrIHRoZSBTdHJpcGUgU0RLIGFuZCBjb25zdGFudHNcbmplc3QubW9jaygnc3RyaXBlJyk7XG5jb25zdCBNb2NrZWRTdHJpcGUgPSBTdHJpcGUgYXMgamVzdC5Nb2NrZWRDbGFzczx0eXBlb2YgU3RyaXBlPjtcbmNvbnN0IG1vY2tQYXltZW50SW50ZW50c0xpc3QgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrUGF5bWVudEludGVudHNSZXRyaWV2ZSA9IGplc3QuZm4oKTtcblxuLy8gTW9jayB0aGUgaW1wbGVtZW50YXRpb24gb2YgdGhlIFN0cmlwZSBjb25zdHJ1Y3RvciB0byByZXR1cm4gb3VyIG1vY2tlZCBtZXRob2RzXG5Nb2NrZWRTdHJpcGUubW9ja0ltcGxlbWVudGF0aW9uKFxuICAoKSA9PlxuICAgICh7XG4gICAgICBwYXltZW50SW50ZW50czoge1xuICAgICAgICBsaXN0OiBtb2NrUGF5bWVudEludGVudHNMaXN0LFxuICAgICAgICByZXRyaWV2ZTogbW9ja1BheW1lbnRJbnRlbnRzUmV0cmlldmUsXG4gICAgICB9LFxuICAgICAgLy8gQWRkIG90aGVyIFN0cmlwZSBzZXJ2aWNlcyBoZXJlIGlmIHRoZXkgZ2V0IHVzZWQgKGUuZy4sIGN1c3RvbWVycywgY2hhcmdlcyBkaXJlY3RseSlcbiAgICB9KSBhcyBhbnlcbik7IC8vIFVzZSAnYXMgYW55JyB0byBzYXRpc2Z5IFN0cmlwZSdzIGNvbXBsZXggdHlwZSwgd2Ugb25seSBjYXJlIGFib3V0IHdoYXQgd2UgdXNlXG5cbmplc3QubW9jaygnLi4vX2xpYnMvY29uc3RhbnRzJywgKCkgPT4gKHtcbiAgQVRPTV9TVFJJUEVfU0VDUkVUX0tFWTogJ3NrX3Rlc3RfZGVmYXVsdCcsIC8vIERlZmF1bHQgbW9jayB2YWx1ZVxufSkpO1xuXG4vLyBTcHkgb24gY29uc29sZS5lcnJvciBhbmQgY29uc29sZS5sb2dcbmxldCBjb25zb2xlRXJyb3JTcHk6IGplc3QuU3B5SW5zdGFuY2U7XG5sZXQgY29uc29sZUxvZ1NweTogamVzdC5TcHlJbnN0YW5jZTtcblxuZGVzY3JpYmUoJ3N0cmlwZVNraWxscycsICgpID0+IHtcbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgbW9ja1BheW1lbnRJbnRlbnRzTGlzdC5tb2NrUmVzZXQoKTtcbiAgICBtb2NrUGF5bWVudEludGVudHNSZXRyaWV2ZS5tb2NrUmVzZXQoKTtcbiAgICBNb2NrZWRTdHJpcGUubW9ja0NsZWFyKCk7IC8vIENsZWFycyBjb25zdHJ1Y3RvciBjYWxsIGNvdW50IGFuZCBpbnN0YW5jZSBtb2Nrc1xuICAgIHJlc2V0U3RyaXBlQ2xpZW50Q2FjaGUoKTsgLy8gUmVzZXQgb3VyIGludGVybmFsIGNsaWVudCBjYWNoZVxuXG4gICAgLy8gU2V0IGRlZmF1bHQgbW9jayB2YWx1ZSBmb3IgdGhlIFN0cmlwZSBrZXlcbiAgICAvLyBVc2UgT2JqZWN0LmRlZmluZVByb3BlcnR5IHRvIG1vZGlmeSB0aGUgcmVhZC1vbmx5IG1vY2tlZCBjb25zdGFudFxuICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShjb25zdGFudHMsICdBVE9NX1NUUklQRV9TRUNSRVRfS0VZJywge1xuICAgICAgdmFsdWU6ICdza190ZXN0X2RlZmF1bHQnLFxuICAgICAgd3JpdGFibGU6IHRydWUsIC8vIEltcG9ydGFudCBmb3IgaXQgdG8gYmUgbW9kaWZpYWJsZSBpbiBzcGVjaWZpYyB0ZXN0c1xuICAgICAgY29uZmlndXJhYmxlOiB0cnVlLFxuICAgIH0pO1xuXG4gICAgY29uc29sZUVycm9yU3B5ID0gamVzdC5zcHlPbihjb25zb2xlLCAnZXJyb3InKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4ge30pO1xuICAgIGNvbnNvbGVMb2dTcHkgPSBqZXN0LnNweU9uKGNvbnNvbGUsICdsb2cnKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4ge30pO1xuICB9KTtcblxuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICAgIGNvbnNvbGVFcnJvclNweS5tb2NrUmVzdG9yZSgpO1xuICAgIGNvbnNvbGVMb2dTcHkubW9ja1Jlc3RvcmUoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ1N0cmlwZSBDbGllbnQgSW5pdGlhbGl6YXRpb24nLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBpbml0aWFsaXplIFN0cmlwZSBjbGllbnQgb25jZSBhbmQgcmV1c2UgaXQgZm9yIG11bHRpcGxlIGNhbGxzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja1BheW1lbnRJbnRlbnRzTGlzdC5tb2NrUmVzb2x2ZWRWYWx1ZSh7IGRhdGE6IFtdLCBoYXNfbW9yZTogZmFsc2UgfSk7IC8vIE1vY2sgQVBJIHJlc3BvbnNlXG4gICAgICBhd2FpdCBsaXN0U3RyaXBlUGF5bWVudHMoKTtcbiAgICAgIGF3YWl0IGxpc3RTdHJpcGVQYXltZW50cygpO1xuICAgICAgZXhwZWN0KE1vY2tlZFN0cmlwZSkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpOyAvLyBDb25zdHJ1Y3RvciBjYWxsZWQgb25seSBvbmNlXG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBTdHJpcGUga2V5IGlzIG5vdCBjb25maWd1cmVkJywgYXN5bmMgKCkgPT4ge1xuICAgICAgT2JqZWN0LmRlZmluZVByb3BlcnR5KGNvbnN0YW50cywgJ0FUT01fU1RSSVBFX1NFQ1JFVF9LRVknLCB7IHZhbHVlOiAnJyB9KTsgLy8gU2ltdWxhdGUgbWlzc2luZyBrZXlcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGxpc3RTdHJpcGVQYXltZW50cygpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0VxdWFsKCdTdHJpcGUgU2VjcmV0IEtleSBub3QgY29uZmlndXJlZC4nKTtcbiAgICAgIGV4cGVjdChNb2NrZWRTdHJpcGUpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgJ1N0cmlwZSBTZWNyZXQgS2V5IG5vdCBjb25maWd1cmVkLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdsaXN0U3RyaXBlUGF5bWVudHMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBsaXN0IHBheW1lbnRzIHN1Y2Nlc3NmdWxseSBhbmQgbWFwIHRoZW0nLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrU3RyaXBlUEk6IFN0cmlwZS5QYXltZW50SW50ZW50ID0ge1xuICAgICAgICBpZDogJ3BpXzEnLFxuICAgICAgICBvYmplY3Q6ICdwYXltZW50X2ludGVudCcsXG4gICAgICAgIGFtb3VudDogMTAwMCxcbiAgICAgICAgY3VycmVuY3k6ICd1c2QnLFxuICAgICAgICBzdGF0dXM6ICdzdWNjZWVkZWQnLFxuICAgICAgICBjcmVhdGVkOiAxNjc4ODg2NDAwLFxuICAgICAgICBsYXRlc3RfY2hhcmdlOiB7XG4gICAgICAgICAgLy8gQXNzdW1pbmcgbGF0ZXN0X2NoYXJnZSBpcyBhbiBleHBhbmRlZCBvYmplY3RcbiAgICAgICAgICBpZDogJ2NoXzEnLFxuICAgICAgICAgIG9iamVjdDogJ2NoYXJnZScsXG4gICAgICAgICAgYW1vdW50OiAxMDAwLFxuICAgICAgICAgIGN1cnJlbmN5OiAndXNkJyxcbiAgICAgICAgICBzdGF0dXM6ICdzdWNjZWVkZWQnLFxuICAgICAgICAgIGNyZWF0ZWQ6IDE2Nzg4ODY0MDAsXG4gICAgICAgICAgcmVjZWlwdF91cmw6ICdodHRwOi8vcmVjZWlwdC5jb20vMScsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdDaGFyZ2UgZm9yIHBpXzEnLFxuICAgICAgICB9IGFzIFN0cmlwZS5DaGFyZ2UsIC8vIENhc3QgdG8gZW5zdXJlIHR5cGUgY29tcGF0aWJpbGl0eSBmb3IgdGhlIG1vY2tcbiAgICAgICAgY3VzdG9tZXI6ICdjdXNfMTIzJyxcbiAgICAgICAgZGVzY3JpcHRpb246ICdQYXltZW50SW50ZW50IGZvciBjdXNfMTIzJyxcbiAgICAgICAgLy8gQWRkIGFueSBvdGhlciBtYW5kYXRvcnkgZmllbGRzIGZvciBTdHJpcGUuUGF5bWVudEludGVudFxuICAgICAgICBjbGllbnRfc2VjcmV0OiAncGlfMV9zZWNyZXRfeHl6JyxcbiAgICAgICAgYW1vdW50X2NhcHR1cmFibGU6IDAsXG4gICAgICAgIGFtb3VudF9kZXRhaWxzOiB7IHRpcDoge30gfSxcbiAgICAgICAgYW1vdW50X3JlY2VpdmVkOiAxMDAwLFxuICAgICAgICBhdXRvbWF0aWNfcGF5bWVudF9tZXRob2RzOiBudWxsLFxuICAgICAgICBjYW5jZWxlZF9hdDogbnVsbCxcbiAgICAgICAgY2FuY2VsbGF0aW9uX3JlYXNvbjogbnVsbCxcbiAgICAgICAgY2FwdHVyZV9tZXRob2Q6ICdhdXRvbWF0aWMnLFxuICAgICAgICBjb25maXJtYXRpb25fbWV0aG9kOiAnYXV0b21hdGljJyxcbiAgICAgICAgaW52b2ljZTogbnVsbCxcbiAgICAgICAgbGFzdF9wYXltZW50X2Vycm9yOiBudWxsLFxuICAgICAgICBsaXZlbW9kZTogZmFsc2UsXG4gICAgICAgIG1ldGFkYXRhOiB7fSxcbiAgICAgICAgbmV4dF9hY3Rpb246IG51bGwsXG4gICAgICAgIG9uX2JlaGFsZl9vZjogbnVsbCxcbiAgICAgICAgcGF5bWVudF9tZXRob2Q6ICdwbV8xMjMnLFxuICAgICAgICBwYXltZW50X21ldGhvZF9jb25maWd1cmF0aW9uX2RldGFpbHM6IG51bGwsXG4gICAgICAgIHBheW1lbnRfbWV0aG9kX29wdGlvbnM6IHt9LFxuICAgICAgICBwYXltZW50X21ldGhvZF90eXBlczogWydjYXJkJ10sXG4gICAgICAgIHByb2Nlc3Npbmc6IG51bGwsXG4gICAgICAgIHJlY2VpcHRfZW1haWw6IG51bGwsXG4gICAgICAgIHJldmlldzogbnVsbCxcbiAgICAgICAgc2V0dXBfZnV0dXJlX3VzYWdlOiBudWxsLFxuICAgICAgICBzaGlwcGluZzogbnVsbCxcbiAgICAgICAgc291cmNlOiBudWxsLFxuICAgICAgICBzdGF0ZW1lbnRfZGVzY3JpcHRvcjogbnVsbCxcbiAgICAgICAgc3RhdGVtZW50X2Rlc2NyaXB0b3Jfc3VmZml4OiBudWxsLFxuICAgICAgICB0cmFuc2Zlcl9kYXRhOiBudWxsLFxuICAgICAgICB0cmFuc2Zlcl9ncm91cDogbnVsbCxcbiAgICAgICAgYXBwbGljYXRpb246IG51bGwsXG4gICAgICAgIGFwcGxpY2F0aW9uX2ZlZV9hbW91bnQ6IG51bGwsXG4gICAgICB9O1xuICAgICAgbW9ja1BheW1lbnRJbnRlbnRzTGlzdC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgICBkYXRhOiBbbW9ja1N0cmlwZVBJXSxcbiAgICAgICAgaGFzX21vcmU6IHRydWUsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGlzdFN0cmlwZVBheW1lbnRzKHsgbGltaXQ6IDEgfSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm9rKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5wYXltZW50cykudG9IYXZlTGVuZ3RoKDEpO1xuICAgICAgY29uc3QgcGF5bWVudCA9IHJlc3VsdC5wYXltZW50cyFbMF07XG4gICAgICBleHBlY3QocGF5bWVudC5pZCkudG9CZSgncGlfMScpO1xuICAgICAgZXhwZWN0KHBheW1lbnQuYW1vdW50KS50b0JlKDEwMDApO1xuICAgICAgZXhwZWN0KHBheW1lbnQubGF0ZXN0X2NoYXJnZT8uaWQpLnRvQmUoJ2NoXzEnKTtcbiAgICAgIGV4cGVjdChwYXltZW50LmxhdGVzdF9jaGFyZ2U/LnJlY2VpcHRfdXJsKS50b0JlKCdodHRwOi8vcmVjZWlwdC5jb20vMScpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5oYXNfbW9yZSkudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChtb2NrUGF5bWVudEludGVudHNMaXN0KS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGxpbWl0OiAxLFxuICAgICAgICBleHBhbmQ6IFsnZGF0YS5sYXRlc3RfY2hhcmdlJ10sXG4gICAgICB9KTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcGFzcyBhbGwgb3B0aW9ucyB0byBzdHJpcGUucGF5bWVudEludGVudHMubGlzdCcsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tQYXltZW50SW50ZW50c0xpc3QubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgZGF0YTogW10sXG4gICAgICAgIGhhc19tb3JlOiBmYWxzZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3Qgb3B0aW9ucyA9IHtcbiAgICAgICAgbGltaXQ6IDUsXG4gICAgICAgIHN0YXJ0aW5nX2FmdGVyOiAncGlfcHJldicsXG4gICAgICAgIGN1c3RvbWVyOiAnY3VzX3h5eicsXG4gICAgICB9O1xuICAgICAgYXdhaXQgbGlzdFN0cmlwZVBheW1lbnRzKG9wdGlvbnMpO1xuICAgICAgZXhwZWN0KG1vY2tQYXltZW50SW50ZW50c0xpc3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHtcbiAgICAgICAgLi4ub3B0aW9ucyxcbiAgICAgICAgZXhwYW5kOiBbJ2RhdGEubGF0ZXN0X2NoYXJnZSddLFxuICAgICAgfSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGhhbmRsZSBBUEkgZXJyb3IgZnJvbSBTdHJpcGUnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBzdHJpcGVFcnJvciA9IG5ldyBFcnJvcignU3RyaXBlIEFQSSBFcnJvcicpO1xuICAgICAgKHN0cmlwZUVycm9yIGFzIGFueSkudHlwZSA9ICdTdHJpcGVBUElFcnJvcic7IC8vIE1pbWljIFN0cmlwZSBlcnJvciBzdHJ1Y3R1cmVcbiAgICAgIG1vY2tQYXltZW50SW50ZW50c0xpc3QubW9ja1JlamVjdGVkVmFsdWVPbmNlKHN0cmlwZUVycm9yKTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGxpc3RTdHJpcGVQYXltZW50cygpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0JlKCdTdHJpcGUgQVBJIEVycm9yJyk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgJ0Vycm9yIGxpc3RpbmcgU3RyaXBlIHBheW1lbnRzOicsXG4gICAgICAgICdTdHJpcGUgQVBJIEVycm9yJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2dldFN0cmlwZVBheW1lbnREZXRhaWxzJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgZ2V0IHBheW1lbnQgZGV0YWlscyBzdWNjZXNzZnVsbHkgYW5kIG1hcCB0aGVtJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0RldGFpbGVkUEk6IFN0cmlwZS5QYXltZW50SW50ZW50ID0ge1xuICAgICAgICBpZDogJ3BpX2RldGFpbGVkJyxcbiAgICAgICAgb2JqZWN0OiAncGF5bWVudF9pbnRlbnQnLFxuICAgICAgICBhbW91bnQ6IDIwMDAsXG4gICAgICAgIGN1cnJlbmN5OiAnZXVyJyxcbiAgICAgICAgc3RhdHVzOiAnc3VjY2VlZGVkJyxcbiAgICAgICAgY3JlYXRlZDogMTY3ODg4MDAwMCxcbiAgICAgICAgbGF0ZXN0X2NoYXJnZToge1xuICAgICAgICAgIGlkOiAnY2hfZGV0YWlsZWQnLFxuICAgICAgICAgIG9iamVjdDogJ2NoYXJnZScsXG4gICAgICAgICAgc3RhdHVzOiAnc3VjY2VlZGVkJyxcbiAgICAgICAgICBhbW91bnQ6IDIwMDAsXG4gICAgICAgICAgY3VycmVuY3k6ICdldXInLFxuICAgICAgICAgIGNyZWF0ZWQ6IDE2Nzg4ODAwMDAsXG4gICAgICAgICAgcmVjZWlwdF91cmw6ICdodHRwOi8vcmVjZWlwdC5jb20vZGV0YWlsZWQnLFxuICAgICAgICB9IGFzIFN0cmlwZS5DaGFyZ2UsXG4gICAgICAgIGN1c3RvbWVyOiB7XG4gICAgICAgICAgaWQ6ICdjdXNfMTIzJyxcbiAgICAgICAgICBvYmplY3Q6ICdjdXN0b21lcicsXG4gICAgICAgICAgbGl2ZW1vZGU6IGZhbHNlLFxuICAgICAgICAgIGNyZWF0ZWQ6IDEyMyxcbiAgICAgICAgICBkZWZhdWx0X3NvdXJjZTogbnVsbCxcbiAgICAgICAgICBkZWxpbnF1ZW50OiBmYWxzZSxcbiAgICAgICAgICBtZXRhZGF0YToge30sXG4gICAgICAgICAgc3Vic2NyaXB0aW9uczoge30gYXMgYW55LFxuICAgICAgICAgIHRheF9leGVtcHQ6ICdub25lJyxcbiAgICAgICAgICBjdXJyZW5jeTogJ2V1cicsXG4gICAgICAgICAgaW52b2ljZV9wcmVmaXg6ICdYWCcsXG4gICAgICAgICAgaW52b2ljZV9zZXR0aW5nczoge30gYXMgYW55LFxuICAgICAgICAgIG5leHRfaW52b2ljZV9zZXF1ZW5jZTogMSxcbiAgICAgICAgICBwaG9uZTogbnVsbCxcbiAgICAgICAgICBwcmVmZXJyZWRfbG9jYWxlczogW10sXG4gICAgICAgICAgc2hpcHBpbmc6IG51bGwsXG4gICAgICAgICAgdGF4X2lkczoge30gYXMgYW55LFxuICAgICAgICAgIGFkZHJlc3M6IG51bGwsXG4gICAgICAgICAgYmFsYW5jZTogMCxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1Rlc3QgQ3VzdG9tZXInLFxuICAgICAgICAgIGVtYWlsOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgICAgbmFtZTogJ1Rlc3QgQ3VzdG9tZXInLFxuICAgICAgICB9LFxuICAgICAgICBjbGllbnRfc2VjcmV0OiAncGlfZGV0YWlsZWRfc2VjcmV0X3h5eicsXG4gICAgICAgIGFtb3VudF9jYXB0dXJhYmxlOiAwLFxuICAgICAgICBhbW91bnRfZGV0YWlsczogeyB0aXA6IHt9IH0sXG4gICAgICAgIGFtb3VudF9yZWNlaXZlZDogMjAwMCxcbiAgICAgICAgYXV0b21hdGljX3BheW1lbnRfbWV0aG9kczogbnVsbCxcbiAgICAgICAgY2FuY2VsZWRfYXQ6IG51bGwsXG4gICAgICAgIGNhbmNlbGxhdGlvbl9yZWFzb246IG51bGwsXG4gICAgICAgIGNhcHR1cmVfbWV0aG9kOiAnYXV0b21hdGljJyxcbiAgICAgICAgY29uZmlybWF0aW9uX21ldGhvZDogJ2F1dG9tYXRpYycsXG4gICAgICAgIGludm9pY2U6IG51bGwsXG4gICAgICAgIGxhc3RfcGF5bWVudF9lcnJvcjogbnVsbCxcbiAgICAgICAgbGl2ZW1vZGU6IGZhbHNlLFxuICAgICAgICBtZXRhZGF0YToge30sXG4gICAgICAgIG5leHRfYWN0aW9uOiBudWxsLFxuICAgICAgICBvbl9iZWhhbGZfb2Y6IG51bGwsXG4gICAgICAgIHBheW1lbnRfbWV0aG9kOiAncG1fMTIzJyxcbiAgICAgICAgcGF5bWVudF9tZXRob2RfY29uZmlndXJhdGlvbl9kZXRhaWxzOiBudWxsLFxuICAgICAgICBwYXltZW50X21ldGhvZF9vcHRpb25zOiB7fSxcbiAgICAgICAgcGF5bWVudF9tZXRob2RfdHlwZXM6IFsnY2FyZCddLFxuICAgICAgICBwcm9jZXNzaW5nOiBudWxsLFxuICAgICAgICByZWNlaXB0X2VtYWlsOiBudWxsLFxuICAgICAgICByZXZpZXc6IG51bGwsXG4gICAgICAgIHNldHVwX2Z1dHVyZV91c2FnZTogbnVsbCxcbiAgICAgICAgc2hpcHBpbmc6IG51bGwsXG4gICAgICAgIHNvdXJjZTogbnVsbCxcbiAgICAgICAgc3RhdGVtZW50X2Rlc2NyaXB0b3I6IG51bGwsXG4gICAgICAgIHN0YXRlbWVudF9kZXNjcmlwdG9yX3N1ZmZpeDogbnVsbCxcbiAgICAgICAgdHJhbnNmZXJfZGF0YTogbnVsbCxcbiAgICAgICAgdHJhbnNmZXJfZ3JvdXA6IG51bGwsXG4gICAgICAgIGFwcGxpY2F0aW9uOiBudWxsLFxuICAgICAgICBhcHBsaWNhdGlvbl9mZWVfYW1vdW50OiBudWxsLFxuICAgICAgfTtcbiAgICAgIG1vY2tQYXltZW50SW50ZW50c1JldHJpZXZlLm1vY2tSZXNvbHZlZFZhbHVlT25jZShtb2NrRGV0YWlsZWRQSSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldFN0cmlwZVBheW1lbnREZXRhaWxzKCdwaV9kZXRhaWxlZCcpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQucGF5bWVudD8uaWQpLnRvQmUoJ3BpX2RldGFpbGVkJyk7XG4gICAgICBleHBlY3QocmVzdWx0LnBheW1lbnQ/LmFtb3VudCkudG9CZSgyMDAwKTtcbiAgICAgIGV4cGVjdChyZXN1bHQucGF5bWVudD8ubGF0ZXN0X2NoYXJnZT8uaWQpLnRvQmUoJ2NoX2RldGFpbGVkJyk7XG4gICAgICBleHBlY3QocmVzdWx0LnBheW1lbnQ/LmxhdGVzdF9jaGFyZ2U/LnJlY2VpcHRfdXJsKS50b0JlKFxuICAgICAgICAnaHR0cDovL3JlY2VpcHQuY29tL2RldGFpbGVkJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXN1bHQucGF5bWVudD8uY3VzdG9tZXIpLnRvQmUoJ2N1c18xMjMnKTsgLy8gQ2hlY2sgY3VzdG9tZXIgSUQgbWFwcGluZ1xuICAgICAgZXhwZWN0KG1vY2tQYXltZW50SW50ZW50c1JldHJpZXZlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCgncGlfZGV0YWlsZWQnLCB7XG4gICAgICAgIGV4cGFuZDogWydsYXRlc3RfY2hhcmdlJywgJ2N1c3RvbWVyJ10sXG4gICAgICB9KTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIHBheW1lbnRJbnRlbnRJZCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0U3RyaXBlUGF5bWVudERldGFpbHMoJycpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0JlKCdQYXltZW50SW50ZW50IElEIGlzIHJlcXVpcmVkLicpO1xuICAgICAgZXhwZWN0KG1vY2tQYXltZW50SW50ZW50c1JldHJpZXZlKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgU3RyaXBlIFwicmVzb3VyY2VfbWlzc2luZ1wiIGVycm9yJywgYXN5bmMgKCkgPT4ge1xuICAgICAgLy8gU3RyaXBlIGVycm9ycyBhcmUgaW5zdGFuY2VzIG9mIFN0cmlwZS5lcnJvcnMuU3RyaXBlRXJyb3JcbiAgICAgIC8vIFdlIG5lZWQgdG8gY29uc3RydWN0IGFuIGVycm9yIG9iamVjdCB0aGF0IG1hdGNoZXMgdGhpcyBzaGFwZSBmb3IgdGhlIHRlc3QuXG4gICAgICBjb25zdCBzdHJpcGVFcnJvciA9IG5ldyBTdHJpcGUuZXJyb3JzLlN0cmlwZUludmFsaWRSZXF1ZXN0RXJyb3Ioe1xuICAgICAgICBjb2RlOiAncmVzb3VyY2VfbWlzc2luZycsXG4gICAgICAgIGRvY191cmw6ICdodHRwczovL3N0cmlwZS5jb20vZG9jcy9lcnJvci1jb2Rlcy9yZXNvdXJjZS1taXNzaW5nJyxcbiAgICAgICAgbWVzc2FnZTogJ05vIHN1Y2ggcGF5bWVudF9pbnRlbnQ6IHBpX25vdF9mb3VuZCcsXG4gICAgICAgIHBhcmFtOiAnaW50ZW50JyxcbiAgICAgICAgdHlwZTogJ2ludmFsaWRfcmVxdWVzdF9lcnJvcicsXG4gICAgICB9KTtcbiAgICAgIG1vY2tQYXltZW50SW50ZW50c1JldHJpZXZlLm1vY2tSZWplY3RlZFZhbHVlT25jZShzdHJpcGVFcnJvcik7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldFN0cmlwZVBheW1lbnREZXRhaWxzKCdwaV9ub3RfZm91bmQnKTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9CZShcbiAgICAgICAgJ1BheW1lbnRJbnRlbnQgd2l0aCBJRCBwaV9ub3RfZm91bmQgbm90IGZvdW5kLidcbiAgICAgICk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEVycm9yIGdldHRpbmcgU3RyaXBlIHBheW1lbnQgZGV0YWlscyBmb3IgSUQgcGlfbm90X2ZvdW5kOmAsXG4gICAgICAgIHN0cmlwZUVycm9yLm1lc3NhZ2VcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGhhbmRsZSBvdGhlciBBUEkgZXJyb3JzIGZyb20gU3RyaXBlJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgZ2VuZXJpY1N0cmlwZUVycm9yID0gbmV3IFN0cmlwZS5lcnJvcnMuU3RyaXBlQVBJRXJyb3Ioe1xuICAgICAgICBtZXNzYWdlOiAnU3RyaXBlIFNlcnZlciBFcnJvcicsXG4gICAgICAgIHR5cGU6ICdhcGlfZXJyb3InLFxuICAgICAgfSk7XG4gICAgICBtb2NrUGF5bWVudEludGVudHNSZXRyaWV2ZS5tb2NrUmVqZWN0ZWRWYWx1ZU9uY2UoZ2VuZXJpY1N0cmlwZUVycm9yKTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldFN0cmlwZVBheW1lbnREZXRhaWxzKCdwaV9vdGhlcl9lcnJvcicpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ1N0cmlwZSBBUEkgRXJyb3I6IFN0cmlwZSBTZXJ2ZXIgRXJyb3InKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==