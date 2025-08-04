import { Request, Response } from 'express';
interface GetUserOutlookContentInput {
    emailId: string;
}
interface GetUserOutlookContentRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: GetUserOutlookContentInput;
}
declare const handler: (req: Request<{}, {}, GetUserOutlookContentRequestBody>, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
