import type { NextApiRequest, NextApiResponse } from "next";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.PYTHON_API_SERVICE_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

async function proxyToBackend(req: NextApiRequest, backendUrl: string) {
  return fetch(backendUrl, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      ...(req.headers.authorization
        ? { Authorization: req.headers.authorization }
        : {}),
      ...(req.headers.cookie ? { Cookie: req.headers.cookie } : {}),
    },
    body:
      req.method !== "GET" && req.method !== "HEAD"
        ? JSON.stringify(req.body ?? {})
        : undefined,
  });
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const path = Array.isArray(req.query.path)
    ? req.query.path.join("/")
    : req.query.path || "";

  const queryParams = new URLSearchParams();
  Object.entries(req.query).forEach(([key, value]) => {
    if (key === "path" || value === undefined) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => queryParams.append(key, item));
    } else {
      queryParams.append(key, value);
    }
  });

  const queryString = queryParams.toString();
  const querySuffix = queryString ? `?${queryString}` : "";
  // The backend mounts GraphRAG at /api/graphrag (main_api_app.py includes
  // graphrag_router without an extra prefix). The old first attempt under
  // /api/graphrag/api/graphrag always 404'd, so every explorer request paid a
  // doomed round-trip before the fallback. Proxy the real route directly.
  const backendUrl = `${BACKEND_URL}/api/graphrag/${path}${querySuffix}`;

  try {
    const response = await proxyToBackend(req, backendUrl);
    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      const text = await response.text();
      return res.status(response.ok ? 502 : response.status).json({
        success: false,
        error: "GraphRAG backend returned a non-JSON response",
        status: response.status,
        preview: text.slice(0, 200),
      });
    }

    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    console.error("GraphRAG proxy error:", error);
    return res.status(502).json({
      success: false,
      error: "Failed to connect to GraphRAG backend",
      message: error instanceof Error ? error.message : "Unknown error",
    });
  }
}
