import { Request, Response } from 'express';
declare const opensearch: (req: Request, res: Response) => Promise<Response<any, Record<string, any>>>;
export default opensearch;
