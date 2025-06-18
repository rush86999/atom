import * as emailSkills from './emailSkills';
import { Email, ReadEmailResponse, SendEmailResponse, EmailDetails } from '../types';
import { google, gmail_v1 } from 'googleapis';
import * as tokenUtils from '../_libs/token-utils';
import * as constants from '../_libs/constants';

// Mocks
jest.mock('googleapis', () => {
    const mockMessages = {
        list: jest.fn(),
        get: jest.fn(),
        send: jest.fn(),
        modify: jest.fn(),
    };
    const mockOAuth2Instance = {
        setCredentials: jest.fn(),
        on: jest.fn(), // Mock the .on method for token refresh
    };
    return {
        google: {
            auth: {
                OAuth2: jest.fn().mockImplementation(() => mockOAuth2Instance),
            },
            gmail: jest.fn(() => ({
                users: {
                    messages: mockMessages,
                },
            })),
            // For google.oauth2('v2').userinfo.get() - this is not used in emailSkills directly
        },
        gmail_v1: { Schema$Message: {} }
    };
});

jest.mock('../_libs/token-utils', () => ({
    getAtomGmailTokens: jest.fn(),
    saveAtomGmailTokens: jest.fn(),
}));

jest.mock('../_libs/constants', () => ({
    ATOM_GMAIL_CLIENT_ID: 'test_gmail_client_id',
    ATOM_GMAIL_CLIENT_SECRET: 'test_gmail_client_secret',
}));

const mockedGetAtomGmailTokens = tokenUtils.getAtomGmailTokens as jest.Mock;
const mockedSaveAtomGmailTokens = tokenUtils.saveAtomGmailTokens as jest.Mock;

// Get the mocked instance of OAuth2 client to access its 'on' method for specific test.
const MockedOAuth2Client = google.auth.OAuth2 as jest.MockedClass<typeof google.auth.OAuth2>;
// We will get the mock 'on' from the instance created in each test, if needed.

const mockedGmailMessages = google.gmail({version: 'v1'}).users.messages as jest.Mocked<gmail_v1.Resource$Users$Messages>;


