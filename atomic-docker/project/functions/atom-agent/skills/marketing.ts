import {
  createMailchimpCampaignFromSalesforceCampaign,
  getMailchimpCampaignSummary,
  createTrelloCardFromMailchimpCampaign
} from './marketingManager';

import {
  createDripCampaign,
  getCampaignStatus
} from './marketingAutomation';

import {
  createLinkedInPost,
  getLinkedInAnalytics
} from './linkedin';

import {
  createTweet,
  getTwitterAnalytics
} from './twitter';

import {
  createSocialMediaPost,
  scheduleSocialMediaPost,
  getSocialMediaAnalytics
} from './socialMedia';

import {
  createBlogPost,
  optimizeContentSEO,
  generateNewsletter
} from './contentCreation';

import {
  createMarketingCampaign,
  analyzeCampaignPerformance,
  generateMarketingReport
} from './contentMarketer';

// Centralized marketing handler functions for NLU integration

export async function handleCreateMarketingCampaign(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const campaignData = {
      name: entities.name || entities.campaignName,
      type: entities.type || entities.campaignType || 'email',
      channels: entities.channels || [entities.platform || 'email'],
      target: entities.target || entities.audience || 'all_customers',
      budget: entities.budget
    };

    const result = await createMarketingCampaign(userId, campaignData);
    if (result.ok) {
      return `Created marketing campaign: ${campaignData.name}`;
    } else {
      return `Error creating campaign: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error creating marketing campaign: ${error.message}`;
  }
}

export async function handleCreateDripCampaign(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const campaignName = entities.name || entities.campaignName || 'Drip Campaign';
    const targetAudience = entities.audience || entities.target || 'new_signups';
    const emailSequence = entities.emails || entities.sequence || ['welcome_mail', 'follow_up_mail'];

    const result = await createDripCampaign(userId, campaignName, targetAudience, emailSequence);
    if (result.ok) {
      return `Created drip campaign: ${campaignName} for ${targetAudience}`;
    } else {
      return `Error creating drip campaign: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error creating drip campaign: ${error.message}`;
  }
}

export async function handleGetCampaignStatus(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const campaignId = entities.campaignId || entities.id;
    if (!campaignId) {
      return 'Please provide a campaign ID to check status';
    }

    const result = await getCampaignStatus(userId, campaignId);
    if (result.ok) {
      const status = result.data;
      return `Campaign ${campaignId}: ${status.name} - Status: ${status.status} - ${status.recipients || 0} recipients`;
    } else {
      return `Error checking campaign: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error checking campaign: ${error.message}`;
  }
}

export async function handleCreateSocialPost(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const content = entities.content || entities.text || entities.post;
    const platform = entities.platform || entities.channel || 'linkedIn';

    let result;
    switch (platform.toLowerCase()) {
      case 'linkedin':
        result = await createLinkedInPost(userId, content);
        break;
      case 'twitter':
        result = await createTweet(userId, content);
        break;
      default:
        result = await createSocialMediaPost(userId, content, platform);
    }

    if (result.ok) {
      return `Posted to ${platform}: "${content.substring(0, 50)}..."`;
    } else {
      return `Error posting to ${platform}: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error creating social post: ${error.message}`;
  }
}

export async function handleGenerateContent(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const topic = entities.topic || entities.subject;
    const format = entities.format || entities.type || 'blog';

    let result;
    switch (format.toLowerCase()) {
      case 'newsletter':
        result = await generateNewsletter(userId, topic);
        break;
      case 'blog':
        result = await createBlogPost(userId, { title: topic });
        break;
      default:
        result = await createContent(userId, topic, format);
    }

    if (result.ok) {
      return `Generated ${format} content for: ${topic}`;
    } else {
      return `Error generating content: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error generating content: ${error.message}`;
  }
}

export async function handleCampaignFromShopify(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const productId = entities.productId || entities.product;

    // Create content from Shopify product data
    const campaign = {
      source: 'shopify',
      product_id: productId,
      channels: entities.channels || ['email', 'social'],
      automation: true
    };

    const result = await createMailchimpCampaignFromSalesforceCampaign(userId, productId);
    if (result.ok) {
      return `Created marketing campaign for Shopify product: ${productId}`;
    } else {
      return `Error creating campaign: ${result.error?.message}`;
    }
  } catch (error: any) {
    return `Error creating campaign from Shopify: ${error.message}`;
  }
}
