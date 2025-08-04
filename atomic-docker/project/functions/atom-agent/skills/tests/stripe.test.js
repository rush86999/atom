import { handleListStripePayments, handleGetStripePaymentDetails, } from '../stripe';
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
            stripeSkills.listStripePayments.mockResolvedValue(mockResponse);
            const result = await handleListStripePayments('test-user', {});
            expect(result).toContain('Stripe Payments (via NLU):');
            expect(result).toContain('pi_123');
        });
        it('should return a message when there are no payments', async () => {
            stripeSkills.listStripePayments.mockResolvedValue({
                ok: true,
                payments: [],
            });
            const result = await handleListStripePayments('test-user', {});
            expect(result).toBe('No Stripe payments found matching your criteria (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            stripeSkills.listStripePayments.mockRejectedValue(new Error('Test Error'));
            const result = await handleListStripePayments('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).');
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
            stripeSkills.getStripePaymentDetails.mockResolvedValue(mockResponse);
            const result = await handleGetStripePaymentDetails('test-user', {
                payment_intent_id: 'pi_123',
            });
            expect(result).toContain('Stripe Payment Details (ID: pi_123, via NLU):');
            expect(result).toContain('Test payment');
        });
        it('should return an error message when the payment intent ID is missing', async () => {
            const result = await handleGetStripePaymentDetails('test-user', {});
            expect(result).toBe('Stripe PaymentIntent ID is required to get details via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            stripeSkills.getStripePaymentDetails.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetStripePaymentDetails('test-user', {
                payment_intent_id: 'pi_123',
            });
            expect(result).toBe('Sorry, an unexpected error occurred while fetching Stripe payment details for pi_123 (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RyaXBlLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzdHJpcGUudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQ0wsd0JBQXdCLEVBQ3hCLDZCQUE2QixHQUM5QixNQUFNLFdBQVcsQ0FBQztBQUNuQixPQUFPLEtBQUssWUFBWSxNQUFNLGlCQUFpQixDQUFDO0FBRWhELElBQUksQ0FBQyxJQUFJLENBQUMsaUJBQWlCLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUNsQyxrQkFBa0IsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0lBQzdCLHVCQUF1QixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7Q0FDbkMsQ0FBQyxDQUFDLENBQUM7QUFFSixRQUFRLENBQUMsY0FBYyxFQUFFLEdBQUcsRUFBRTtJQUM1QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO0lBQ3ZCLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLDBCQUEwQixFQUFFLEdBQUcsRUFBRTtRQUN4QyxFQUFFLENBQUMseUNBQXlDLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDdkQsTUFBTSxZQUFZLEdBQUc7Z0JBQ25CLEVBQUUsRUFBRSxJQUFJO2dCQUNSLFFBQVEsRUFBRTtvQkFDUjt3QkFDRSxFQUFFLEVBQUUsUUFBUTt3QkFDWixNQUFNLEVBQUUsSUFBSTt3QkFDWixRQUFRLEVBQUUsS0FBSzt3QkFDZixNQUFNLEVBQUUsV0FBVzt3QkFDbkIsT0FBTyxFQUFFLElBQUksQ0FBQyxHQUFHLEVBQUUsR0FBRyxJQUFJO3FCQUMzQjtpQkFDRjthQUNGLENBQUM7WUFDRCxZQUFZLENBQUMsa0JBQWdDLENBQUMsaUJBQWlCLENBQzlELFlBQVksQ0FDYixDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSx3QkFBd0IsQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFFL0QsTUFBTSxDQUFDLE1B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dCB7XG4gIGhhbmRsZUxpc3RTdHJpcGVQYXltZW50cyxcbiAgaGFuZGxlR2V0U3RyaXBlUGF5bWVudERldGFpbHMsXG59IGZyb20gJy4uL3N0cmlwZSc7XG5pbXBvcnQgKiBhcyBzdHJpcGVTa2lsbHMgZnJvbSAnLi4vc3RyaXBlU2tpbGxzJztcblxuamVzdC5tb2NrKCcuLi9zdHJpcGVTa2lsbHMnLCAoKSA9PiAoe1xuICBsaXN0U3RyaXBlUGF5bWVudHM6IGplc3QuZm4oKSxcbiAgZ2V0U3RyaXBlUGF5bWVudERldGFpbHM6IGplc3QuZm4oKSxcbn0pKTtcblxuZGVzY3JpYmUoJ3N0cmlwZSBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUxpc3RTdHJpcGVQYXltZW50cycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIGxpc3Qgb2YgU3RyaXBlIHBheW1lbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3BvbnNlID0ge1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgcGF5bWVudHM6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBpZDogJ3BpXzEyMycsXG4gICAgICAgICAgICBhbW91bnQ6IDEwMDAsXG4gICAgICAgICAgICBjdXJyZW5jeTogJ3VzZCcsXG4gICAgICAgICAgICBzdGF0dXM6ICdzdWNjZWVkZWQnLFxuICAgICAgICAgICAgY3JlYXRlZDogRGF0ZS5ub3coKSAvIDEwMDAsXG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgIH07XG4gICAgICAoc3RyaXBlU2tpbGxzLmxpc3RTdHJpcGVQYXltZW50cyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrUmVzcG9uc2VcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3RTdHJpcGVQYXltZW50cygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1N0cmlwZSBQYXltZW50cyAodmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ3BpXzEyMycpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBtZXNzYWdlIHdoZW4gdGhlcmUgYXJlIG5vIHBheW1lbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKHN0cmlwZVNraWxscy5saXN0U3RyaXBlUGF5bWVudHMgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBwYXltZW50czogW10sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdFN0cmlwZVBheW1lbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdObyBTdHJpcGUgcGF5bWVudHMgZm91bmQgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYSAodmlhIE5MVSkuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoc3RyaXBlU2tpbGxzLmxpc3RTdHJpcGVQYXltZW50cyBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdFN0cmlwZVBheW1lbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyBTdHJpcGUgcGF5bWVudHMgKE5MVSBwYXRoKS4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlR2V0U3RyaXBlUGF5bWVudERldGFpbHMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gdGhlIGRldGFpbHMgb2YgYSBTdHJpcGUgcGF5bWVudCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tSZXNwb25zZSA9IHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIHBheW1lbnQ6IHtcbiAgICAgICAgICBpZDogJ3BpXzEyMycsXG4gICAgICAgICAgYW1vdW50OiAxMDAwLFxuICAgICAgICAgIGN1cnJlbmN5OiAndXNkJyxcbiAgICAgICAgICBzdGF0dXM6ICdzdWNjZWVkZWQnLFxuICAgICAgICAgIGNyZWF0ZWQ6IERhdGUubm93KCkgLyAxMDAwLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGVzdCBwYXltZW50JyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICAoc3RyaXBlU2tpbGxzLmdldFN0cmlwZVBheW1lbnREZXRhaWxzIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIG1vY2tSZXNwb25zZVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0U3RyaXBlUGF5bWVudERldGFpbHMoJ3Rlc3QtdXNlcicsIHtcbiAgICAgICAgcGF5bWVudF9pbnRlbnRfaWQ6ICdwaV8xMjMnLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignU3RyaXBlIFBheW1lbnQgRGV0YWlscyAoSUQ6IHBpXzEyMywgdmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1Rlc3QgcGF5bWVudCcpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBwYXltZW50IGludGVudCBJRCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0U3RyaXBlUGF5bWVudERldGFpbHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1N0cmlwZSBQYXltZW50SW50ZW50IElEIGlzIHJlcXVpcmVkIHRvIGdldCBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoc3RyaXBlU2tpbGxzLmdldFN0cmlwZVBheW1lbnREZXRhaWxzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRTdHJpcGVQYXltZW50RGV0YWlscygndGVzdC11c2VyJywge1xuICAgICAgICBwYXltZW50X2ludGVudF9pZDogJ3BpXzEyMycsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1NvcnJ5LCBhbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIFN0cmlwZSBwYXltZW50IGRldGFpbHMgZm9yIHBpXzEyMyAoTkxVIHBhdGgpLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=