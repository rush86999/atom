import {
  handleListStripePayments,
  handleGetStripePaymentDetails,
} from '../stripe';
import * as stripeSkills from '../stripeSkills';

jest.mock('../stripeSkills', () => ({
  listStripePayments: jest.fn(),
  getStripePaymentDetails: jest.fn(),
}));

describe('stripe skill', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('handleListStripePayments', () => {
    it('should return a list of Stripe payments', async () => {
      const mockResponse = {
        ok: true,
        payments: [
          {
            id: 'pi_123',
            amount: 1000,
            currency: 'usd',
            status: 'succeeded',
            created: Date.now() / 1000,
          },
        ],
      };
      (stripeSkills.listStripePayments as jest.Mock).mockResolvedValue(
        mockResponse
      );

      const result = await handleListStripePayments('test-user', {});

      expect(result).toContain('Stripe Payments (via NLU):');
      expect(result).toContain('pi_123');
    });

    it('should return a message when there are no payments', async () => {
      (stripeSkills.listStripePayments as jest.Mock).mockResolvedValue({
        ok: true,
        payments: [],
      });

      const result = await handleListStripePayments('test-user', {});

      expect(result).toBe(
        'No Stripe payments found matching your criteria (via NLU).'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (stripeSkills.listStripePayments as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleListStripePayments('test-user', {});

      expect(result).toBe(
        'Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).'
      );
    });
  });

  describe('handleGetStripePaymentDetails', () => {
    it('should return the details of a Stripe payment', async () => {
      const mockResponse = {
        ok: true,
        payment: {
          id: 'pi_123',
          amount: 1000,
          currency: 'usd',
          status: 'succeeded',
          created: Date.now() / 1000,
          description: 'Test payment',
        },
      };
      (stripeSkills.getStripePaymentDetails as jest.Mock).mockResolvedValue(
        mockResponse
      );

      const result = await handleGetStripePaymentDetails('test-user', {
        payment_intent_id: 'pi_123',
      });

      expect(result).toContain('Stripe Payment Details (ID: pi_123, via NLU):');
      expect(result).toContain('Test payment');
    });

    it('should return an error message when the payment intent ID is missing', async () => {
      const result = await handleGetStripePaymentDetails('test-user', {});

      expect(result).toBe(
        'Stripe PaymentIntent ID is required to get details via NLU.'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (stripeSkills.getStripePaymentDetails as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleGetStripePaymentDetails('test-user', {
        payment_intent_id: 'pi_123',
      });

      expect(result).toBe(
        'Sorry, an unexpected error occurred while fetching Stripe payment details for pi_123 (NLU path).'
      );
    });
  });
});
