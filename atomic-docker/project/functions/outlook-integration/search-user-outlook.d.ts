import { Request, Response } from 'express';
interface SearchUserOutlookInput {
    query: string;
    maxResults?: number;
}
interface SearchUserOutlookRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: SearchUserOutlookInput;
}
declare const handler: (req: Request<{}, {}, SearchUserOutlookRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
