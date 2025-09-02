import type { NextApiRequest, NextApiResponse } from 'next';

// Define TypeScript interfaces for our data structures for type safety.
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

// This is our mock database. In a real application, you would fetch this from a CRM like Salesforce or HubSpot.
const mockCrmData: SalesData = {
  opportunities: [
    {
      id: 'opp1',
      name: 'Synergy Corp Website Revamp',
      stage: 'Qualification',
      value: 120000,
    },
    {
      id: 'opp2',
      name: 'Quantum Solutions Cloud Migration',
      stage: 'Proposal',
      value: 350000,
    },
    {
      id: 'opp3',
      name: 'Innovate LLC AI Chatbot',
      stage: 'Negotiation',
      value: 75000,
    },
  ],
  contacts: [
    { id: 'cont1', name: 'Laura Chen', opportunityId: 'opp1' },
    { id: 'cont2', name: 'David Rodriguez', opportunityId: 'opp2' },
    { id: 'cont3', name: 'Samantha Williams', opportunityId: 'opp3' },
  ],
  tasks: [
    {
      id: 'task1',
      description: 'Schedule discovery call with Synergy Corp',
      dueDate: '2024-08-05',
    },
    {
      id: 'task2',
      description: 'Finalize proposal for Quantum Solutions',
      dueDate: '2024-08-10',
    },
    {
      id: 'task3',
      description: 'Send updated contract to Innovate LLC',
      dueDate: '2024-07-30',
    },
  ],
};

/**
 * API handler for fetching CRM data.
 * It simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request. The userId could be extracted from here.
 * @param {NextApiResponse<SalesData>} res - The outgoing API response.
 */
export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<SalesData>
) {
  // You could use req.query.userId here to fetch user-specific data from a real CRM.
  // const { userId } = req.query;

  // Simulate a network delay of 1 second to mimic a real API call.
  setTimeout(() => {
    res.status(200).json(mockCrmData);
  }, 1000);
}
