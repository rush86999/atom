const axios = require('axios');
const shopifyStoreUrl = 'YOUR_SHOPIFY_STORE_URL';
const shopifyAccessToken = 'YOUR_ACCESS_TOKEN';

async function updateInventory(variantId, newQuantity) {
  try {
    const response = await axios.post(`${shopifyStoreUrl}/admin/api/2023-01/inventory_levels/set.json`, {
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
  } catch (error) {
    console.error('Error updating inventory:', error);
  }
}

// Example usage:
updateInventory('VARIANT_ID', 10);
