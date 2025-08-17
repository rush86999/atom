import axios, { AxiosError } from 'axios';

const shopifyStoreUrl = 'YOUR_SHOPIFY_STORE_URL';
const shopifyAccessToken = 'YOUR_ACCESS_TOKEN';

interface InventoryLevel {
  inventory_item_id: string;
  available: number;
}

interface ResponseData {
  // Define the structure of the response data as needed
  inventory_level: InventoryLevel;
}

async function updateInventory(variantId: string, newQuantity: number): Promise<ResponseData> {
  try {
    const response = await axios.post<ResponseData>(`${shopifyStoreUrl}/admin/api/2023-01/inventory_levels/set.json`, {
      inventory_level: {
        inventory_item_id: variantId,
        available: newQuantity
      }
    }, {
      headers: {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': shopifyAccessToken
      }
    });
    console.log('Inventory updated successfully:', response.data);
    return response.data;
  } catch (error: any) { // AxiosError is not a valid type for catch clause
    console.error('Error updating inventory:', error);
    throw error; // Rethrow the error to handle it upstream
  }
}

// Example usage:
// updateInventory('VARIANT_ID', 10).then(data => console.log(data)).catch(error => console.error(error));
