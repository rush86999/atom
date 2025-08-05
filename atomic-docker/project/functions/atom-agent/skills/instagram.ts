import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// Instagram Business API integration
export interface InstagramPost {
  id: string;
  caption: string;
  media_url: string;
  permalink: string;
  timestamp: string;
  like_count: number;
  comments_count: number;
}

export interface InstagramStory {
  id: string;
  media_url: string;
  permalink: string;
  timestamp: string;
  expires_at: string;
}

export interface InstagramStoryMetric {
  exits: number;
  impressions: number;
  replies: number;
  taps_forward: number;
  taps_back: number;
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

export async function createInstagramPost(
  userId: string,
  postData: { caption: string; media_url: string; hashtags?: string[] }
): Promise<SkillResponse<{ id: string; permalink: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/instagram/post`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      caption: postData.caption,
      media_url: postData.media_url,
      hashtags: postData.hashtags || [],
    });
    return handlePythonApiResponse(response, 'createInstagramPost');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createInstagramPost');
  }
}

export async function getInstagramInsights(
  userId: string,
  period: string = '7d'
): Promise<SkillResponse<{ reach: number; impressions: number; followers: number }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/instagram/insights?user_id=${userId}&period=${period}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getInstagramInsights');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getInstagramInsights');
  }
}

export async function scheduleInstagramPost(
  userId: string,
  postData: { caption: string; media_url: string; scheduled_time: string; hashtags?: string[] }
): Promise<SkillResponse<{ id: string; scheduled_time: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/instagram/schedule`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      ...postData,
    });
    return handlePythonApiResponse(response, 'scheduleInstagramPost');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'scheduleInstagramPost');
  }
}

export async function getInstagramPosts(
  userId: string,
  limit: number = 10
): Promise<SkillResponse<{ posts: InstagramPost[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
+      ok: false,
+      error: {
+        code: 'CONFIG_ERROR',
+        message: 'Python API service URL is not configured.',
+      },
+    };
+  }
+  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/instagram/posts?user_id=${userId}&limit=${limit}`;
+
+  try {
+    const response = await axios.get(endpoint);
+    return handlePythonApiResponse(response, 'getInstagramPosts');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'getInstagramPosts');
+  }
+}
+
+// Handler functions for NLU integration
+export async function handleCreateInstagramPost(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const caption = entities.caption || entities.text || entities.content;
+    const mediaUrl = entities.mediaUrl || entities.image || entities.picture;
+    const hashtags = entities.hashtags ? entities.hashtags.split(' ') : [];
+
+    if (!caption || !mediaUrl) {
+      return 'Please provide caption and media URL for Instagram post';
+    }
+
+    const result = await createInstagramPost(userId, { caption, media_url: mediaUrl, hashtags });
+    if (result.ok) {
+      return `Created Instagram post: "${caption.substring(0, 50)}..." - ${result.data.permalink}`;
+    } else {
+      return `Error creating Instagram post: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error creating Instagram post: ${error.message}`;
+  }
+}
+
+export async function handleScheduleInstagramPost(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const caption = entities.caption || entities.text || entities.content;
+    const mediaUrl = entities.mediaUrl || entities.image || entities.picture;
+    const scheduledTime = entities.time || entities.when || entities.schedule;
+    const hashtags = entities.hashtags ? entities.hashtags.split(' ') : [];
+
+    if (!caption || !mediaUrl || !scheduledTime) {
+      return 'Please provide caption, media URL, and scheduled time for Instagram post';
+    }
+
+    const result = await scheduleInstagramPost(userId, {
+      caption,
+      media_url: mediaUrl,
+      scheduled_time: scheduledTime,
+      hashtags
+    });
+    if (result.ok) {
+      return `Scheduled Instagram post for ${scheduledTime}: "${caption.substring(0, 30)}..."`;
+    } else {
+      return `Error scheduling Instagram post: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error scheduling Instagram post: ${error.message}`;
+  }
+}
+
+export async function handleInstagramAnalytics(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const period = entities.period || entities.duration || '7d';
+    const result = await getInstagramInsights(userId, period);
+    if (result.ok) {
+      const insights = result.data;
+      return `Instagram Last ${period}: ${insights.reach.toLocaleString()} reach, ${insights.impressions.toLocaleString()} impressions, ${insights.followers.toLocaleString()} followers`;
+    } else {
+      return `Error getting Instagram insights: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error getting Instagram analytics: ${error.message}`;
+  }
+}
