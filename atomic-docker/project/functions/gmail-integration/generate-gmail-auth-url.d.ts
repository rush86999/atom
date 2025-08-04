import { Request, Response } from 'express';
interface GenerateGmailAuthUrlRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {};
}
declare const handler: (req: Request<{}, {}, GenerateGmailAuthUrlRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
