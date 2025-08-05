import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// TikTok Business API integration
export interface TikTokVideo {
  id: string;
  title: string;
  description: string;
  media_url: string;
  cover_url: string;
  created_time: string;
  duration: number;
  view_count: number;
  like_count: number;
  comment_count: number;
  share_count: number;
}

export interface TikTokAnalytics {
  views: number;
  likes: number;
  comments: number;
  shares: number;
  average_watch_time: number;
  completion_rate: number;
  click_through_rate: number;
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
+      message: `Error: ${error.message}`,
+    },
+  };
+}
+
+export async function createTikTokUpload(
+  userId: string,
+  uploadData: { title: string; description: string; video_url: string; hashtags?: string[] }
+): Promise<SkillResponse<{ id: string; upload_url: string }>> {
+  if (!PYTHON_API_SERVICE_BASE_URL) {
+    return {
+      ok: false,
+      error: {
+        code: 'CONFIG_ERROR',
+        message: 'Python API service URL is not configured.',
+      },
+    };
+  }
+  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/tiktok/upload`;
+
+  try {
+    const response = await axios.post(endpoint, {
+      user_id: userId,
+      title: uploadData.title,
+      description: uploadData.description,
+      video_url: uploadData.video_url,
+      hashtags: uploadData.hashtags || [],
+    });
+    return handlePythonApiResponse(response, 'createTikTokUpload');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'createTikTokUpload');
+  }
+}
+
+export async function getTikTokAnalytics(
+  userId: string,
+  period: string = '7d'
+): Promise<SkillResponse<TikTokAnalytics>> {
+  if (!PYTHON_API_SERVICE_BASE_URL) {
+    return {
+      ok: false,
+      error: {
+        code: 'CONFIG_ERROR',
+        message: 'Python API service URL is not configured.',
+      },
+    };
+  }
+  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/tiktok/analytics?user_id=${userId}&period=${period}`;
+
+  try {
+    const response = await axios.get(endpoint);
+    return handlePythonApiResponse(response, 'getTikTokAnalytics');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'getTikTokAnalytics');
+  }
+}
+
+// Handler functions for NLU integration
+export async function handleUploadTikTokVideo(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const title = entities.title || entities.caption || 'New TikTok Video';
+    const description = entities.description || entities.text || '';
+    const videoUrl = entities.videoUrl || entities.video || entities.url;
+    const hashtags = entities.hashtags ? entities.hashtags.split(' ') : [];
+
+    if (!videoUrl) {
+      return 'Please provide a video URL for TikTok upload';
+    }
+
+    const result = await createTikTokUpload(userId, {
+      title,
+      description,
+      video_url: videoUrl,
+      hashtags
+    });
+    if (result.ok) {
+      return `Created TikTok upload: "${title}" - Upload URL: ${result.data.upload_url}`;
+    } else {
+      return `Error creating TikTok upload: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error creating TikTok upload: ${error.message}`;
+  }
+}
+
+export async function handleTikTokAnalytics(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const period = entities.period || entities.duration || '7d';
+    const result = await getTikTokAnalytics(userId, period);
+    if (result.ok) {
+      const analytics = result.data;
+      return `TikTok Analytics (${period}): ${analytics.views} views, ${analytics.likes} likes, ${analytics.shares} shares, ${(analytics.completion_rate * 100).toFixed(1)}% completion rate`;
+    } else {
+      return `Error getting TikTok analytics: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error getting TikTok analytics: ${error.message}`;
+  }
+}
