import { SkillResponse, ShopifyProduct, ShopifyOrder } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function listShopifyProducts(userId: string): Promise<SkillResponse<{
    products: ShopifyProduct[];
}>>;
export declare function getShopifyOrder(userId: string, orderId: string): Promise<SkillResponse<ShopifyOrder>>;
export declare function getShopifyConnectionStatus(userId: string): Promise<SkillResponse<{
    isConnected: boolean;
    shopUrl?: string;
}>>;
export declare function disconnectShopify(userId: string): Promise<SkillResponse<null>>;
