import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { query } = req.query;

  // In a real application, you would have a more sophisticated search implementation
  // that would query each agent skill's data source. For this example, we'll just
  // return some mock data.

  const results = [
    {
      skill: 'Research',
      title: `Research results for "${query}"`,
      url: `/Research?q=${query}`,
    },
    {
      skill: 'Social',
      title: `Social media posts about "${query}"`,
      url: `/Social?q=${query}`,
    },
    {
      skill: 'Content',
      title: `Content ideas for "${query}"`,
      url: `/Content?q=${query}`,
    },
    {
      skill: 'Shopping',
      title: `Shopping results for "${query}"`,
      url: `/Shopping?q=${query}`,
    },
  ];

  res.status(200).json(results);
}
