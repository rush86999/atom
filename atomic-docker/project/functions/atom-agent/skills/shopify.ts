import axios, { AxiosError } from 'axios';
import {
  SkillResponse,
  ShopifyProduct,
  ShopifyOrder,
  PythonApiResponse,
  ShopifyConnectionStatus,
} from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: PythonApiResponse<T>,
  operationName: string
): SkillResponse<T> {
  if (response.ok && response.data !== undefined) {
    return { ok: true, data: response.data };
  }
  logger.warn(
    `[${operationName}] Failed API call. API ok: ${response.ok}`,
    response.error
  );
  return {
    ok: false,
    error: {
      code: response.error?.code || 'PYTHON_API_ERROR',
      message: response.error?.message || `Failed to ${operationName}.`,
      details: response.error?.details,
    },
  };
}

// Helper to handle network/axios errors
function handleAxiosError(
  error: AxiosError,
  operationName: string
): SkillResponse<null> {
  if (error.response) {
    logger.error(
      `[${operationName}] Error: ${error.response.status}`,
      error.response.data
    );
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}.`,
      },
    };
  } else if (error.request) {
    logger.error(
      `[${operationName}] Error: No response received`,
      error.request
    );
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: `No response received for ${operationName}.`,
      },
    };
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: 'REQUEST_SETUP_ERROR',
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  };
}

export async function listShopifyProducts(
  userId: string
): Promise<SkillResponse<{ products: ShopifyProduct[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/products?user_id=${userId}`;

  try {
    const response =
      await axios.get<PythonApiResponse<{ products: ShopifyProduct[] }>>(
        endpoint
      );
    return handlePythonApiResponse(response.data, 'listShopifyProducts');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'listShopifyProducts');
  }
}

export async function getShopifyOrder(
  userId: string,
  orderId: string
): Promise<SkillResponse<ShopifyOrder>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/orders/${orderId}?user_id=${userId}`;

  try {
    const response = await axios.get<PythonApiResponse<ShopifyOrder>>(endpoint);
    return handlePythonApiResponse(response.data, 'getShopifyOrder');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getShopifyOrder');
  }
}

export async function getShopifyConnectionStatus(
  userId: string
): Promise<SkillResponse<ShopifyConnectionStatus>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/shopify/connection-status?user_id=${userId}`;

  try {
    const response =
      await axios.get<
        PythonApiResponse<ShopifyConnectionStatus>
      >(endpoint);
    return handlePythonApiResponse(response.data, 'getShopifyConnectionStatus');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getShopifyConnectionStatus');
  }
}

// Handler functions for NLU integration
export async function handleListShopifyProducts(userId: string): Promise<string> {
  const result = await listShopifyProducts(userId);
  if (result.ok) {
    const products = result.data?.products || [];
    return `Found ${products.length} Shopify product${products.length !== 1 ? 's' : ''}${products.length > 0 ? ': ' + products.slice(0, 5).map(p => p.title).join(', ') : ''}`;
  } else {
    return `Error fetching Shopify products: ${result.error?.message}`;
  }
}

export async function handleGetShopifyOrder(userId: string, entities: any): Promise<string> {
  const orderId = entities.orderId || entities.id;
  if (!orderId) {
    return 'Please provide an order ID to get the details.';
  }

  const result = await getShopifyOrder(userId, orderId);
  if (result.ok) {
    const order = result.data;
    return `Shopify Order #${order.order_number || order.id} - ${order.financial_status} - Total: ${order.total_price}${order.currency}`;
  } else {
    return `Error fetching Shopify order: ${result.error?.message}`;
  }
}

export async function handleGetShopifyConnectionStatus(userId: string): Promise<string> {
  const result = await getShopifyConnectionStatus(userId);
  if (result.ok) {
    const status = result.data;
    return status.isConnected
      ? `Shopify is connected as: ${status.shopUrl}`
      : 'Shopify is not currently connected.';
  } else {
    return `Error checking Shopify connection: ${result.error?.message}`;
  }
}
