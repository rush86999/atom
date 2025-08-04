import {
  handleGetQuickBooksAuthUrl,
  handleListQuickBooksInvoices,
  handleGetQuickBooksInvoiceDetails,
} from '../quickbooks';
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
      (quickbooksSkills.getAuthUri as jest.Mock).mockReturnValue(
        'https://example.com/auth'
      );

      const result = await handleGetQuickBooksAuthUrl('test-user', {});

      expect(result).toContain('https://example.com/auth');
    });

    it('should return an error message when an error occurs', async () => {
      (quickbooksSkills.getAuthUri as jest.Mock).mockImplementation(() => {
        throw new Error('Test Error');
      });

      const result = await handleGetQuickBooksAuthUrl('test-user', {});

      expect(result).toBe(
        'Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).'
      );
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
      (quickbooksSkills.listQuickBooksInvoices as jest.Mock).mockResolvedValue(
        mockResponse
      );

      const result = await handleListQuickBooksInvoices('test-user', {});

      expect(result).toContain('QuickBooks Invoices (via NLU):');
      expect(result).toContain('INV-001');
    });

    it('should return a message when there are no invoices', async () => {
      (quickbooksSkills.listQuickBooksInvoices as jest.Mock).mockResolvedValue({
        ok: true,
        invoices: [],
      });

      const result = await handleListQuickBooksInvoices('test-user', {});

      expect(result).toBe(
        'No QuickBooks invoices found via NLU matching your criteria.'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (quickbooksSkills.listQuickBooksInvoices as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleListQuickBooksInvoices('test-user', {});

      expect(result).toBe(
        'Sorry, an error occurred while fetching QuickBooks invoices via NLU.'
      );
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
      (
        quickbooksSkills.getQuickBooksInvoiceDetails as jest.Mock
      ).mockResolvedValue(mockResponse);

      const result = await handleGetQuickBooksInvoiceDetails('test-user', {
        invoice_id: '123',
      });

      expect(result).toContain('QuickBooks Invoice (ID: 123):');
      expect(result).toContain('INV-001');
    });

    it('should return an error message when the invoice ID is missing', async () => {
      const result = await handleGetQuickBooksInvoiceDetails('test-user', {});

      expect(result).toBe(
        'Invoice ID is required to get QuickBooks invoice details via NLU.'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (
        quickbooksSkills.getQuickBooksInvoiceDetails as jest.Mock
      ).mockRejectedValue(new Error('Test Error'));

      const result = await handleGetQuickBooksInvoiceDetails('test-user', {
        invoice_id: '123',
      });

      expect(result).toBe(
        'Sorry, an error occurred while fetching QuickBooks invoice details via NLU.'
      );
    });
  });
});
