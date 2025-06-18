import * as msEmailSkills from './microsoftEmailSkills';
import { Email, ReadEmailResponse, SendEmailResponse, EmailDetails } from '../types';
import got from 'got';
import * as tokenUtils from '../_libs/token-utils';
import * as constants from '../_libs/constants'; // Though constants are mocked globally, good to show dependency

// Mocks
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

jest.mock('../_libs/token-utils', () => ({
    getAtomMicrosoftGraphTokens: jest.fn(),
    saveAtomMicrosoftGraphTokens: jest.fn(),
    deleteAtomMicrosoftGraphTokens: jest.fn(),
}));

jest.mock('../_libs/constants', () => ({
    ATOM_MSGRAPH_CLIENT_ID: 'test_ms_client_id_email_skill',
    ATOM_MSGRAPH_CLIENT_SECRET: 'test_ms_client_secret_email_skill',
    ATOM_MSGRAPH_TENANT_ID: 'common_tenant_email_skill',
    MSGRAPH_OAUTH_AUTHORITY_BASE: 'https://login.microsoftonline.com/',
    MSGRAPH_API_SCOPES: ['User.Read', 'Mail.ReadWrite', 'Mail.Send', 'offline_access'],
    ATOM_MSGRAPH_REDIRECT_URI: 'http://localhost/ms_callback_email_skill',
}));

const mockedGetMsGraphTokens = tokenUtils.getAtomMicrosoftGraphTokens as jest.Mock;
const mockedSaveMsGraphTokens = tokenUtils.saveAtomMicrosoftGraphTokens as jest.Mock;
const mockedDeleteMsGraphTokens = tokenUtils.deleteAtomMicrosoftGraphTokens as jest.Mock;

describe('Microsoft Email Skills with Graph API Mocks', () => {
    const mockUserId = 'test-user-ms-email-skill';
    const initialMockTokenSet = {
        access_token: 'valid_ms_email_access_token',
        refresh_token: 'valid_ms_email_refresh_token',
        expiry_date: Date.now() + 3600000,
        appEmail: 'user.ms@example.com'
    };
    let consoleErrorSpy: jest.SpyInstance;
    let consoleLogSpy: jest.SpyInstance;

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    });
    afterEach(() => {
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });

    describe('listRecentEmailsMicrosoft', () => {
        it('should return empty array if no tokens found', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(null);
            const emails = await msEmailSkills.listRecentEmailsMicrosoft(mockUserId, 5);
            expect(emails).toEqual([]);
        });

        it('should fetch and map emails successfully', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const mockGraphResponse = {
                body: {
                    value: [
                        { id: 'ms_email1', subject: 'MS Email 1', bodyPreview: 'Preview 1', from: {emailAddress: {address: 'f1@ms.com', name: 'F1'}}, toRecipients: [{emailAddress:{address:'t1@ms.com',name:'T1'}}], receivedDateTime: new Date().toISOString(), isRead: false, webLink: 'ms_email_link1' },
                        { id: 'ms_email2', subject: 'MS Email 2', bodyPreview: 'Preview 2', from: {emailAddress: {address: 'f2@ms.com', name: 'F2'}}, receivedDateTime: new Date().toISOString(), isRead: true },
                    ]
                }
            };
            mockedGot.get.mockResolvedValue(mockGraphResponse as any);
            const emails = await msEmailSkills.listRecentEmailsMicrosoft(mockUserId, 2);
            expect(mockedGot.get).toHaveBeenCalledWith(expect.stringContaining('https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages'), expect.any(Object));
            expect(emails.length).toBe(2);
            expect(emails[0].subject).toBe('MS Email 1');
            expect(emails[0].read).toBe(false);
            expect(emails[0].sender).toBe('F1 <f1@ms.com>');
        });

        it('should attempt token refresh on 401 and retry', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            mockedGot.get.mockRejectedValueOnce({ response: { statusCode: 401 } } as any); // First call fails
            mockedGot.post.mockResolvedValueOnce({ body: { access_token: 'refreshed_token', expires_in: 3600 } } as any); // Refresh succeeds
            mockedGot.get.mockResolvedValueOnce({ body: { value: [{id: 'refreshed_email', subject: 'After Refresh'}]} } as any); // Second call succeeds

            const emails = await msEmailSkills.listRecentEmailsMicrosoft(mockUserId, 1);
            expect(mockedSaveMsGraphTokens).toHaveBeenCalled();
            expect(emails.length).toBe(1);
            expect(emails[0].subject).toBe('After Refresh');
        });
    });

    describe('readEmailMicrosoft', () => {
        const emailId = 'msEmailId1';
        it('should return auth error if no tokens', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(null);
            const result = await msEmailSkills.readEmailMicrosoft(mockUserId, emailId);
            expect(result.success).toBe(false);
        });

        it('should fetch, parse, and mark email as read', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const mockFullEmail = {
                id: emailId, subject: 'Full MS Subject', from: {emailAddress:{address:'f_full@ms.com'}}, toRecipients:[], receivedDateTime: new Date().toISOString(), isRead: false, webLink: 'link',
                body: { contentType: 'text', content: 'Full body text' }
            };
            mockedGot.get.mockResolvedValue({ body: mockFullEmail } as any);
            mockedGot.patch.mockResolvedValue({} as any); // For mark as read

            const result = await msEmailSkills.readEmailMicrosoft(mockUserId, emailId);
            expect(mockedGot.get).toHaveBeenCalledWith(expect.stringContaining(`/me/messages/${emailId}`), expect.any(Object));
            expect(mockedGot.patch).toHaveBeenCalledWith(expect.stringContaining(`/me/messages/${emailId}`), expect.objectContaining({ json: { isRead: true } }));
            expect(result.success).toBe(true);
            expect(result.email?.body).toBe('Full body text');
            expect(result.email?.read).toBe(true);
        });
    });

    describe('sendEmailMicrosoft', () => {
        const emailDetails: EmailDetails = { to: 'dest@example.com', subject: 'MS Test Send', body: 'Body from MS' };
        it('should return auth error if no tokens', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(null);
            const result = await msEmailSkills.sendEmailMicrosoft(mockUserId, emailDetails);
            expect(result.success).toBe(false);
        });

        it('should construct message and send it', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            mockedGot.post.mockResolvedValue({ statusCode: 202 } as any); // sendMail returns 202

            const result = await msEmailSkills.sendEmailMicrosoft(mockUserId, emailDetails);
            expect(mockedGot.post).toHaveBeenCalledWith('https://graph.microsoft.com/v1.0/me/sendMail', expect.any(Object));
            const requestBody = (mockedGot.post.mock.calls[0][1] as any).json;
            expect(requestBody.message.subject).toBe(emailDetails.subject);
            expect(requestBody.message.toRecipients[0].emailAddress.address).toBe(emailDetails.to);
            expect(result.success).toBe(true);
            expect(result.message).toContain('Email sent successfully via Microsoft Graph.');
        });
    });
});
