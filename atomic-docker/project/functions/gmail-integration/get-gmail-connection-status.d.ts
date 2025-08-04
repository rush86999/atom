import { Request, Response } from 'express';
interface GetGmailConnectionStatusRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
}
interface GmailConnectionStatusResponse {
    isConnected: boolean;
    userEmail?: string | null;
    message?: string;
}
declare const handler: (req: Request<{}, {}, GetGmailConnectionStatusRequestBody>, res: Response<GmailConnectionStatusResponse>) => Promise<Response<GmailConnectionStatusResponse, Record<string, any>>>;
export default handler;
