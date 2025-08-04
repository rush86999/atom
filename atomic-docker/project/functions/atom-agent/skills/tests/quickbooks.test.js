import { handleGetQuickBooksAuthUrl, handleListQuickBooksInvoices, handleGetQuickBooksInvoiceDetails, } from '../quickbooks';
import * as quickbooksSkills from '../quickbooksSkills';
jest.mock('../quickbooksSkills', () => ({
    getAuthUri: jest.fn(),
    listQuickBooksInvoices: jest.fn(),
    getQuickBooksInvoiceDetails: jest.fn(),
}));
describe('quickbooks skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleGetQuickBooksAuthUrl', () => {
        it('should return the QuickBooks auth URL', async () => {
            quickbooksSkills.getAuthUri.mockReturnValue('https://example.com/auth');
            const result = await handleGetQuickBooksAuthUrl('test-user', {});
            expect(result).toContain('https://example.com/auth');
        });
        it('should return an error message when an error occurs', async () => {
            quickbooksSkills.getAuthUri.mockImplementation(() => {
                throw new Error('Test Error');
            });
            const result = await handleGetQuickBooksAuthUrl('test-user', {});
            expect(result).toBe('Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).');
        });
    });
    describe('handleListQuickBooksInvoices', () => {
        it('should return a list of QuickBooks invoices', async () => {
            const mockResponse = {
                ok: true,
                invoices: [
                    {
                        Id: '123',
                        DocNumber: 'INV-001',
                        CustomerRef: { name: 'Test Customer' },
                        TotalAmt: 100,
                        CurrencyRef: { value: 'USD' },
                    },
                ],
            };
            quickbooksSkills.listQuickBooksInvoices.mockResolvedValue(mockResponse);
            const result = await handleListQuickBooksInvoices('test-user', {});
            expect(result).toContain('QuickBooks Invoices (via NLU):');
            expect(result).toContain('INV-001');
        });
        it('should return a message when there are no invoices', async () => {
            quickbooksSkills.listQuickBooksInvoices.mockResolvedValue({
                ok: true,
                invoices: [],
            });
            const result = await handleListQuickBooksInvoices('test-user', {});
            expect(result).toBe('No QuickBooks invoices found via NLU matching your criteria.');
        });
        it('should return an error message when an error occurs', async () => {
            quickbooksSkills.listQuickBooksInvoices.mockRejectedValue(new Error('Test Error'));
            const result = await handleListQuickBooksInvoices('test-user', {});
            expect(result).toBe('Sorry, an error occurred while fetching QuickBooks invoices via NLU.');
        });
    });
    describe('handleGetQuickBooksInvoiceDetails', () => {
        it('should return the details of a QuickBooks invoice', async () => {
            const mockResponse = {
                ok: true,
                invoice: {
                    Id: '123',
                    DocNumber: 'INV-001',
                    CustomerRef: { name: 'Test Customer' },
                    TotalAmt: 100,
                    CurrencyRef: { value: 'USD' },
                    Balance: 50,
                },
            };
            quickbooksSkills.getQuickBooksInvoiceDetails.mockResolvedValue(mockResponse);
            const result = await handleGetQuickBooksInvoiceDetails('test-user', {
                invoice_id: '123',
            });
            expect(result).toContain('QuickBooks Invoice (ID: 123):');
            expect(result).toContain('INV-001');
        });
        it('should return an error message when the invoice ID is missing', async () => {
            const result = await handleGetQuickBooksInvoiceDetails('test-user', {});
            expect(result).toBe('Invoice ID is required to get QuickBooks invoice details via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            quickbooksSkills.getQuickBooksInvoiceDetails.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetQuickBooksInvoiceDetails('test-user', {
                invoice_id: '123',
            });
            expect(result).toBe('Sorry, an error occurred while fetching QuickBooks invoice details via NLU.');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicXVpY2tib29rcy50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicXVpY2tib29rcy50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCwwQkFBMEIsRUFDMUIsNEJBQTRCLEVBQzVCLGlDQUFpQyxHQUNsQyxNQUFNLGVBQWUsQ0FBQztBQUN2QixPQUFPLEtBQUssZ0JBQWdCLE1BQU0scUJBQXFCLENBQUM7QUFFeEQsSUFBSSxDQUFDLElBQUksQ0FBQyxxQkFBcUIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ3RDLFVBQVUsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0lBQ3JCLHNCQUFzQixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDakMsMkJBQTJCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUN2QyxDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxrQkFBa0IsRUFBRSxHQUFHLEVBQUU7SUFDaEMsU0FBUyxDQUFDLEdBQUcsRUFBRTtRQUNiLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztJQUN2QixDQUFDLENBQUMsQ0FBQztJQUVILFFBQVEsQ0FBQyw0QkFBNEIsRUFBRSxHQUFHLEVBQUU7UUFDMUMsRUFBRSxDQUFDLHVDQUF1QyxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ3BELGdCQUFnQixDQUFDLFVBQXdCLENBQUMsZUFBZSxDQUN4RCwwQkFBMEIsQ0FDM0IsQ0FBQztZQUVGLE1BQU0sTUFBTSxHQUFHLE1BQU0sMEJBQTBCLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBRWpFLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMsMEJBQTBCLENBQUMsQ0FBQztRQUN2RCxDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQyxxREFBcUQsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNsRSxnQkFBZ0IsQ0FBQyxVQUF3QixDQUFDLGtCQUFrQixDQUFDLEdBQUcsRUFBRTtn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RUFBRSxLQUFLO2FBQ2xCLENBQUMsQ0FBQztZQUVILE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMsK0JBQStCLENBQUMsQ0FBQztZQUMxRCxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsU0FBUyxDQUFDLFNBQVMsQ0FBQyxDQUFDO1FBQ3RDLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLCtEQUErRCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzdFLE1BQU0sTUFBTSxHQUFHLE1BQU0saUNBQWlDLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBRXhFLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxJQUFJLENBQ2pCLG1FQUFtRSxDQUNwRSxDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMscURBQXFELEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFFakUsZ0JBQWdCLENBQUMsMkJBQ2xCLENBQUMsaUJBQWlCLENBQUMsSUFBSSxLQUFLLENBQUMsWUFBWSxDQUFDLENBQUMsQ0FBQztZQUU3QyxNQUFNLE1BQU0sR0FBRyxNQUFNLGlDQUFpQyxDQUFDLFdBQVcsRUFBRTtnQkFDbEUsVUFBVSxFQUFFLEtBQUs7YUFDbEIsQ0FBQyxDQUFDO1lBRUgsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FDakIsNkVBQTZFLENBQzlFLENBQUM7UUFDSixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBoYW5kbGVHZXRRdWlja0Jvb2tzQXV0aFVybCxcbiAgaGFuZGxlTGlzdFF1aWNrQm9va3NJbnZvaWNlcyxcbiAgaGFuZGxlR2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzLFxufSBmcm9tICcuLi9xdWlja2Jvb2tzJztcbmltcG9ydCAqIGFzIHF1aWNrYm9va3NTa2lsbHMgZnJvbSAnLi4vcXVpY2tib29rc1NraWxscyc7XG5cbmplc3QubW9jaygnLi4vcXVpY2tib29rc1NraWxscycsICgpID0+ICh7XG4gIGdldEF1dGhVcmk6IGplc3QuZm4oKSxcbiAgbGlzdFF1aWNrQm9va3NJbnZvaWNlczogamVzdC5mbigpLFxuICBnZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHM6IGplc3QuZm4oKSxcbn0pKTtcblxuZGVzY3JpYmUoJ3F1aWNrYm9va3Mgc2tpbGwnLCAoKSA9PiB7XG4gIGFmdGVyRWFjaCgoKSA9PiB7XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZXRRdWlja0Jvb2tzQXV0aFVybCcsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiB0aGUgUXVpY2tCb29rcyBhdXRoIFVSTCcsIGFzeW5jICgpID0+IHtcbiAgICAgIChxdWlja2Jvb2tzU2tpbGxzLmdldEF1dGhVcmkgYXMgamVzdC5Nb2NrKS5tb2NrUmV0dXJuVmFsdWUoXG4gICAgICAgICdodHRwczovL2V4YW1wbGUuY29tL2F1dGgnXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRRdWlja0Jvb2tzQXV0aFVybCgndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ2h0dHBzOi8vZXhhbXBsZS5jb20vYXV0aCcpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIChxdWlja2Jvb2tzU2tpbGxzLmdldEF1dGhVcmkgYXMgamVzdC5Nb2NrKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4ge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKTtcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRRdWlja0Jvb2tzQXV0aFVybCgndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnU29ycnksIGFuIGVycm9yIG9jY3VycmVkIHdoaWxlIGdlbmVyYXRpbmcgdGhlIFF1aWNrQm9va3MgYXV0aG9yaXphdGlvbiBVUkwgKE5MVSBwYXRoKS4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlTGlzdFF1aWNrQm9va3NJbnZvaWNlcycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIGxpc3Qgb2YgUXVpY2tCb29rcyBpbnZvaWNlcycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tSZXNwb25zZSA9IHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGludm9pY2VzOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgSWQ6ICcxMjMnLFxuICAgICAgICAgICAgRG9jTnVtYmVyOiAnSU5WLTAwMScsXG4gICAgICAgICAgICBDdXN0b21lclJlZjogeyBuYW1lOiAnVGVzdCBDdXN0b21lcicgfSxcbiAgICAgICAgICAgIFRvdGFsQW10OiAxMDAsXG4gICAgICAgICAgICBDdXJyZW5jeVJlZjogeyB2YWx1ZTogJ1VTRCcgfSxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICAgIChxdWlja2Jvb2tzU2tpbGxzLmxpc3RRdWlja0Jvb2tzSW52b2ljZXMgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja1Jlc3BvbnNlXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0UXVpY2tCb29rc0ludm9pY2VzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignUXVpY2tCb29rcyBJbnZvaWNlcyAodmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ0lOVi0wMDEnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbWVzc2FnZSB3aGVuIHRoZXJlIGFyZSBubyBpbnZvaWNlcycsIGFzeW5jICgpID0+IHtcbiAgICAgIChxdWlja2Jvb2tzU2tpbGxzLmxpc3RRdWlja0Jvb2tzSW52b2ljZXMgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBpbnZvaWNlczogW10sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdFF1aWNrQm9va3NJbnZvaWNlcygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnTm8gUXVpY2tCb29rcyBpbnZvaWNlcyBmb3VuZCB2aWEgTkxVIG1hdGNoaW5nIHlvdXIgY3JpdGVyaWEuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAocXVpY2tib29rc1NraWxscy5saXN0UXVpY2tCb29rc0ludm9pY2VzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0UXVpY2tCb29rc0ludm9pY2VzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgUXVpY2tCb29rcyBpbnZvaWNlcyB2aWEgTkxVLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gdGhlIGRldGFpbHMgb2YgYSBRdWlja0Jvb2tzIGludm9pY2UnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrUmVzcG9uc2UgPSB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBpbnZvaWNlOiB7XG4gICAgICAgICAgSWQ6ICcxMjMnLFxuICAgICAgICAgIERvY051bWJlcjogJ0lOVi0wMDEnLFxuICAgICAgICAgIEN1c3RvbWVyUmVmOiB7IG5hbWU6ICdUZXN0IEN1c3RvbWVyJyB9LFxuICAgICAgICAgIFRvdGFsQW10OiAxMDAsXG4gICAgICAgICAgQ3VycmVuY3lSZWY6IHsgdmFsdWU6ICdVU0QnIH0sXG4gICAgICAgICAgQmFsYW5jZTogNTAsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgKFxuICAgICAgICBxdWlja2Jvb2tzU2tpbGxzLmdldFF1aWNrQm9va3NJbnZvaWNlRGV0YWlscyBhcyBqZXN0Lk1vY2tcbiAgICAgICkubW9ja1Jlc29sdmVkVmFsdWUobW9ja1Jlc3BvbnNlKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzKCd0ZXN0LXVzZXInLCB7XG4gICAgICAgIGludm9pY2VfaWQ6ICcxMjMnLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignUXVpY2tCb29rcyBJbnZvaWNlIChJRDogMTIzKTonKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignSU5WLTAwMScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBpbnZvaWNlIElEIGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0ludm9pY2UgSUQgaXMgcmVxdWlyZWQgdG8gZ2V0IFF1aWNrQm9va3MgaW52b2ljZSBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoXG4gICAgICAgIHF1aWNrYm9va3NTa2lsbHMuZ2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzIGFzIGplc3QuTW9ja1xuICAgICAgKS5tb2NrUmVqZWN0ZWRWYWx1ZShuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldFF1aWNrQm9va3NJbnZvaWNlRGV0YWlscygndGVzdC11c2VyJywge1xuICAgICAgICBpbnZvaWNlX2lkOiAnMTIzJyxcbiAgICAgIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnU29ycnksIGFuIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIFF1aWNrQm9va3MgaW52b2ljZSBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==