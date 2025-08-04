import { Request, Response } from 'express';
interface GenerateCanvaAuthUrlRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: {};
}
declare const handler: (req: Request<{}, {}, GenerateCanvaAuthUrlRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
