import { Request, Response } from 'express';
declare const handler: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export default handler;
