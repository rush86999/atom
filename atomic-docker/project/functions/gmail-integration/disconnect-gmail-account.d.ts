import { Request, Response } from 'express';
interface DisconnectGmailAccountRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
}
interface DisconnectGmailAccountResponse {
    success: boolean;
    message?: string;
}
declare const handler: (req: Request<{}, {}, DisconnectGmailAccountRequestBody>, res: Response<DisconnectGmailAccountResponse>) => Promise<Response<DisconnectGmailAccountResponse, Record<string, any>>>;
export default handler;
