import { Request, Response } from 'express';
interface GenerateMcpAuthUrlRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {};
}
declare const handler: (req: Request<{}, {}, GenerateMcpAuthUrlRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
