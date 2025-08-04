import { NextApiRequest, NextApiResponse } from 'next';
import { Request, Response } from 'express';
export default function superTokens(req: NextApiRequest & Request, res: NextApiResponse & Response): Promise<void>;
