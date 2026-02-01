import axios from "axios";
// Type definitions
export interface SkillResponse<T> {
  ok: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface PythonApiResponse<T> {
  ok: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface ShopifyProduct {
  id: string;
  title: string;
  handle: string;
}

export interface ShopifyOrder {
  id: string;
  order_number: string;
}

export interface ShopifyTopSellingProduct {
  id: string;
  title: string;
  vancant_units: number;
}

export interface ShopifyConnectionStatusInfo {
  isConnected: boolean;
  shopUrl?: string;
  reason?: string;
}

// Configuration
const PYTHON_API_SERVICE_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Simple logger
const logger = {
  warn: (message: string, error?: any) => console.warn(message, error),
  error: (message: string, error?: any) => console.error(message, error),
  info: (message: string, data?: any) => console.log(message, data),
};

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: PythonApiResponse<T>,
  operationName: string,
): SkillResponse<T> {
  if (response.ok && response.data !== undefined) {
    return { ok: true, data: response.data };
  }
  logger.warn(
    `[${operationName}] Failed API call. API ok: ${response.ok}`,
    response.error,
  );
  return {
    ok: false,
    error: {
      code: response.error?.code || "PYTHON_API_ERROR",
      message: response.error?.message || `Failed to ${operationName}.`,
      details: response.error?.details,
    },
  };
}

// Helper to handle network/axios errors
// Helper to handle network/axios errors
function handleAxiosError<T>(
  error: any,
  operationName: string,
): SkillResponse<T> {
  if (error.response) {
    logger.error(
      `[${operationName}] Error: ${error.response.status}`,
      error.response.data,
    );
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}.`,
      },
    } as SkillResponse<T>;
  } else if (error.request) {
    logger.error(
      `[${operationName}] Error: No response received`,
      error.request,
    );
    return {
      ok: false,
      error: {
        code: "NETWORK_ERROR",
        message: `No response received for ${operationName}.`,
      },
    } as SkillResponse<T>;
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: "REQUEST_SETUP_ERROR",
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  } as SkillResponse<T>;
}

export async function listShopifyProducts(
  userId: string,
): Promise<SkillResponse<{ products: ShopifyProduct[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/products?user_id=${userId}`;

  try {
    const response =
      await axios.get<PythonApiResponse<{ products: ShopifyProduct[] }>>(
        endpoint,
      );
    return handlePythonApiResponse(response.data, "listShopifyProducts");
  } catch (error) {
    return handleAxiosError<any>(error, "listShopifyProducts");
  }
}

export async function getShopifyOrder(
  userId: string,
  orderId: string,
): Promise<SkillResponse<ShopifyOrder>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/orders/${orderId}?user_id=${userId}`;

  try {
    const response = await axios.get<PythonApiResponse<ShopifyOrder>>(endpoint);
    return handlePythonApiResponse(response.data, "getShopifyOrder");
  } catch (error) {
    return handleAxiosError<any>(error, "getShopifyOrder");
  }
}

export async function getTopSellingProducts(
  userId: string,
): Promise<SkillResponse<{ products: ShopifyTopSellingProduct[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/top-selling-products?user_id=${userId}`;

  try {
    const response =
      await axios.get<
        PythonApiResponse<{ products: ShopifyTopSellingProduct[] }>
      >(endpoint);
    return handlePythonApiResponse(response.data, "getTopSellingProducts");
  } catch (error) {
    return handleAxiosError<any>(error, "getTopSellingProducts");
  }
}

export async function getShopifyConnectionStatus(
  userId: string,
): Promise<SkillResponse<{ isConnected: boolean; shopUrl?: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/connection-status?user_id=${userId}`;

  try {
    const response =
      await axios.get<
        PythonApiResponse<{ isConnected: boolean; shopUrl?: string }>
      >(endpoint);
    return handlePythonApiResponse(response.data, "getShopifyConnectionStatus");
  } catch (error) {
    return handleAxiosError<any>(error, "getShopifyConnectionStatus");
  }
}

export async function disconnectShopify(
  userId: string,
): Promise<SkillResponse<null>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/disconnect`;

  try {
    const response = await axios.post<PythonApiResponse<null>>(endpoint, {
      user_id: userId,
    });
    return handlePythonApiResponse(response.data, "disconnectShopify");
  } catch (error) {
    return handleAxiosError<any>(error, "disconnectShopify");
  }
}

export async function updateInventory(
  userId: string,
  variantId: string,
  newQuantity: number,
): Promise<
  SkillResponse<{
    inventory_level: { inventory_item_id: string; available: number };
  }>
> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: "CONFIG_ERROR",
        message: "Python API service URL is not configured.",
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/update-inventory`;

  try {
    const response = await axios.post<
      PythonApiResponse<{
        inventory_level: { inventory_item_id: string; available: number };
      }>
    >(endpoint, {
      user_id: userId,
      variant_id: variantId,
      new_quantity: newQuantity,
    });
    return handlePythonApiResponse(response.data, "updateInventory");
  } catch (error) {
    return handleAxiosError<any>(error, "updateInventory");
  }
}
