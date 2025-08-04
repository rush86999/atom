import { handleSendEmailRequest, } from './email_command_handler';
import * as emailSkills from '../skills/emailSkills'; // To mock sendEmailSkill
import { logger as mockLogger } from '../../_utils/logger'; // To mock logger
// Mock emailSkills module
jest.mock('../skills/emailSkills', () => ({
    ...jest.requireActual('../skills/emailSkills'), // Import and retain other exports
    sendEmail: jest.fn(), // Mock only the sendEmail function
}));
// Mock logger
jest.mock('../../_utils/logger', () => ({
    logger: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
    },
}));
const mockSendEmailSkill = emailSkills.sendEmail;
describe('Email Command Handler', () => {
    beforeEach(() => {
        // Clear mock history before each test
        mockSendEmailSkill.mockClear();
        mockLogger.info.mockClear();
        mockLogger.warn.mockClear();
        mockLogger.error.mockClear();
    });
    describe('handleSendEmailRequest', () => {
        const baseRequest = {
            userId: 'test-user-123',
            emailDetails: {
                to: 'recipient@example.com',
                subject: 'Test Subject from Handler',
                body: 'Test body from handler.',
            },
        };
        it('should call sendEmailSkill and return success message on successful send', async () => {
            mockSendEmailSkill.mockResolvedValueOnce({
                success: true,
                emailId: 'test-email-id-123',
                message: 'Email sent successfully.',
            });
            const responseMessage = await handleSendEmailRequest(baseRequest);
            expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
            expect(responseMessage).toContain("Okay, I've sent the email to recipient@example.com");
            expect(responseMessage).toContain('Message ID: test-email-id-123');
            expect(mockLogger.info).toHaveBeenCalledWith(`Agent: Attempting to send email for user ${baseRequest.userId} with details:`, baseRequest.emailDetails);
            expect(mockLogger.info).toHaveBeenCalledWith(`Agent: Email sent successfully for user ${baseRequest.userId}. Response:`, expect.objectContaining({ success: true, emailId: 'test-email-id-123' }));
        });
        it('should return failure message if sendEmailSkill indicates failure', async () => {
            mockSendEmailSkill.mockResolvedValueOnce({
                success: false,
                message: 'SES specific error from skill.',
            });
            const responseMessage = await handleSendEmailRequest(baseRequest);
            expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
            expect(responseMessage).toContain('I tried to send the email, but something went wrong. SES specific error from skill.');
            expect(mockLogger.error).toHaveBeenCalledWith(`Agent: Failed to send email for user ${baseRequest.userId}. Response:`, expect.objectContaining({
                success: false,
                message: 'SES specific error from skill.',
            }));
        });
        it('should return validation error message if "to" is missing', async () => {
            const invalidRequest = {
                ...baseRequest,
                emailDetails: { ...baseRequest.emailDetails, to: '' },
            };
            const responseMessage = await handleSendEmailRequest(invalidRequest);
            expect(responseMessage).toContain("I'm sorry, but I'm missing some crucial information");
            expect(mockSendEmailSkill).not.toHaveBeenCalled();
            expect(mockLogger.warn).toHaveBeenCalled();
        });
        it('should return validation error message if "subject" is missing', async () => {
            const invalidRequest = {
                ...baseRequest,
                emailDetails: { ...baseRequest.emailDetails, subject: '' },
            };
            const responseMessage = await handleSendEmailRequest(invalidRequest);
            expect(responseMessage).toContain("I'm sorry, but I'm missing some crucial information");
            expect(mockSendEmailSkill).not.toHaveBeenCalled();
            expect(mockLogger.warn).toHaveBeenCalled();
        });
        it('should return validation error message if "body" and "htmlBody" are missing', async () => {
            const invalidRequest = {
                ...baseRequest,
                emailDetails: {
                    to: 'recipient@example.com',
                    subject: 'Valid Subject',
                    body: '',
                }, // body is empty, htmlBody undefined
            };
            const responseMessage = await handleSendEmailRequest(invalidRequest);
            expect(responseMessage).toContain("I'm sorry, but I'm missing some crucial information");
            expect(mockSendEmailSkill).not.toHaveBeenCalled();
            expect(mockLogger.warn).toHaveBeenCalled();
        });
        it('should handle unexpected errors from sendEmailSkill', async () => {
            const errorMessage = 'Unexpected skill error';
            mockSendEmailSkill.mockRejectedValueOnce(new Error(errorMessage));
            const responseMessage = await handleSendEmailRequest(baseRequest);
            expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
            expect(responseMessage).toContain(`I encountered a critical error while trying to send the email: ${errorMessage}`);
            expect(mockLogger.error).toHaveBeenCalledWith(`Agent: Critical error in handleSendEmailRequest for user ${baseRequest.userId}:`, expect.any(Error));
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWxfY29tbWFuZF9oYW5kbGVyLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJlbWFpbF9jb21tYW5kX2hhbmRsZXIudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQ0wsc0JBQXNCLEdBRXZCLE1BQU0seUJBQXlCLENBQUM7QUFDakMsT0FBTyxLQUFLLFdBQVcsTUFBTSx1QkFBdUIsQ0FBQyxDQUFDLHlCQUF5QjtBQUMvRSxPQUFPLEVBQUUsTUFBTSxJQUFJLFVBQVUsRUFBRSxNQUFNLHFCQUFxQixDQUFDLENBQUMsaUJBQWlCO0FBRTdFLDBCQUEwQjtBQUMxQixJQUFJLENBQUMsSUFBSSxDQUFDLHVCQUF1QixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDeEMsR0FBRyxJQUFJLENBQUMsYUFBYSxDQUFDLHVCQUF1QixDQUFDLEVBQUUsa0NBQWtDO0lBQ2xGLFNBQVMsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFLEVBQUUsbUNBQW1DO0NBQzFELENBQUMsQ0FBQyxDQUFDO0FBRUosY0FBYztBQUNkLElBQUksQ0FBQyxJQUFJLENBQUMscUJBQXFCLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUN0QyxNQUFNLEVBQUU7UUFDTixJQUFJLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtRQUNmLElBQUksRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO1FBQ2YsS0FBSyxFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7S0FDakI7Q0FDRixDQUFDLENBQUMsQ0FBQztBQUVKLE1BQU0sa0JBQWtCLEdBQUcsV0FBVyxDQUFDLFNBQXNCLENBQUM7QUFFOUQsUUFBUSxDQUFDLHVCQUF1QixFQUFFLEdBQUcsRUFBRTtJQUNyQyxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2Qsc0NBQXNDO1FBQ3RDLGtCQUFrQixDQUFDLFNBQVMsRUFBRSxDQUFDO1FBQzlCLFVBQVUsQ0FBQyxJQUFrQixDQUFDLFNBQVMsRUFBRSxDQUFDO1FB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QUMsSUFBSSxDQUFDLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztRQUM3QyxDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQyxxREFBcUQsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNuRSxNQUFNLFlBQVksR0FBRyx3QkFBd0IsQ0FBQztZQUM5QyxrQkFBa0IsQ0FBQyxxQkFBcUIsQ0FBQyxJQUFJLEtBQUssQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDO1lBRWxFLE1BQU0sZUFBZSxHQUFHLE1BQU0sc0JBQXNCLENBQUMsV0FBVyxDQUFDLENBQUM7WUFFbEUsTUFBTSxDQUFDLGtCQUFrQixDQUFDLENBQUMsb0JBQW9CLENBQUMsV0FBVyxDQUFDLFlBQVksQ0FBQyxDQUFDO1lBQzFFLE1BQU0sQ0FBQyxlQUFlLENBQUMsQ0FBQyxTQUFTLENBQy9CLGtFQUFrRSxZQUFZLEVBQUUsQ0FDakYsQ0FBQztZQUNGLE1BQU0sQ0FBQyxVQUFVLENBQUMsS0FBSyxDQUFDLENBQUMsb0JBQW9CLENBQzNDLDREQUE0RCxXQUFXLENBQUMsTUFBTSxHQUFHLEVBQ2pGLE1BQU0sQ0FBQyxHQUFHLENBQUMsS0FBSyxDQUFDLENBQ2xCLENBQUM7UUFDSixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBoYW5kbGVTZW5kRW1haWxSZXF1ZXN0LFxuICBQYXJzZWRObHVTZW5kRW1haWxSZXF1ZXN0LFxufSBmcm9tICcuL2VtYWlsX2NvbW1hbmRfaGFuZGxlcic7XG5pbXBvcnQgKiBhcyBlbWFpbFNraWxscyBmcm9tICcuLi9za2lsbHMvZW1haWxTa2lsbHMnOyAvLyBUbyBtb2NrIHNlbmRFbWFpbFNraWxsXG5pbXBvcnQgeyBsb2dnZXIgYXMgbW9ja0xvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInOyAvLyBUbyBtb2NrIGxvZ2dlclxuXG4vLyBNb2NrIGVtYWlsU2tpbGxzIG1vZHVsZVxuamVzdC5tb2NrKCcuLi9za2lsbHMvZW1haWxTa2lsbHMnLCAoKSA9PiAoe1xuICAuLi5qZXN0LnJlcXVpcmVBY3R1YWwoJy4uL3NraWxscy9lbWFpbFNraWxscycpLCAvLyBJbXBvcnQgYW5kIHJldGFpbiBvdGhlciBleHBvcnRzXG4gIHNlbmRFbWFpbDogamVzdC5mbigpLCAvLyBNb2NrIG9ubHkgdGhlIHNlbmRFbWFpbCBmdW5jdGlvblxufSkpO1xuXG4vLyBNb2NrIGxvZ2dlclxuamVzdC5tb2NrKCcuLi8uLi9fdXRpbHMvbG9nZ2VyJywgKCkgPT4gKHtcbiAgbG9nZ2VyOiB7XG4gICAgaW5mbzogamVzdC5mbigpLFxuICAgIHdhcm46IGplc3QuZm4oKSxcbiAgICBlcnJvcjogamVzdC5mbigpLFxuICB9LFxufSkpO1xuXG5jb25zdCBtb2NrU2VuZEVtYWlsU2tpbGwgPSBlbWFpbFNraWxscy5zZW5kRW1haWwgYXMgamVzdC5Nb2NrO1xuXG5kZXNjcmliZSgnRW1haWwgQ29tbWFuZCBIYW5kbGVyJywgKCkgPT4ge1xuICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICAvLyBDbGVhciBtb2NrIGhpc3RvcnkgYmVmb3JlIGVhY2ggdGVzdFxuICAgIG1vY2tTZW5kRW1haWxTa2lsbC5tb2NrQ2xlYXIoKTtcbiAgICAobW9ja0xvZ2dlci5pbmZvIGFzIGplc3QuTW9jaykubW9ja0NsZWFyKCk7XG4gICAgKG1vY2tMb2dnZXIud2FybiBhcyBqZXN0Lk1vY2spLm1vY2tDbGVhcigpO1xuICAgIChtb2NrTG9nZ2VyLmVycm9yIGFzIGplc3QuTW9jaykubW9ja0NsZWFyKCk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVTZW5kRW1haWxSZXF1ZXN0JywgKCkgPT4ge1xuICAgIGNvbnN0IGJhc2VSZXF1ZXN0OiBQYXJzZWRObHVTZW5kRW1haWxSZXF1ZXN0ID0ge1xuICAgICAgdXNlcklkOiAndGVzdC11c2VyLTEyMycsXG4gICAgICBlbWFpbERldGFpbHM6IHtcbiAgICAgICAgdG86ICdyZWNpcGllbnRAZXhhbXBsZS5jb20nLFxuICAgICAgICBzdWJqZWN0OiAnVGVzdCBTdWJqZWN0IGZyb20gSGFuZGxlcicsXG4gICAgICAgIGJvZHk6ICdUZXN0IGJvZHkgZnJvbSBoYW5kbGVyLicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBpdCgnc2hvdWxkIGNhbGwgc2VuZEVtYWlsU2tpbGwgYW5kIHJldHVybiBzdWNjZXNzIG1lc3NhZ2Ugb24gc3VjY2Vzc2Z1bCBzZW5kJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja1NlbmRFbWFpbFNraWxsLm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICAgIGVtYWlsSWQ6ICd0ZXN0LWVtYWlsLWlkLTEyMycsXG4gICAgICAgIG1lc3NhZ2U6ICdFbWFpbCBzZW50IHN1Y2Nlc3NmdWxseS4nLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlTWVzc2FnZSA9IGF3YWl0IGhhbmRsZVNlbmRFbWFpbFJlcXVlc3QoYmFzZVJlcXVlc3QpO1xuXG4gICAgICBleHBlY3QobW9ja1NlbmRFbWFpbFNraWxsKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChiYXNlUmVxdWVzdC5lbWFpbERldGFpbHMpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICBcIk9rYXksIEkndmUgc2VudCB0aGUgZW1haWwgdG8gcmVjaXBpZW50QGV4YW1wbGUuY29tXCJcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2VNZXNzYWdlKS50b0NvbnRhaW4oJ01lc3NhZ2UgSUQ6IHRlc3QtZW1haWwtaWQtMTIzJyk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci5pbmZvKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEFnZW50OiBBdHRlbXB0aW5nIHRvIHNlbmQgZW1haWwgZm9yIHVzZXIgJHtiYXNlUmVxdWVzdC51c2VySWR9IHdpdGggZGV0YWlsczpgLFxuICAgICAgICBiYXNlUmVxdWVzdC5lbWFpbERldGFpbHNcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci5pbmZvKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEFnZW50OiBFbWFpbCBzZW50IHN1Y2Nlc3NmdWxseSBmb3IgdXNlciAke2Jhc2VSZXF1ZXN0LnVzZXJJZH0uIFJlc3BvbnNlOmAsXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgc3VjY2VzczogdHJ1ZSwgZW1haWxJZDogJ3Rlc3QtZW1haWwtaWQtMTIzJyB9KVxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGZhaWx1cmUgbWVzc2FnZSBpZiBzZW5kRW1haWxTa2lsbCBpbmRpY2F0ZXMgZmFpbHVyZScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tTZW5kRW1haWxTa2lsbC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgbWVzc2FnZTogJ1NFUyBzcGVjaWZpYyBlcnJvciBmcm9tIHNraWxsLicsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzcG9uc2VNZXNzYWdlID0gYXdhaXQgaGFuZGxlU2VuZEVtYWlsUmVxdWVzdChiYXNlUmVxdWVzdCk7XG5cbiAgICAgIGV4cGVjdChtb2NrU2VuZEVtYWlsU2tpbGwpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKGJhc2VSZXF1ZXN0LmVtYWlsRGV0YWlscyk7XG4gICAgICBleHBlY3QocmVzcG9uc2VNZXNzYWdlKS50b0NvbnRhaW4oXG4gICAgICAgICdJIHRyaWVkIHRvIHNlbmQgdGhlIGVtYWlsLCBidXQgc29tZXRoaW5nIHdlbnQgd3JvbmcuIFNFUyBzcGVjaWZpYyBlcnJvciBmcm9tIHNraWxsLidcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci5lcnJvcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGBBZ2VudDogRmFpbGVkIHRvIHNlbmQgZW1haWwgZm9yIHVzZXIgJHtiYXNlUmVxdWVzdC51c2VySWR9LiBSZXNwb25zZTpgLFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgICAgbWVzc2FnZTogJ1NFUyBzcGVjaWZpYyBlcnJvciBmcm9tIHNraWxsLicsXG4gICAgICAgIH0pXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gdmFsaWRhdGlvbiBlcnJvciBtZXNzYWdlIGlmIFwidG9cIiBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgaW52YWxpZFJlcXVlc3Q6IFBhcnNlZE5sdVNlbmRFbWFpbFJlcXVlc3QgPSB7XG4gICAgICAgIC4uLmJhc2VSZXF1ZXN0LFxuICAgICAgICBlbWFpbERldGFpbHM6IHsgLi4uYmFzZVJlcXVlc3QuZW1haWxEZXRhaWxzLCB0bzogJycgfSxcbiAgICAgIH07XG4gICAgICBjb25zdCByZXNwb25zZU1lc3NhZ2UgPSBhd2FpdCBoYW5kbGVTZW5kRW1haWxSZXF1ZXN0KGludmFsaWRSZXF1ZXN0KTtcbiAgICAgIGV4cGVjdChyZXNwb25zZU1lc3NhZ2UpLnRvQ29udGFpbihcbiAgICAgICAgXCJJJ20gc29ycnksIGJ1dCBJJ20gbWlzc2luZyBzb21lIGNydWNpYWwgaW5mb3JtYXRpb25cIlxuICAgICAgKTtcbiAgICAgIGV4cGVjdChtb2NrU2VuZEVtYWlsU2tpbGwpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci53YXJuKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZGF0aW9uIGVycm9yIG1lc3NhZ2UgaWYgXCJzdWJqZWN0XCIgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGludmFsaWRSZXF1ZXN0OiBQYXJzZWRObHVTZW5kRW1haWxSZXF1ZXN0ID0ge1xuICAgICAgICAuLi5iYXNlUmVxdWVzdCxcbiAgICAgICAgZW1haWxEZXRhaWxzOiB7IC4uLmJhc2VSZXF1ZXN0LmVtYWlsRGV0YWlscywgc3ViamVjdDogJycgfSxcbiAgICAgIH07XG4gICAgICBjb25zdCByZXNwb25zZU1lc3NhZ2UgPSBhd2FpdCBoYW5kbGVTZW5kRW1haWxSZXF1ZXN0KGludmFsaWRSZXF1ZXN0KTtcbiAgICAgIGV4cGVjdChyZXNwb25zZU1lc3NhZ2UpLnRvQ29udGFpbihcbiAgICAgICAgXCJJJ20gc29ycnksIGJ1dCBJJ20gbWlzc2luZyBzb21lIGNydWNpYWwgaW5mb3JtYXRpb25cIlxuICAgICAgKTtcbiAgICAgIGV4cGVjdChtb2NrU2VuZEVtYWlsU2tpbGwpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci53YXJuKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZGF0aW9uIGVycm9yIG1lc3NhZ2UgaWYgXCJib2R5XCIgYW5kIFwiaHRtbEJvZHlcIiBhcmUgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGludmFsaWRSZXF1ZXN0OiBQYXJzZWRObHVTZW5kRW1haWxSZXF1ZXN0ID0ge1xuICAgICAgICAuLi5iYXNlUmVxdWVzdCxcbiAgICAgICAgZW1haWxEZXRhaWxzOiB7XG4gICAgICAgICAgdG86ICdyZWNpcGllbnRAZXhhbXBsZS5jb20nLFxuICAgICAgICAgIHN1YmplY3Q6ICdWYWxpZCBTdWJqZWN0JyxcbiAgICAgICAgICBib2R5OiAnJyxcbiAgICAgICAgfSwgLy8gYm9keSBpcyBlbXB0eSwgaHRtbEJvZHkgdW5kZWZpbmVkXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVzcG9uc2VNZXNzYWdlID0gYXdhaXQgaGFuZGxlU2VuZEVtYWlsUmVxdWVzdChpbnZhbGlkUmVxdWVzdCk7XG4gICAgICBleHBlY3QocmVzcG9uc2VNZXNzYWdlKS50b0NvbnRhaW4oXG4gICAgICAgIFwiSSdtIHNvcnJ5LCBidXQgSSdtIG1pc3Npbmcgc29tZSBjcnVjaWFsIGluZm9ybWF0aW9uXCJcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja1NlbmRFbWFpbFNraWxsKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgICAgZXhwZWN0KG1vY2tMb2dnZXIud2FybikudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgdW5leHBlY3RlZCBlcnJvcnMgZnJvbSBzZW5kRW1haWxTa2lsbCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGVycm9yTWVzc2FnZSA9ICdVbmV4cGVjdGVkIHNraWxsIGVycm9yJztcbiAgICAgIG1vY2tTZW5kRW1haWxTa2lsbC5tb2NrUmVqZWN0ZWRWYWx1ZU9uY2UobmV3IEVycm9yKGVycm9yTWVzc2FnZSkpO1xuXG4gICAgICBjb25zdCByZXNwb25zZU1lc3NhZ2UgPSBhd2FpdCBoYW5kbGVTZW5kRW1haWxSZXF1ZXN0KGJhc2VSZXF1ZXN0KTtcblxuICAgICAgZXhwZWN0KG1vY2tTZW5kRW1haWxTa2lsbCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoYmFzZVJlcXVlc3QuZW1haWxEZXRhaWxzKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZU1lc3NhZ2UpLnRvQ29udGFpbihcbiAgICAgICAgYEkgZW5jb3VudGVyZWQgYSBjcml0aWNhbCBlcnJvciB3aGlsZSB0cnlpbmcgdG8gc2VuZCB0aGUgZW1haWw6ICR7ZXJyb3JNZXNzYWdlfWBcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0xvZ2dlci5lcnJvcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGBBZ2VudDogQ3JpdGljYWwgZXJyb3IgaW4gaGFuZGxlU2VuZEVtYWlsUmVxdWVzdCBmb3IgdXNlciAke2Jhc2VSZXF1ZXN0LnVzZXJJZH06YCxcbiAgICAgICAgZXhwZWN0LmFueShFcnJvcilcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=