describe('Email Skills with Gmail API Mocks', () => {
    const mockUserId = 'test-user-email-skill';
    const mockTokenSet = {
        access_token: 'valid_gmail_access_token',
        refresh_token: 'valid_gmail_refresh_token',
        expiry_date: Date.now() + 3600000,
        scope: 'some_gmail_scope',
        token_type: 'Bearer',
        appEmail: 'user@example.com'
    };
    let consoleErrorSpy: jest.SpyInstance;

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
         // Reset the 'on' mock for each test on the class prototype if needed, or instance.
         // For simplicity, we assume a new OAuth2 instance is created per skill call.
         (MockedOAuth2Client.mock.results[0]?.value?.on as jest.Mock)?.mockClear();

    });
    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    describe('listRecentEmails', () => {
        it('should return empty array if no tokens are found', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(null);
            const emails = await emailSkills.listRecentEmails(mockUserId, 5);
            expect(emails).toEqual([]);
            expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('No valid Gmail tokens'));
        });

        it('should fetch and map emails successfully', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.list.mockResolvedValue({
                data: { messages: [{ id: 'msg1' }, { id: 'msg2' }], resultSizeEstimate: 2 },
            }as any);

            const mockMsg1Data = {
                id: 'msg1', snippet: 'Snippet 1', internalDate: String(Date.now()), labelIds: ['INBOX', 'UNREAD'],
                payload: { headers: [{name: 'Subject', value: 'S1'}, {name: 'From', value: 'F1'}, {name: 'To', value: 'T1'}, {name: 'Date', value: new Date().toUTCString()}] }
            };
            const mockMsg2Data = {
                id: 'msg2', snippet: 'Snippet 2', internalDate: String(Date.now() - 10000), labelIds: ['INBOX'],
                payload: { headers: [{name: 'Subject', value: 'S2'}, {name: 'From', value: 'F2'}, {name: 'To', value: 'T2'}, {name: 'Date', value: new Date(Date.now() - 10000).toUTCString()}] }
            };
            mockedGmailMessages.get
                .mockResolvedValueOnce({ data: mockMsg1Data } as any)
                .mockResolvedValueOnce({ data: mockMsg2Data } as any);

            const emails = await emailSkills.listRecentEmails(mockUserId, 2);
            expect(mockedGmailMessages.list).toHaveBeenCalledWith({ userId: 'me', maxResults: 2, q: 'is:inbox' });
            expect(mockedGmailMessages.get).toHaveBeenCalledTimes(2);
            expect(emails.length).toBe(2);
            expect(emails[0].subject).toBe('S1');
            expect(emails[0].read).toBe(false);
            expect(emails[1].subject).toBe('S2');
            expect(emails[1].read).toBe(true);
        });

        it('should return empty array on API error', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.list.mockRejectedValue(new Error("Gmail API list error"));
            const emails = await emailSkills.listRecentEmails(mockUserId, 5);
            expect(emails).toEqual([]);
            expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error listing Gmail messages'), "Gmail API list error");
        });

        it('should save refreshed tokens if "tokens" event is emitted during listRecentEmails', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.list.mockResolvedValue({ data: { messages: [] } } as any); // API call itself is fine

            // Capture the 'on' call from the OAuth2 instance created within listRecentEmails
            let tokenListener: (tokens: any) => void = () => {};
            const mockOAuth2Instance = new (google.auth.OAuth2)();
             (mockOAuth2Instance.on as jest.Mock).mockImplementation((event, listener) => {
              if (event === 'tokens') {
                tokenListener = listener;
              }
            });
            (google.auth.OAuth2 as jest.Mock).mockReturnValue(mockOAuth2Instance); // Ensure new instances use this mock

            await emailSkills.listRecentEmails(mockUserId, 5); // This will set up the listener

            const refreshedTokensFromEvent = { access_token: 'new_access_token_list', expiry_date: Date.now() + 3600000 };
            await tokenListener(refreshedTokensFromEvent); // Manually trigger listener

            expect(mockedSaveAtomGmailTokens).toHaveBeenCalledWith(
              mockUserId,
              expect.objectContaining({
                access_token: 'new_access_token_list',
                refresh_token: mockTokenSet.refresh_token, // Should reuse old refresh token
              }),
              mockTokenSet.appEmail
            );
          });
    });

    describe('readEmail', () => {
        const emailId = 'testEmailId123';
        it('should return auth error if no tokens', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(null);
            const result = await emailSkills.readEmail(mockUserId, emailId);
            expect(result.success).toBe(false);
            expect(result.message).toContain('Authentication required');
        });

        it('should fetch, parse, and mark email as read', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            const mockFullMessage = {
                id: emailId, snippet: 'Full snippet', internalDate: String(Date.now()), labelIds: ['INBOX', 'UNREAD'],
                payload: {
                    headers: [{name: 'Subject', value: 'Full Subject'}, {name: 'From', value: 'Sender Full'}, {name: 'To', value: 'Receiver Full'}, {name: 'Date', value: new Date().toUTCString()}],
                    parts: [{ mimeType: 'text/plain', body: { data: Buffer.from('Full body content plain').toString('base64url') } }]
                }
            };
            mockedGmailMessages.get.mockResolvedValue({ data: mockFullMessage } as any);
            mockedGmailMessages.modify.mockResolvedValue({ data: {} } as any);

            const result = await emailSkills.readEmail(mockUserId, emailId);
            expect(mockedGmailMessages.get).toHaveBeenCalledWith({ userId: 'me', id: emailId, format: 'full' });
            expect(mockedGmailMessages.modify).toHaveBeenCalledWith({ userId: 'me', id: emailId, requestBody: { removeLabelIds: ['UNREAD'] } });
            expect(result.success).toBe(true);
            expect(result.email?.subject).toBe('Full Subject');
            expect(result.email?.body).toBe('Full body content plain');
            expect(result.email?.read).toBe(true);
        });

        it('should return error on API failure for readEmail', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.get.mockRejectedValue(new Error("Gmail API get error"));
            const result = await emailSkills.readEmail(mockUserId, emailId);
            expect(result.success).toBe(false);
            expect(result.message).toContain("Failed to read email: Gmail API get error");
        });
    });

    describe('sendEmail', () => {
        const emailDetails: EmailDetails = { to: 'receiver@example.com', subject: 'Test Send', body: 'Hello there!' };
        it('should return auth error if no tokens', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(null);
            const result = await emailSkills.sendEmail(mockUserId, emailDetails);
            expect(result.success).toBe(false);
            expect(result.message).toContain('Authentication required');
        });

        it('should construct raw email and send it', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.send.mockResolvedValue({ data: { id: 'sentMsgId1' } } as any);

            const result = await emailSkills.sendEmail(mockUserId, emailDetails);
            expect(mockedGmailMessages.send).toHaveBeenCalledWith(expect.objectContaining({
                userId: 'me',
                requestBody: expect.objectContaining({
                    raw: expect.any(String)
                })
            }));

            const rawEmailArg = (mockedGmailMessages.send.mock.calls[0][0] as any).requestBody.raw;
            const decodedRawEmail = Buffer.from(rawEmailArg, 'base64url').toString('utf8');
            expect(decodedRawEmail).toContain(`From: ${mockTokenSet.appEmail}`);
            expect(decodedRawEmail).toContain(`To: ${emailDetails.to}`);
            expect(decodedRawEmail).toContain(`Subject: ${emailDetails.subject}`);
            expect(decodedRawEmail).toContain(emailDetails.body);

            expect(result.success).toBe(true);
            expect(result.emailId).toBe('sentMsgId1');
            expect(result.message).toContain('Email sent successfully via Gmail.');
        });

        it('should return error on API failure for sendEmail', async () => {
            mockedGetAtomGmailTokens.mockResolvedValue(mockTokenSet);
            mockedGmailMessages.send.mockRejectedValue(new Error("Gmail API send error"));
            const result = await emailSkills.sendEmail(mockUserId, emailDetails);
            expect(result.success).toBe(false);
            expect(result.message).toContain("Failed to send email via Gmail: Gmail API send error");
        });
    });
});
