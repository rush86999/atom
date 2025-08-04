import type { NextApiRequest, NextApiResponse } from 'next';
interface Opportunity {
    id: string;
    name: string;
    stage: string;
    value: number;
}
interface Contact {
    id: string;
    name: string;
    opportunityId: string;
}
interface Task {
    id: string;
    description: string;
    dueDate: string;
}
interface SalesData {
    opportunities: Opportunity[];
    contacts: Contact[];
    tasks: Task[];
}
/**
 * API handler for fetching CRM data.
 * It simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request. The userId could be extracted from here.
 * @param {NextApiResponse<SalesData>} res - The outgoing API response.
 */
export default function handler(req: NextApiRequest, res: NextApiResponse<SalesData>): void;
export {};
