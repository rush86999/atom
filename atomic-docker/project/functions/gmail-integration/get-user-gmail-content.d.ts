import { Request, Response } from 'express';
interface GmailMessagePayloadHeader {
    name?: string | null;
    value?: string | null;
}
interface GmailMessagePartBody {
    size?: number | null;
    data?: string | null;
    attachmentId?: string | null;
}
interface GmailMessagePart {
    partId?: string | null;
    mimeType?: string | null;
    filename?: string | null;
    headers?: GmailMessagePayloadHeader[] | null;
    body?: GmailMessagePartBody | null;
    parts?: GmailMessagePart[] | null;
}
interface GmailMessageContent {
    id: string;
    threadId?: string | null;
    labelIds?: string[] | null;
    snippet?: string | null;
    historyId?: string | null;
    internalDate?: string | null;
    payload?: GmailMessagePart | null;
    sizeEstimate?: number | null;
    raw?: string | null;
}
interface GetUserGmailContentInput {
    emailId: string;
}
interface GetUserGmailContentRequestBody {
    session_variables: {
        'x-hasura-user-id': string;
    };
    input: GetUserGmailContentInput;
}
interface GetUserGmailContentResponse {
    success: boolean;
    message?: string;
    email?: GmailMessageContent | null;
}
declare const handler: (req: Request<{}, {}, GetUserGmailContentRequestBody>, res: Response<GetUserGmailContentResponse>) => Promise<Response<GetUserGmailContentResponse, Record<string, any>>>;
export default handler;
