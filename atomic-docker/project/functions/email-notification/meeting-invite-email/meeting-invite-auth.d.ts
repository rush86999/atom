import { Request, Response } from 'express';
declare const handler: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | {
    statusCode: number;
    headers: {
        'Access-Control-Allow-Origin': string;
    };
    body: string;
} | undefined>;
export default handler;
