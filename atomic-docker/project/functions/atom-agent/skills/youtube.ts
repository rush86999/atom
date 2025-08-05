import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

// YouTube API integration for marketing automation
export interface YouTubeVideo {
  id: string;
  title: string;
  description: string;
  thumbnails: {
    default: string;
    medium?: string;
    high?: string;
  };
  duration: string;
  publishedAt: string;
  viewCount: number;
  likeCount: number;
  commentCount: number;
}

export interface YouTubeChannel {
  id: string;
  title: string;
  description: string;
  thumbnails: {
    default: string;
    medium?: string;
    high?: string;
  };
  subscriberCount: number;
  videoCount: number;
}

export interface YouTubeUploadRequest {
  title: string;
  description: string;
  video_url: string;
  tags: string[];
  category_id: string;
  privacy_status: 'public' | 'unlisted' | 'private';
  thumbnail_url?: string;
  playlist_ids?: string[];
}

export interface YouTubeAnalytics {
  views: number;
  likes: number;
  dislikes: number;
  comments: number;
  subscribe_count: number;
  watch_time: number; // in hours
  average_view_duration: number; // in minutes
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

// YouTube API methods
export async function uploadYouTubeVideo(
  userId: string,
  videoData: YouTubeUploadRequest
): Promise<SkillResponse<{ id: string; url: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/youtube/videos/upload`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      ...videoData,
    });
    return handlePythonApiResponse(response, 'uploadYouTubeVideo');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'uploadYouTubeVideo');
  }
}

export async function createYouTubePlaylist(
  userId: string,
  playlistData: { title: string; description: string; privacy_status: 'public' | 'unlisted' | 'private' }
): Promise<SkillResponse<{ id: string; title: string }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/youtube/playlists`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      ...playlistData,
    });
    return handlePythonApiResponse(response, 'createYouTubePlaylist');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createYouTubePlaylist');
  }
}

export async function getYouTubeChannelAnalytics(
  userId: string,
  period: string = '7d'
): Promise<SkillResponse<YouTubeAnalytics>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/youtube/analytics?user_id=${userId}&period=${period}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getYouTubeChannelAnalytics');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getYouTubeChannelAnalytics');
  }
}

export async function getYouTubeVideos(
  userId: string,
  limit: number = 10,
  playlist_id?: string
): Promise<SkillResponse<{ videos: YouTubeVideo[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  let endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/youtube/videos?user_id=${userId}&limit=${limit}`;
  if (playlist_id) {
    endpoint += `&playlist_id=${playlist_id}`;
  }

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getYouTubeVideos');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getYouTubeVideos');
  }
}

export async function addVideoToPlaylist(
  userId: string,
  videoId: string,
  playlistIds: string[],
  position: number = 0
): Promise<SkillResponse<{ success: boolean }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/youtube/playlist/add`;

  try {
+    const response = await axios.post(endpoint, {
+      user_id: userId,
+      video_id: videoId,
+      playlist_ids: playlistIds,
+      position,
+    });
+    return handlePythonApiResponse(response, 'addVideoToPlaylist');
+  } catch (error) {
+    return handleAxiosError(error as AxiosError, 'addVideoToPlaylist');
+  }
+}
+
+// Handler functions for NLU integration
+export async function handleUploadYouTubeVideo(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const title = entities.title || entities.videoTitle || 'New Video';
+    const description = entities.description || entities.videoDescription || '';
+    const videoUrl = entities.videoUrl || entities.video || entities.url;
+    const tags = entities.tags ? entities.tags.split(',') : [];
+    const category_id = entities.category || entities.videoCategory || '22'; // People & Blogs
+    const privacy_status = entities.privacy || entities.visibility || 'public';
+
+    if (!videoUrl) {
+      return 'Please provide a video URL for YouTube upload';
+    }
+
+    const videoData: YouTubeUploadRequest = {
+      title,
+      description,
+      video_url: videoUrl,
+      tags,
+      category_id,
+      privacy_status,
+      playlist_ids: entities.playlistIds ? entities.playlistIds.split(',') : [],
+    };
+
+    const result = await uploadYouTubeVideo(userId, videoData);
+    if (result.ok) {
+      return `Uploaded YouTube video: "${title}" - ${result.data.url}`;
+    } else {
+      return `Error uploading YouTube video: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error uploading YouTube video: ${error.message}`;
+  }
+}
+
+export async function handleCreateYouTubePlaylist(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const title = entities.title || entities.playlistName || 'New Playlist';
+    const description = entities.description || entities.playlistDescription || '';
+    const privacy_status = entities.privacy || entities.visibility || 'public';
+
+    const result = await createYouTubePlaylist(userId, {
+      title,
+      description,
+      privacy_status: privacy_status as any,
+    });
+    if (result.ok) {
+      return `Created YouTube playlist: "${title}"`;
+    } else {
+      return `Error creating YouTube playlist: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error creating YouTube playlist: ${error.message}`;
+  }
+}
+
+export async function handleYouTubeAnalytics(
+  userId: string,
+  entities: any
+): Promise<string> {
+  try {
+    const period = entities.period || entities.duration || '7d';
+    const result = await getYouTubeChannelAnalytics(userId, period);
+    if (result.ok) {
+      const analytics = result.data;
+      return `YouTube Analytics (${period}): ${analytics.views.toLocaleString()} views, ${analytics.likes?.toLocaleString()} likes, ${analytics.comments?.toLocaleString()} comments, Watch time: ${analytics.watch_time}h`;
+    } else {
+      return `Error getting YouTube analytics: ${result.error.message}`;
+    }
+  } catch (error: any) {
+    return `Error getting YouTube analytics: ${error.message}`;
+  }
+}
