import {
  listQuickBooksInvoices,
  getQuickBooksInvoiceDetails,
  getAuthUri,
  resetOAuthClientInstanceCache, // Import the reset function
} from './quickbooksSkills';
import OAuthClient from 'intuit-oauth';
import QuickBooks from 'node-quickbooks';
import fs from 'fs/promises'; // Import the actual fs.promises for mocking
import path from 'path';
import * as constants from '../_libs/constants';
import { QuickBooksAuthTokens, QuickBooksInvoice } from '../types';

// Mock external dependencies
jest.mock('intuit-oauth');
jest.mock('node-quickbooks');
jest.mock('fs/promises'); // Mock fs.promises

// Setup mock functions for the mocked classes
const MockedOAuthClient = OAuthClient as jest.MockedClass<typeof OAuthClient>;
const mockGenerateAuthUri = jest.fn();
const mockRefreshUsingToken = jest.fn();
MockedOAuthClient.mockImplementation(
  () =>
    ({
      generateAuthUri: mockGenerateAuthUri,
      refreshUsingToken: mockRefreshUsingToken,
    }) as any
);

const MockedQuickBooks = QuickBooks as jest.MockedClass<typeof QuickBooks>;
const mockFindInvoices = jest.fn();
const mockGetInvoice = jest.fn();
MockedQuickBooks.mockImplementation(
  () =>
    ({
      findInvoices: mockFindInvoices,
      getInvoice: mockGetInvoice,
    }) as any
);

const mockedFs = fs as jest.Mocked<typeof fs>;

jest.mock('../_libs/constants', () => ({
  ATOM_QB_CLIENT_ID: 'test_qb_client_id',
  ATOM_QB_CLIENT_SECRET: 'test_qb_client_secret',
  ATOM_QB_ENVIRONMENT: 'sandbox',
  ATOM_QB_REDIRECT_URI: 'https://test.com/callback',
  ATOM_QB_TOKEN_FILE_PATH: './test_qb_tokens.json',
  ATOM_QB_SCOPES: ['com.intuit.quickbooks.accounting', 'openid'],
}));

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

