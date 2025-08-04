import { Request, Response } from 'express';
declare const publisher: (req: Request, res: Response) => Promise<void>;
export default publisher;
