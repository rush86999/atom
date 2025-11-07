import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
  const { reportType } = req.query;

  if (!reportType || typeof reportType !== 'string') {
    return res.status(400).json({
      error: 'Report type is required',
      message: 'Please specify a report type (profitandloss, balancesheet, cashflow)',
    });
  }

  try {
    const url = `${backendUrl}/api/quickbooks/reports/${reportType}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('QuickBooks reports API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch QuickBooks report',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}