describe('quickbooksSkills', () => {
  const validTokenData: QuickBooksAuthTokens = {
    accessToken: 'valid_access_token',
    refreshToken: 'valid_refresh_token',
    realmId: 'test_realm_id',
    accessTokenExpiresAt: Date.now() + 3600 * 1000, // Expires in 1 hour
    refreshTokenExpiresAt: Date.now() + 86400 * 1000 * 30, // Expires in 30 days
    createdAt: Date.now(),
  };

  beforeEach(() => {
    mockGenerateAuthUri.mockReset();
    mockRefreshUsingToken.mockReset();
    mockFindInvoices.mockReset();
    mockGetInvoice.mockReset();
    mockedFs.readFile.mockReset();
    mockedFs.writeFile.mockReset();
    mockedFs.unlink.mockReset();
    MockedOAuthClient.mockClear();
    MockedQuickBooks.mockClear();

    resetOAuthClientInstanceCache(); // Call the exported reset function

    // Set default mock values for constants (can be overridden in tests if needed)
    Object.defineProperty(constants, 'ATOM_QB_CLIENT_ID', {
      value: 'test_qb_client_id',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_QB_CLIENT_SECRET', {
      value: 'test_qb_client_secret',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_QB_ENVIRONMENT', {
      value: 'sandbox',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_QB_REDIRECT_URI', {
      value: 'https://test.com/callback',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_QB_TOKEN_FILE_PATH', {
      value: './test_qb_tokens.json',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_QB_SCOPES', {
      value: ['com.intuit.quickbooks.accounting', 'openid'],
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

  describe('Token Management', () => {
    it('should return error if token file does not exist initially for listInvoices', async () => {
      mockedFs.readFile.mockRejectedValueOnce({
        code: 'ENOENT',
      } as NodeJS.ErrnoException);
      const result = await listQuickBooksInvoices();
      expect(result.ok).toBe(false);
      expect(result.error).toContain(
        'QuickBooks client could not be initialized'
      ); // Error from getQboClient due to no tokens
      expect(consoleLogSpy).toHaveBeenCalledWith(
        'No QuickBooks tokens found. Please authorize the application first using the /api/atom/auth/qb/connect endpoint or by calling getAuthUri() and completing flow.'
      );
    });

    it('should load valid, non-expired tokens and make API call for listInvoices', async () => {
      mockedFs.readFile.mockResolvedValueOnce(JSON.stringify(validTokenData));
      mockFindInvoices.mockImplementation((params, callback) =>
        callback(null, { QueryResponse: { Invoice: [], totalCount: 0 } })
      );

      await listQuickBooksInvoices();
      expect(mockedFs.readFile).toHaveBeenCalledWith(
        path.resolve(constants.ATOM_QB_TOKEN_FILE_PATH),
        'utf-8'
      );
      expect(mockFindInvoices).toHaveBeenCalledTimes(1);
      expect(mockRefreshUsingToken).not.toHaveBeenCalled();
      expect(MockedQuickBooks).toHaveBeenCalledWith(
        // Check if QBO client was initialized with correct token
        constants.ATOM_QB_CLIENT_ID,
        constants.ATOM_QB_CLIENT_SECRET,
        validTokenData.accessToken,
        false,
        validTokenData.realmId,
        true,
        true,
        null,
        '2.0',
        validTokenData.refreshToken
      );
    });

    it('should refresh expired access token, save, and use new token for listInvoices', async () => {
      const expiredTokenData = {
        ...validTokenData,
        accessTokenExpiresAt: Date.now() - 1000,
      };
      const refreshedOAuthData = {
        access_token: 'new_access_token_from_refresh',
        refresh_token: 'new_refresh_token_from_refresh',
        realmId: 'test_realm_id', // Should be same realmId
        expires_in: 3600, // 1 hour in seconds
        x_refresh_token_expires_in: 86400 * 60, // 60 days in seconds
      };
      mockedFs.readFile.mockResolvedValueOnce(JSON.stringify(expiredTokenData)); // Initial load (expired)
      mockRefreshUsingToken.mockResolvedValueOnce({
        getJson: () => refreshedOAuthData,
      } as any);
      mockedFs.writeFile.mockResolvedValueOnce(undefined); // Mock successful save
      // This mock is for the loadTokens *after* successful refresh and save
      mockedFs.readFile.mockResolvedValueOnce(
        JSON.stringify({
          ...validTokenData, // Keep other valid parts
          accessToken: refreshedOAuthData.access_token,
          refreshToken: refreshedOAuthData.refresh_token,
          accessTokenExpiresAt:
            Date.now() + refreshedOAuthData.expires_in * 1000 - 1000, // Simulate slight delay
          refreshTokenExpiresAt:
            Date.now() +
            refreshedOAuthData.x_refresh_token_expires_in * 1000 -
            1000,
        })
      );

      mockFindInvoices.mockImplementation((params, callback) =>
        callback(null, { QueryResponse: { Invoice: [], totalCount: 0 } })
      );
      await listQuickBooksInvoices();

      expect(mockRefreshUsingToken).toHaveBeenCalledWith(
        expiredTokenData.refreshToken
      );
      expect(mockedFs.writeFile).toHaveBeenCalledTimes(1);
      expect(mockFindInvoices).toHaveBeenCalledTimes(1);
      // Check that QuickBooks was initialized with the new token
      expect(MockedQuickBooks.mock.calls[0][2]).toBe(
        refreshedOAuthData.access_token
      );
    });

    it('should handle refresh failure and delete token file for listInvoices', async () => {
      const expiredTokenData = {
        ...validTokenData,
        accessTokenExpiresAt: Date.now() - 1000,
      };
      mockedFs.readFile.mockResolvedValueOnce(JSON.stringify(expiredTokenData));
      mockRefreshUsingToken.mockRejectedValueOnce(
        new Error('Refresh Token Failed Miserably')
      );
      mockedFs.unlink.mockResolvedValueOnce(undefined); // Mock successful deletion

      const result = await listQuickBooksInvoices();
      expect(result.ok).toBe(false);
      expect(result.error).toContain(
        'QuickBooks client could not be initialized'
      );
      expect(mockedFs.unlink).toHaveBeenCalledWith(
        path.resolve(constants.ATOM_QB_TOKEN_FILE_PATH)
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'QuickBooks token refresh failed:',
        'Refresh Token Failed Miserably'
      );
    });
  });

  describe('getAuthUri', () => {
    it('should generate and return the authorization URI', () => {
      mockGenerateAuthUri.mockReturnValue('test_auth_uri_from_sdk');
      const uri = getAuthUri();
      expect(uri).toBe('test_auth_uri_from_sdk');
      expect(MockedOAuthClient).toHaveBeenCalledTimes(1);
      expect(mockGenerateAuthUri).toHaveBeenCalledWith({
        scope: constants.ATOM_QB_SCOPES,
        state: 'atom_qbo_init_oauth',
      });
    });
    it('should return null if OAuth client constants are missing for getAuthUri', () => {
      Object.defineProperty(constants, 'ATOM_QB_CLIENT_ID', { value: '' });
      const uri = getAuthUri();
      expect(uri).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'QuickBooks OAuth client credentials for Auth URI generation not configured.'
      );
    });
  });

  describe('listQuickBooksInvoices', () => {
    beforeEach(() => {
      // Ensure valid tokens for these tests
      mockedFs.readFile.mockResolvedValue(JSON.stringify(validTokenData));
    });

    it('should list invoices successfully and map them', async () => {
      const mockQboInvoice = {
        Id: '1',
        DocNumber: 'INV001',
        TotalAmt: 100,
        CustomerRef: { value: 'cust1', name: 'Cust Name' },
      };
      mockFindInvoices.mockImplementation((params, callback) =>
        callback(null, {
          QueryResponse: {
            Invoice: [mockQboInvoice],
            totalCount: 1,
            MaxResults: 10,
            StartPosition: 1,
          },
        })
      );

      const result = await listQuickBooksInvoices({
        limit: 1,
        customerId: 'cust1',
      });
      expect(result.ok).toBe(true);
      expect(result.invoices).toHaveLength(1);
      expect(result.invoices![0].Id).toBe('1');
      expect(result.invoices![0].DocNumber).toBe('INV001');
      expect(result.queryResponse?.totalCount).toBe(1);
      expect(mockFindInvoices).toHaveBeenCalledWith(
        expect.objectContaining({
          filter: { CustomerRef: 'cust1' },
          limit: 1,
          offset: 1,
        }),
        expect.any(Function)
      );
    });

    it('should handle QBO API error when listing invoices', async () => {
      const qboError = {
        Fault: {
          Error: [
            { Message: 'QBO List Error', Detail: 'Some detail', code: '1000' },
          ],
          type: 'ValidationFault',
        },
        time: new Date().toISOString(),
      };
      mockFindInvoices.mockImplementation((params, callback) =>
        callback(qboError, null)
      );

      const result = await listQuickBooksInvoices();
      expect(result.ok).toBe(false);
      expect(result.error).toBe('QBO List Error');
    });
  });

  describe('getQuickBooksInvoiceDetails', () => {
    beforeEach(() => {
      // Ensure valid tokens
      mockedFs.readFile.mockResolvedValue(JSON.stringify(validTokenData));
    });

    it('should get invoice details successfully and map them', async () => {
      const mockDetailedQboInvoice = {
        Id: '2',
        DocNumber: 'INV002',
        TotalAmt: 250,
        Balance: 50,
        BillEmail: { Address: 'test@co.com' },
      };
      mockGetInvoice.mockImplementation((id, callback) =>
        callback(null, mockDetailedQboInvoice)
      );

      const result = await getQuickBooksInvoiceDetails('2');
      expect(result.ok).toBe(true);
      expect(result.invoice?.Id).toBe('2');
      expect(result.invoice?.TotalAmt).toBe(250);
      expect(result.invoice?.BillEmail?.Address).toBe('test@co.com');
      expect(mockGetInvoice).toHaveBeenCalledWith('2', expect.any(Function));
    });

    it('should handle "not found" error (6240) from QBO for getInvoice', async () => {
      const qboNotFoundError = {
        Fault: {
          Error: [{ Message: 'Object Not Found', code: '6240' }],
          type: 'ValidationFault',
        },
        time: new Date().toISOString(),
      };
      mockGetInvoice.mockImplementation((id, callback) =>
        callback(qboNotFoundError, null)
      );

      const result = await getQuickBooksInvoiceDetails('nonexistent_id');
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Invoice with ID nonexistent_id not found.');
    });

    it('should return error if invoiceId is missing for getInvoiceDetails', async () => {
      const result = await getQuickBooksInvoiceDetails('');
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Invoice ID is required.');
      expect(mockGetInvoice).not.toHaveBeenCalled();
    });
  });
});
