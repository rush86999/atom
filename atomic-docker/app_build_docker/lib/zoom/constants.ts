export const zoomApiUrl = 'https://api.zoom.us/v2';
export const zoomCreateMeetingUrl =
  process.env.NEXT_PUBLIC_ZOOM_CREATE_MEETING_URL;
export const zoomUpdateMeetingUrl =
  process.env.NEXT_PUBLIC_ZOOM_UPDATE_MEETING_URL;
export const zoomDeleteMeetingUrl =
  process.env.NEXT_PUBLIC_ZOOM_DELETE_MEETING_URL;
export const zoomName = 'Zoom Meeting';
export const zoomResourceName = 'zoom';
export const zoomOAuthStartUrl = process.env.NEXT_PUBLIC_ZOOM_OAUTH_START_URL;
// ANDROID
// atomiclife
// IOS
// atomiclife.auth
export const meetingType = {
  instant: 1,
  scheduled: 2,
  recurring_no_fixed: 3,
  recurring_fixed: 8,
};

export const urlScheme = 'atomiclife';

export const getDeepLink = (path = '') => {
  const scheme = urlScheme;
  const prefix = `${scheme}://`;
  return prefix + path;
};
