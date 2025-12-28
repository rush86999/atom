import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const { path } = req.query;
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Construct the full backend URL
  const apiPath = Array.isArray(path) ? path.join("/") : path || "";
  const fullUrl = `${backendUrl}/api/lancedb-search/${apiPath}`;

  try {
    // Forward the request to the backend
    const response = await fetch(fullUrl, {
      method: req.method,
      headers: {
        "Content-Type": "application/json",
        ...(req.headers.authorization && {
          Authorization: req.headers.authorization,
        }),
      },
      body:
        req.method !== "GET" && req.method !== "HEAD"
          ? JSON.stringify(req.body)
          : undefined,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Backend API error (${response.status}):`, errorText);
      return res.status(response.status).json({
        success: false,
        error: `Backend API error: ${response.statusText}`,
      });
    }

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (error) {
    console.error("Error proxying to backend:", error);
    res.status(500).json({
      success: false,
      error: "Failed to connect to search backend",
    });
  }
}
