import {
  listStripePayments,
  getStripePaymentDetails,
  resetStripeClientCache,
} from './stripeSkills';
import Stripe from 'stripe';
import * as constants from '../_libs/constants';
import { StripePaymentIntent, StripeCharge } from '../types'; // Using our types for expected results

// Mock the Stripe SDK and constants
jest.mock('stripe');
const MockedStripe = Stripe as jest.MockedClass<typeof Stripe>;
const mockPaymentIntentsList = jest.fn();
const mockPaymentIntentsRetrieve = jest.fn();

// Mock the implementation of the Stripe constructor to return our mocked methods
MockedStripe.mockImplementation(
  () =>
    ({
      paymentIntents: {
        list: mockPaymentIntentsList,
        retrieve: mockPaymentIntentsRetrieve,
      },
      // Add other Stripe services here if they get used (e.g., customers, charges directly)
    }) as any
); // Use 'as any' to satisfy Stripe's complex type, we only care about what we use

jest.mock('../_libs/constants', () => ({
  ATOM_STRIPE_SECRET_KEY: 'sk_test_default', // Default mock value
}));

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

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

    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
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
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Stripe Secret Key not configured.'
      );
    });
  });

  describe('listStripePayments', () => {
    it('should list payments successfully and map them', async () => {
      const mockStripePI: Stripe.PaymentIntent = {
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
        } as Stripe.Charge, // Cast to ensure type compatibility for the mock
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
      const payment = result.payments![0];
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
      (stripeError as any).type = 'StripeAPIError'; // Mimic Stripe error structure
      mockPaymentIntentsList.mockRejectedValueOnce(stripeError);
      const result = await listStripePayments();
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Stripe API Error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error listing Stripe payments:',
        'Stripe API Error'
      );
    });
  });

  describe('getStripePaymentDetails', () => {
    it('should get payment details successfully and map them', async () => {
      const mockDetailedPI: Stripe.PaymentIntent = {
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
        } as Stripe.Charge,
        customer: {
          id: 'cus_123',
          object: 'customer',
          livemode: false,
          created: 123,
          default_source: null,
          delinquent: false,
          metadata: {},
          subscriptions: {} as any,
          tax_exempt: 'none',
          currency: 'eur',
          invoice_prefix: 'XX',
          invoice_settings: {} as any,
          next_invoice_sequence: 1,
          phone: null,
          preferred_locales: [],
          shipping: null,
          tax_ids: {} as any,
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
      expect(result.payment?.latest_charge?.receipt_url).toBe(
        'http://receipt.com/detailed'
      );
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
      expect(result.error).toBe(
        'PaymentIntent with ID pi_not_found not found.'
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        `Error getting Stripe payment details for ID pi_not_found:`,
        stripeError.message
      );
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
