"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.listShopifyProducts = listShopifyProducts;
exports.getShopifyOrder = getShopifyOrder;
exports.getTopSellingProducts = getTopSellingProducts;
exports.getShopifyConnectionStatus = getShopifyConnectionStatus;
exports.disconnectShopify = disconnectShopify;
exports.updateInventory = updateInventory;
const axios_1 = __importDefault(require("axios"));
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants");
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse(response, operationName) {
    if (response.ok && response.data !== undefined) {
        return { ok: true, data: response.data };
    }
    logger_1.logger.warn(`[${operationName}] Failed API call. API ok: ${response.ok}`, response.error);
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
function handleAxiosError(error, operationName) {
    if (error.response) {
        logger_1.logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
        const errData = error.response.data;
        return {
            ok: false,
            error: {
                code: `HTTP_${error.response.status}`,
                message: errData?.error?.message || `Failed to ${operationName}.`,
            },
        };
    }
    else if (error.request) {
        logger_1.logger.error(`[${operationName}] Error: No response received`, error.request);
        return {
            ok: false,
            error: {
                code: "NETWORK_ERROR",
                message: `No response received for ${operationName}.`,
            },
        };
    }
    logger_1.logger.error(`[${operationName}] Error: ${error.message}`);
    return {
        ok: false,
        error: {
            code: "REQUEST_SETUP_ERROR",
            message: `Error setting up request for ${operationName}: ${error.message}`,
        },
    };
}
async function listShopifyProducts(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/products?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response.data, "listShopifyProducts");
    }
    catch (error) {
        return handleAxiosError(error, "listShopifyProducts");
    }
}
async function getShopifyOrder(userId, orderId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/orders/${orderId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response.data, "getShopifyOrder");
    }
    catch (error) {
        return handleAxiosError(error, "getShopifyOrder");
    }
}
async function getTopSellingProducts(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/top-selling-products?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response.data, "getTopSellingProducts");
    }
    catch (error) {
        return handleAxiosError(error, "getTopSellingProducts");
    }
}
async function getShopifyConnectionStatus(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/connection-status?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response.data, "getShopifyConnectionStatus");
    }
    catch (error) {
        return handleAxiosError(error, "getShopifyConnectionStatus");
    }
}
async function disconnectShopify(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/disconnect`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
        });
        return handlePythonApiResponse(response.data, "disconnectShopify");
    }
    catch (error) {
        return handleAxiosError(error, "disconnectShopify");
    }
}
async function updateInventory(userId, variantId, newQuantity) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: "CONFIG_ERROR",
                message: "Python API service URL is not configured.",
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/shopify/update-inventory`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            variant_id: variantId,
            new_quantity: newQuantity,
        });
        return handlePythonApiResponse(response.data, "updateInventory");
    }
    catch (error) {
        return handleAxiosError(error, "updateInventory");
    }
}
//# sourceMappingURL=shopifySkills.js.map