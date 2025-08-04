import { handleListEmails, handleReadEmail, handleSendEmail } from '../email';
import * as emailSkills from '../emailSkills';
jest.mock('../emailSkills', () => ({
    listRecentEmails: jest.fn(),
    readEmail: jest.fn(),
    sendEmail: jest.fn(),
}));
describe('email skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleListEmails', () => {
        it('should return a list of recent emails', async () => {
            const mockEmails = [
                {
                    id: 'test-email-1',
                    sender: 'test1@example.com',
                    subject: 'Test Email 1',
                    read: false,
                },
                {
                    id: 'test-email-2',
                    sender: 'test2@example.com',
                    subject: 'Test Email 2',
                    read: true,
                },
            ];
            emailSkills.listRecentEmails.mockResolvedValue(mockEmails);
            const result = await handleListEmails({});
            expect(result).toContain('Recent emails (via NLU):');
            expect(result).toContain('Test Email 1');
            expect(result).toContain('Test Email 2');
        });
        it('should return a message when there are no recent emails', async () => {
            emailSkills.listRecentEmails.mockResolvedValue([]);
            const result = await handleListEmails({});
            expect(result).toBe('No recent emails found (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            emailSkills.listRecentEmails.mockRejectedValue(new Error('Test Error'));
            const result = await handleListEmails({});
            expect(result).toBe("Sorry, I couldn't fetch recent emails due to an error (NLU path).");
        });
    });
    describe('handleReadEmail', () => {
        it('should return the content of an email', async () => {
            const mockEmail = {
                id: 'test-email-1',
                sender: 'test1@example.com',
                recipient: 'test@example.com',
                subject: 'Test Email 1',
                timestamp: new Date().toISOString(),
                body: 'This is a test email.',
            };
            emailSkills.readEmail.mockResolvedValue({
                success: true,
                email: mockEmail,
            });
            const result = await handleReadEmail({ email_id: 'test-email-1' });
            expect(result).toContain('Email (ID: test-email-1):');
            expect(result).toContain('This is a test email.');
        });
        it('should return an error message when the email ID is missing', async () => {
            const result = await handleReadEmail({});
            expect(result).toBe('Email ID is required to read an email via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            emailSkills.readEmail.mockRejectedValue(new Error('Test Error'));
            const result = await handleReadEmail({ email_id: 'test-email-1' });
            expect(result).toBe("Sorry, I couldn't read the specified email due to an error (NLU path).");
        });
    });
    describe('handleSendEmail', () => {
        it('should send an email', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
                body: 'This is a test email.',
            };
            emailSkills.sendEmail.mockResolvedValue({
                success: true,
                message: 'Email sent successfully',
                emailId: 'test-email-id',
            });
            const result = await handleSendEmail(mockEmail);
            expect(result).toContain('Email sent via NLU: Email sent successfully');
        });
        it('should return an error message when the recipient is missing', async () => {
            const mockEmail = {
                subject: 'Test Email',
                body: 'This is a test email.',
            };
            const result = await handleSendEmail(mockEmail);
            expect(result).toBe("Recipient 'to' address is required to send an email via NLU.");
        });
        it('should return an error message when the subject is missing', async () => {
            const mockEmail = {
                to: 'test@example.com',
                body: 'This is a test email.',
            };
            const result = await handleSendEmail(mockEmail);
            expect(result).toBe('Subject is required to send an email via NLU.');
        });
        it('should return an error message when the body is missing', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
            };
            const result = await handleSendEmail(mockEmail);
            expect(result).toBe('Body is required to send an email via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
                body: 'This is a test email.',
            };
            emailSkills.sendEmail.mockRejectedValue(new Error('Test Error'));
            const result = await handleSendEmail(mockEmail);
            expect(result).toBe("Sorry, I couldn't send the email due to an error (NLU path).");
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWwudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImVtYWlsLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLGdCQUFnQixFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsTUFBTSxVQUFVLENBQUM7QUFDOUUsT0FBTyxLQUFLLFdBQVcsTUFBTSxnQkFBZ0IsQ0FBQztBQUU5QyxJQUFJLENBQUMsSUFBSSxDQUFDLGdCQUFnQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDakMsZ0JBQWdCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUMzQixTQUFTLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUNwQixTQUFTLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUNyQixDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxhQUFhLEVBQUUsR0FBRyxFQUFFO0lBQzNCLFNBQVMsQ0FBQyxHQUFHLEVBQUU7UUFDYixJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkIsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsa0JBQWtCLEVBQUUsR0FBRyxFQUFFO1FBQ2hDLEVBQUUsQ0FBQyx1Q0FBdUMsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNyRCxNQUFNLFVBQVUsR0FBRztnQkFDakI7b0JBQ0UsRUFBRSxFQUFFLGNBQWM7b0JBQ2xCLE1BQU0sRUFBRSxtQkFBbUI7b0JBQzNCLE9BQU8sRUFBRSxjQUFjO29CQUN2QixJQUFJLEVBQUUsS0FBSztpQkFDWjtnQkFDRDtvQkFDRSxFQUFFLEVBQUUsY0FBYztvQkFDbEIsTUFBTSxFQUFFLG1CQUFtQjtvQkFDM0IsT0FBTyxFQUFFLGNBQWM7b0JBQ3ZCLElBQUksRUFBRSxJQUFJO2lCQUNYO2FBQ0YsQ0FBQztZQUNELFdBQVcsQ0FBQyxnQkFBOEIsQ0FBQyxpQkFBaUIsQ0FBQyxVQUFVLENBQUMsQ0FBQztZQUUxRSxNQUFNLE1BQU0sR0FBRyxNQUFNLGdC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QUMseURBQXlELEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDdkUsTUFBTSxTQUFTLEdBQUc7Z0JBQ2hCLEVBQUUsRUFBRSxrQkFBa0I7Z0JBQ3RCLE9BQU8sRUFBRSxZQUFZO2FBQ3RCLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxTQUFTLENBQUMsQ0FBQztZQUVoRCxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUFDLDRDQUE0QyxDQUFDLENBQUM7UUFDcEUsQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMscURBQXFELEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDbkUsTUFBTSxTQUFTLEdBQUc7Z0JBQ2hCLEVBQUUsRUFBRSxrQkFBa0I7Z0JBQ3RCLE9BQU8sRUFBRSxZQUFZO2dCQUNyQixJQUFJLEVBQUUsdUJBQXVCO2FBQzlCLENBQUM7WUFDRCxXQUFXLENBQUMsU0FBdUIsQ0FBQyxpQkFBaUIsQ0FDcEQsSUFBSSxLQUFLLENBQUMsWUFBWSxDQUFDLENBQ3hCLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxTQUFTLENBQUMsQ0FBQztZQUVoRCxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQiw4REFBOEQsQ0FDL0QsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGhhbmRsZUxpc3RFbWFpbHMsIGhhbmRsZVJlYWRFbWFpbCwgaGFuZGxlU2VuZEVtYWlsIH0gZnJvbSAnLi4vZW1haWwnO1xuaW1wb3J0ICogYXMgZW1haWxTa2lsbHMgZnJvbSAnLi4vZW1haWxTa2lsbHMnO1xuXG5qZXN0Lm1vY2soJy4uL2VtYWlsU2tpbGxzJywgKCkgPT4gKHtcbiAgbGlzdFJlY2VudEVtYWlsczogamVzdC5mbigpLFxuICByZWFkRW1haWw6IGplc3QuZm4oKSxcbiAgc2VuZEVtYWlsOiBqZXN0LmZuKCksXG59KSk7XG5cbmRlc2NyaWJlKCdlbWFpbCBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUxpc3RFbWFpbHMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBsaXN0IG9mIHJlY2VudCBlbWFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRW1haWxzID0gW1xuICAgICAgICB7XG4gICAgICAgICAgaWQ6ICd0ZXN0LWVtYWlsLTEnLFxuICAgICAgICAgIHNlbmRlcjogJ3Rlc3QxQGV4YW1wbGUuY29tJyxcbiAgICAgICAgICBzdWJqZWN0OiAnVGVzdCBFbWFpbCAxJyxcbiAgICAgICAgICByZWFkOiBmYWxzZSxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIGlkOiAndGVzdC1lbWFpbC0yJyxcbiAgICAgICAgICBzZW5kZXI6ICd0ZXN0MkBleGFtcGxlLmNvbScsXG4gICAgICAgICAgc3ViamVjdDogJ1Rlc3QgRW1haWwgMicsXG4gICAgICAgICAgcmVhZDogdHJ1ZSxcbiAgICAgICAgfSxcbiAgICAgIF07XG4gICAgICAoZW1haWxTa2lsbHMubGlzdFJlY2VudEVtYWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKG1vY2tFbWFpbHMpO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0RW1haWxzKHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdSZWNlbnQgZW1haWxzICh2aWEgTkxVKTonKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBFbWFpbCAxJyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1Rlc3QgRW1haWwgMicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBtZXNzYWdlIHdoZW4gdGhlcmUgYXJlIG5vIHJlY2VudCBlbWFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoZW1haWxTa2lsbHMubGlzdFJlY2VudEVtYWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFtdKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdEVtYWlscyh7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoJ05vIHJlY2VudCBlbWFpbHMgZm91bmQgKHZpYSBOTFUpLicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIChlbWFpbFNraWxscy5saXN0UmVjZW50RW1haWxzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0RW1haWxzKHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBmZXRjaCByZWNlbnQgZW1haWxzIGR1ZSB0byBhbiBlcnJvciAoTkxVIHBhdGgpLlwiXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlUmVhZEVtYWlsJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIHRoZSBjb250ZW50IG9mIGFuIGVtYWlsJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0VtYWlsID0ge1xuICAgICAgICBpZDogJ3Rlc3QtZW1haWwtMScsXG4gICAgICAgIHNlbmRlcjogJ3Rlc3QxQGV4YW1wbGUuY29tJyxcbiAgICAgICAgcmVjaXBpZW50OiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgIHN1YmplY3Q6ICdUZXN0IEVtYWlsIDEnLFxuICAgICAgICB0aW1lc3RhbXA6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgYm9keTogJ1RoaXMgaXMgYSB0ZXN0IGVtYWlsLicsXG4gICAgICB9O1xuICAgICAgKGVtYWlsU2tpbGxzLnJlYWRFbWFpbCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgZW1haWw6IG1vY2tFbWFpbCxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVSZWFkRW1haWwoeyBlbWFpbF9pZDogJ3Rlc3QtZW1haWwtMScgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRW1haWwgKElEOiB0ZXN0LWVtYWlsLTEpOicpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUaGlzIGlzIGEgdGVzdCBlbWFpbC4nKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiB0aGUgZW1haWwgSUQgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVJlYWRFbWFpbCh7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoJ0VtYWlsIElEIGlzIHJlcXVpcmVkIHRvIHJlYWQgYW4gZW1haWwgdmlhIE5MVS4nKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoZW1haWxTa2lsbHMucmVhZEVtYWlsIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVSZWFkRW1haWwoeyBlbWFpbF9pZDogJ3Rlc3QtZW1haWwtMScgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgcmVhZCB0aGUgc3BlY2lmaWVkIGVtYWlsIGR1ZSB0byBhbiBlcnJvciAoTkxVIHBhdGgpLlwiXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlU2VuZEVtYWlsJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgc2VuZCBhbiBlbWFpbCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tFbWFpbCA9IHtcbiAgICAgICAgdG86ICd0ZXN0QGV4YW1wbGUuY29tJyxcbiAgICAgICAgc3ViamVjdDogJ1Rlc3QgRW1haWwnLFxuICAgICAgICBib2R5OiAnVGhpcyBpcyBhIHRlc3QgZW1haWwuJyxcbiAgICAgIH07XG4gICAgICAoZW1haWxTa2lsbHMuc2VuZEVtYWlsIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICBtZXNzYWdlOiAnRW1haWwgc2VudCBzdWNjZXNzZnVsbHknLFxuICAgICAgICBlbWFpbElkOiAndGVzdC1lbWFpbC1pZCcsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VuZEVtYWlsKG1vY2tFbWFpbCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRW1haWwgc2VudCB2aWEgTkxVOiBFbWFpbCBzZW50IHN1Y2Nlc3NmdWxseScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSByZWNpcGllbnQgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tFbWFpbCA9IHtcbiAgICAgICAgc3ViamVjdDogJ1Rlc3QgRW1haWwnLFxuICAgICAgICBib2R5OiAnVGhpcyBpcyBhIHRlc3QgZW1haWwuJyxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlbmRFbWFpbChtb2NrRW1haWwpO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICBcIlJlY2lwaWVudCAndG8nIGFkZHJlc3MgaXMgcmVxdWlyZWQgdG8gc2VuZCBhbiBlbWFpbCB2aWEgTkxVLlwiXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBzdWJqZWN0IGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRW1haWwgPSB7XG4gICAgICAgIHRvOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgIGJvZHk6ICdUaGlzIGlzIGEgdGVzdCBlbWFpbC4nLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VuZEVtYWlsKG1vY2tFbWFpbCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoJ1N1YmplY3QgaXMgcmVxdWlyZWQgdG8gc2VuZCBhbiBlbWFpbCB2aWEgTkxVLicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBib2R5IGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRW1haWwgPSB7XG4gICAgICAgIHRvOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgIHN1YmplY3Q6ICdUZXN0IEVtYWlsJyxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlbmRFbWFpbChtb2NrRW1haWwpO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKCdCb2R5IGlzIHJlcXVpcmVkIHRvIHNlbmQgYW4gZW1haWwgdmlhIE5MVS4nKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRW1haWwgPSB7XG4gICAgICAgIHRvOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgIHN1YmplY3Q6ICdUZXN0IEVtYWlsJyxcbiAgICAgICAgYm9keTogJ1RoaXMgaXMgYSB0ZXN0IGVtYWlsLicsXG4gICAgICB9O1xuICAgICAgKGVtYWlsU2tpbGxzLnNlbmRFbWFpbCBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VuZEVtYWlsKG1vY2tFbWFpbCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiU29ycnksIEkgY291bGRuJ3Qgc2VuZCB0aGUgZW1haWwgZHVlIHRvIGFuIGVycm9yIChOTFUgcGF0aCkuXCJcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=