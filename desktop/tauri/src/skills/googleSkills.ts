// Google Workspace Skills Index
export { GmailSkill, type GmailListAction, type GmailSendAction, type GmailSearchAction, type GmailReadAction, type GmailMarkAction, type GmailDeleteAction, type GmailReplyAction, type GoogleEmail, type GoogleEmailAttachment } from './googleGmailSkill';
export { GoogleCalendarSkill, type GoogleCalendarListAction, type GoogleCalendarEventsAction, type GoogleCalendarCreateAction, type GoogleCalendarUpdateAction, type GoogleCalendarDeleteAction, type GoogleCalendar, type GoogleCalendarEvent, type GoogleEventAttendee } from './googleCalendarSkill';
export { GoogleDriveSkill, type GoogleDriveListAction, type GoogleDriveSearchAction, type GoogleDriveCreateAction, type GoogleDriveCreateFolderAction, type GoogleDriveDeleteAction, type GoogleDriveShareAction, type GoogleDriveFile, type GoogleDrivePermission, type GoogleDriveFolder } from './googleDriveSkill';

// Re-export all Google types
export type {
  GoogleUser,
  GoogleSearchResult,
  GoogleEventOrganizer,
  GoogleEventAttachment,
  GoogleCalendarAclRule,
  GoogleCalendarColor,
  GoogleCalendarList,
  GoogleEventsList,
  GoogleEventReminder,
  GoogleDriveUploadResult,
  GoogleDriveFileList,
  GoogleDriveSearchResult,
  GoogleDriveShareResult,
  GoogleOAuthToken,
  GoogleOAuthUrlResponse,
  GoogleOAuthCallbackResponse,
  GoogleConnectionStatus,
  GoogleApiError
} from './googleGmailSkill';

// Create type aliases for all action types
export type GmailActions = GmailListAction | GmailSendAction | GmailSearchAction | GmailReadAction | GmailMarkAction | GmailDeleteAction | GmailReplyAction;
export type GoogleCalendarActions = GoogleCalendarListAction | GoogleCalendarEventsAction | GoogleCalendarCreateAction | GoogleCalendarUpdateAction | GoogleCalendarDeleteAction;
export type GoogleDriveActions = GoogleDriveListAction | GoogleDriveSearchAction | GoogleDriveCreateAction | GoogleDriveCreateFolderAction | GoogleDriveDeleteAction | GoogleDriveShareAction;
export type GoogleSkillsActions = GmailActions | GoogleCalendarActions | GoogleDriveActions;

// Google Skills Registry
export const googleSkills = [
  GmailSkill,
  GoogleCalendarSkill,
  GoogleDriveSkill
];

export default {
  skills: googleSkills,
  GmailSkill,
  GoogleCalendarSkill,
  GoogleDriveSkill
};