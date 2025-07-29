import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // In a real application, you would fetch data from each agent skill's data source.
  // For this example, we'll just return some mock data.

  const dashboardData = {
    calendar: [
      { id: 1, title: 'Meeting with team', time: '10:00 AM' },
      { id: 2, title: 'Lunch with Jane', time: '12:30 PM' },
    ],
    tasks: [
      { id: 1, title: 'Finish report', due_date: 'Today' },
      { id: 2, title: 'Follow up with client', due_date: 'Tomorrow' },
    ],
    social: [
      { id: 1, platform: 'Twitter', post: 'Just released a new feature!' },
      { id: 2, platform: 'LinkedIn', post: 'We are hiring!' },
    ],
  };

  res.status(200).json(dashboardData);
}
