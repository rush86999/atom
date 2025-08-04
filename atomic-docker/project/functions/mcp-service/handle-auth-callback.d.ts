import { Request, Response } from 'express';
interface HandleMcpAuthCallbackRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {
        code: string;
    };
}
declare const handler: (req: Request<{}, {}, HandleMcpAuthCallbackRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
