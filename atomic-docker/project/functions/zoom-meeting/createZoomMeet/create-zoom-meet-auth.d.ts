import { Request, Response } from 'express';
declare const publisher: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export default publisher;
