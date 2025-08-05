import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// Video creation API integration for marketing automation
export interface VideoCreationRequest {
  type: 'promo' | 'social_ad' | 'product_demo' | 'story' | 'reel';
  title: string;
  description?: string;
  duration: number; // seconds
  style: 'professional' | 'casual' | 'energetic' | 'minimal' | 'trendy';
  visual_assets: {
    images: string[];
    video_clips: string[];
    product_data?: any;
  };
  audio_assets?: {
    background_music_url?: string;
    voiceover_text?: string;
  };
  brand_assets?: {
    logo_url: string;
    brand_colors: string[];
    font_style: string;
  };
  target_platform: 'instagram' | 'tiktok' | 'facebook' | 'youtube' | 'linkedin';
  aspect_ratio: '16:9' | '9:16' | '1:1' | '4:5';
  includes_captions?: boolean;
  includes_hashtags?: boolean;
}

export interface VideoResult {
  id: string;
  url: string;
  thumbnail_url: string;
  file_size: number;
  metadata: {
    duration: number;
    resolution: string;
    codec: string;
    fps: number;
  };
}

export interface VideoEditingOptions {
  trim_start?: number;
  trim_end?: number;
  add_text_overlays?: {
    text: string;
    position: { x: number; y: number };
    duration: { start: number; end: number };
    style: object;
  }[];
  add_transitions?: {
    type: string;
    duration: number;
    position: number;
  }[];
  color_correction?: object;
  audio_enhancement?: object;
}

function handlePythonApiResponse<T>(
  response: any,
  operationName: string
): SkillResponse<T> {
  if (response.data && response.data.ok && response.data.data) {
    return { ok: true, data: response.data.data };
  }
  logger.warn(`[${operationName}] Failed API call.`, response.data?.error);
  return {
    ok: false,
    error: {
      code: response.data?.error?.code || 'PYTHON_API_ERROR',
      message: response.data?.error?.message || `Failed to ${operationName}.`,
      details: response.data?.error?.details,
    },
  };
}

function handleAxiosError(
  error: AxiosError,
  operationName: string
): SkillResponse<null> {
  if (error.response) {
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}.`,
      },
    };
  }
  return {
    ok: false,
    error: {
      code: 'NETWORK_ERROR',
      message: `Error: ${error.message}`,
    },
  };
}

// Video creation and editing services
export async function createMarketingVideo(
  userId: string,
  videoRequest: VideoCreationRequest
): Promise<SkillResponse<VideoResult>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/videos/create`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      video_request: videoRequest,
    });
    return handlePythonApiResponse(response, 'createMarketingVideo');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createMarketingVideo');
  }
}

export async function editExistingVideo(
  userId: string,
  videoId: string,
  editingOptions: VideoEditingOptions
): Promise<SkillResponse<VideoResult>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
+        message: 'Python API service URL is not configured.',
+      },
+    };
+  }
+  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/videos/edit/${videoId}`;
+
+  try {
+    const response = await axios.put(endpoint, {
+      user_id: userId,
+      options: editingOptions,
+    });
+    return handlePythonApiResponse(response, 'editExistingVideo');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'editExistingVideo');
+  }
+}
+
+export async function generateVideoFromProduct(
+  userId: string,
+  platform: string,
+  productData: any
+): Promise<SkillResponse<VideoResult>> {
+  if (!PYTHON_API_SERVICE_BASE_URL) {
+    return {
+      ok: false,
+      error: {
+        code: 'CONFIG_ERROR',
+        message: 'Python API service URL is not configured.',
+      },
+    };
+  }
+  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/videos/generate-from-product`;
+
+  try {
+    const response = await axios.post(endpoint, {
+      user_id: userId,
+      platform,
+      product_data: productData,
+    });
+    return handlePythonApiResponse(response, 'generateVideoFromProduct');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'generateVideoFromProduct');
+  }
+}
+
+export async function createSocialMediaVideo(
+  userId: string,
+  platform: 'instagram' | 'tiktok' | 'facebook' | 'youtube' | 'linkedin',
+  content: string,
+  visualAssets?: any,
+  audioAssets?: any
+): Promise<SkillResponse<VideoResult>> {
+  const videoRequest: VideoCreationRequest = {
+    type: 'social_ad',
+    title: `Social media post for ${platform}`,
+    duration: platform === 'tiktok' ? 15 : platform === 'instagram-story' ? 7 : 60,
+    style: 'trendy',
+    visual_assets: {
+      images: visualAssets?.images || [],
+      video_clips: visualAssets?.video_clips || [],
+    },
+    audio_assets: audioAssets,
+    target_platform: platform,
+    aspect_ratio: platform === 'tiktok' ? '9:16' : platform === 'instagram' ? '1:1' : '16:9',
+    includes_captions: true,
+    includes_hashtags: true,
+  };
+
+  return await createMarketingVideo(userId, videoRequest);
+}
+
+// Handler functions for NLU integration
+export async function handleCreateMarketingVideo(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const type = entities.type || entities.videoType || 'promo';
+    const title = entities.title || entities.name || 'Marketing Video';
+    const platform = entities.platform || entities.targetPlatform || 'instagram';
+    const duration = parseInt(entities.duration) || 30;
+    const style = entities.style || entities.theme || 'professional';
+
+    const videoRequest: VideoCreationRequest = {
+      type: type as any,
+      title,
+      duration,
+      style: style as any,
+      target_platform: platform as any,
+      aspect_ratio: platform === 'tiktok' ? '9:16' : '1:1',
+      visual_assets: {
+        images: entities.images ? entities.images.split(',') : [],
+        video_clips: entities.videoClips ? entities.videoClips.split(',') : [],
+      },
+      includes_captions: true,
+      includes_hashtags: true,
+    };
+
+    if (entities.audioUrl) {
+      videoRequest.audio_assets = { background_music_url: entities.audioUrl };
+    }
+    if (entities.voiceoverText) {
+      videoRequest.audio_assets = { ...videoRequest.audio_assets, voiceover_text: entities.voiceoverText };
+    }
+
+    const result = await createMarketingVideo(userId, videoRequest);
+    if (result.ok) {
+      return `Created ${type} video for ${platform}: "${title}" - ${result.data.url}`;
+    } else {
+      return `Error creating video: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error creating marketing video: ${error.message}`;
+  }
+}
+
+export async function handleGenerateProductVideo(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const productId = entities.productId || entities.product;
+    const platform = entities.platform || 'instagram';
+
+    if (!productId) {
+      return 'Please specify a product ID for video generation';
+    }
+
+    const result = await generateVideoFromProduct(userId, platform, { product_id: productId });
+    if (result.ok) {
+      return `Generated product promotional video for ${platform}: ${result.data.url}`;
+    } else {
+      return `Error generating product video: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error generating product video: ${error.message}`;
+  }
+}
+
+export async function handleSocialVideoCreation(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const platform = entities.platform || entities.social || 'tiktok';
+    const content = entities.content || entities.text || '';
+    const images = entities.images ? entities.images.split(',') : [];
+    const videoClips = entities.videos ? entities.videos.split(',') : [];
+
+    const result = await createSocialMediaVideo(
+      userId,
+      platform,
+      content,
+      { images, video_clips: videoClips }
+    );
+    if (result.ok) {
+      return `Created ${platform} video: "${content.substring(0, 50)}..." - ${result.data.url}`;
+    } else {
+      return `Error creating social video: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error creating social video: ${error.message}`;
+  }
+}
