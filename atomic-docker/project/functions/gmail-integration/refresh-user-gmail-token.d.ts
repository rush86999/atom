import { Request, Response } from 'express';
interface RefreshGmailTokenRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {};
}
declare const handler: (req: Request<{}, {}, RefreshGmailTokenRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
