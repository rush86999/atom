import { Request, Response } from 'express';
export declare function decrypt(text: string): string;
interface HandleGmailAuthCallbackRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {
        code: string;
    };
}
declare const handler: (req: Request<{}, {}, HandleGmailAuthCallbackRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
