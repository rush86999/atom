import { Request, Response } from 'express';
interface SearchUserGmailInput {
    query: string;
    maxResults?: number;
}
interface SearchUserGmailRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: SearchUserGmailInput;
}
interface GmailSearchResultItem {
    id: string;
    threadId?: string;
    snippet?: string;
    subject?: string;
    from?: string;
    date?: string;
}
interface SearchUserGmailResponse {
    success: boolean;
    message?: string;
    results?: GmailSearchResultItem[];
}
declare const handler: (req: Request<{}, {}, SearchUserGmailRequestBody>, res: Response<SearchUserGmailResponse>) => Promise<Response<SearchUserGmailResponse, Record<string, any>>>;
export default handler;
