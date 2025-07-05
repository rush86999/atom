import OpenAI from 'openai';
import got from 'got';
import dayjs from 'dayjs';
import timezonePlugin from 'dayjs/plugin/timezone';
import utcPlugin from 'dayjs/plugin/utc';
import customParseFormatPlugin from 'dayjs/plugin/customParseFormat';
import isBetweenPlugin from 'dayjs/plugin/isBetween';
import { google, Auth } from 'googleapis';
import { v4 as uuidv4 } from 'uuid';
import _ from 'lodash';
import { sendEmail } from '@/_utils/email/email';

dayjs.extend(utcPlugin);
dayjs.extend(timezonePlugin);
dayjs.extend(customParseFormatPlugin);
dayjs.extend(isBetweenPlugin);


// --- Types (Consolidated) ---
interface SuccessResponseType<T> { success: true; data: T; }
interface GenericSuccessResponse { success: true; }
interface FailureResponseType { success: false; error: { message: string; details?: any; rawResponse?: string; parsedResponse?: any; }; }
interface OpenAIErrorResponse { type: 'OPENAI_API_ERROR'; status: number; data: any; message: string; }
interface OpenAIRequestErrorResponse { type: 'OPENAI_REQUEST_ERROR'; message: string; }
interface OpenAISuccessResponse { success: true; content: string | null | undefined; }
interface OpenAIFailureResponse { success: false; error: OpenAIErrorResponse | OpenAIRequestErrorResponse; }
type CallOpenAIResponse = OpenAISuccessResponse | OpenAIFailureResponse;
export interface CalendarIntegrationType { id: string; userId: string; clientType: 'ios' | 'android' | 'web' | 'atomic-web'; token: string | null; refreshToken: string | null; expiresAt: string | null; resource: string; syncEnabled?: boolean; primaryCalendarId?: string; }
export interface GoogleTokenResponseType { access_token: string; expires_in: number; scope?: string; token_type?: string; id_token?: string; }
interface CreateGoogleEventSuccessData { id: string; googleEventId: string; generatedId: string; calendarId: string; generatedEventId?: string; }
type CreateGoogleEventResponse = | { success: true, data: CreateGoogleEventSuccessData } | FailureResponseType;
export interface EventType { id: string; userId: string; calendarId: string; gEventId?: string | null; provider?: string | null; summary?: string | null; description?: string | null; startDateTime?: string | null; endDateTime?: string | null; timezone?: string | null; status?: string | null; isDeleted?: boolean | null; parentEventId?: string | null; taskId?: string | null; projectId?: string | null; createdAt?: string; updatedAt?: string; }
export interface GlobalCalendarType extends CalendarIntegrationType {}
export interface UserPreferenceType { id: string; userId: string; somePreference?: string; workHoursStartTime?: string; workHoursEndTime?: string; workDays?: number[]; slotDuration?: number; timezone?: string; bufferBetweenMeetings?: number; } // Added fields for availability
interface EventInput extends Partial<Omit<EventType, 'id' | 'createdAt' | 'updatedAt'>> { id?: string; userId: string; calendarId: string; summary: string; startDateTime: string; endDateTime: string; timezone: string; }
interface UpsertEventsResponseData { affected_rows: number; returning: { id: string; [key: string]: any }[]; }
type UpsertEventsPostPlannerResponse = | SuccessResponseType<UpsertEventsResponseData> | FailureResponseType;
type EmailResponse = GenericSuccessResponse | FailureResponseType;
interface AvailabilitySlot { startDate: string; endDate: string; } // ISO strings in UTC
interface ParsedScheduleTask { start_time: string; end_time: string; task: string; description?: string; }

// --- OpenAI Client Setup ---
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// --- Helper Function Implementations (condensed, from previous steps) ---
import retry from 'async-retry'; // Import async-retry

// Standard retry configuration for got
const defaultGotRetryConfig = {
  limit: 3,
  methods: ['GET', 'POST', 'PUT', 'HEAD', 'DELETE', 'OPTIONS', 'TRACE'], // Retrying POST/PUT for Hasura assuming idempotency or acceptance
  statusCodes: [408, 429, 500, 502, 503, 504],
  errorCodes: ['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'],
  calculateDelay: ({attemptCount}: {attemptCount: number}) => {
    // console.warn(`Retrying got request, attempt ${attemptCount}`); // Placeholder for proper logger
    return Math.pow(2, attemptCount - 1) * 500 + Math.random() * 200; // Exponential backoff with jitter
  }
};

export const callOpenAI = async (systemMessage: string, userMessage: string, exampleInput?: string, exampleOutput?: string, model?: string): Promise<CallOpenAIResponse> => {
  const messages: OpenAI.Chat.Completions.ChatCompletionMessageParam[] = [{ role: 'system', content: systemMessage }];
  if (exampleInput && exampleOutput) { messages.push({ role: 'user', content: exampleInput }); messages.push({ role: 'assistant', content: exampleOutput }); }
  messages.push({ role: 'user', content: userMessage });
  const chosenModel = model || 'gpt-3.5-turbo-1106';
  const operation_name = 'OpenAICall';

  return await retry(
    async (bail, attemptNumber) => {
      try {
        // console.log(`[${operation_name}] Attempt ${attemptNumber} to call OpenAI...`); // Placeholder for logger
        const completion = await openai.chat.completions.create({
          model: chosenModel,
          messages,
          timeout: 20000, // 20s timeout per attempt
        });
        return { success: true, content: completion?.choices?.[0]?.message?.content };
      } catch (error: any) {
        // console.error(`[${operation_name}] Error on attempt ${attemptNumber}:`, error.message); // Placeholder
        if (error.response) { // Error from OpenAI API itself
          // Don't retry on 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found
          if ([400, 401, 403, 404].includes(error.response.status)) {
            // console.warn(`[${operation_name}] Non-retryable OpenAI API error (status ${error.response.status}). Bailing.`); // Placeholder
            bail(error); // Stop retrying for these errors
            // The error thrown by bail will be caught by the outer catch block of async-retry
            // We need to return the structured error from there. This bail just stops retries.
            // To immediately return the structured error, we'd have to throw the structured one here.
            // For now, let bail throw, and the outer catch will format it.
            return; // Should not be reached if bail throws
          }
          // For other API errors (e.g., 429, 5xx), let retry happen
          throw error; // Re-throw to trigger retry
        } else { // Network error or other non-API error
          throw error; // Re-throw to trigger retry
        }
      }
    },
    {
      retries: 3, // Total attempts = initial + 3 retries = 4
      factor: 2,
      minTimeout: 1000, // 1 second
      maxTimeout: 10000, // 10 seconds
      onRetry: (error, attemptNumber) => {
        const logContext: any = {
          operation_name: `${operation_name}_RetryAttempt`,
          attempt: attemptNumber,
          error_message: error.message,
          error_type: error.constructor.name,
        };
        if (error.response && error.response.status) {
          logContext.error_status = error.response.status;
        }
        // This will use global console.warn. Ideally, a passed-in or global Winston logger is used.
        console.warn("Retrying OpenAI call", logContext);
      },
    }
  ).catch(error => { // Catch error from retry (if all retries failed or bailed after `bail(error)` was called)
    const finalErrorContext: any = {
        operation_name: `${operation_name}_FinalFailure`,
        error_message: error.message,
        error_type: error.constructor.name,
        was_bailed: error.bail // async-retry adds `bail` property to error if bail() was called
    };
    if (error.response) { // Error from OpenAI API
      finalErrorContext.error_status = error.response.status;
      finalErrorContext.error_data = error.response.data;
      // console.error("OpenAI API Error after retries or bail", finalErrorContext); // Placeholder
      return { success: false, error: { type: 'OPENAI_API_ERROR', status: error.response.status, data: error.response.data, message: `OpenAI API request failed: ${error.message}` } };
    } else { // Network or other request error
      // console.error("Error calling OpenAI after retries", finalErrorContext); // Placeholder
      return { success: false, error: { type: 'OPENAI_REQUEST_ERROR', message: error.message } };
    }
  });
};

export const getCalendarIntegration = async (userId: string, resource: string): Promise<SuccessResponseType<CalendarIntegrationType | undefined> | FailureResponseType> => {
  const query = `query GetCalendarIntegration($userId: String!, $resource: String!) { Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}, limit: 1) { id userId clientType token refreshToken expiresAt resource syncEnabled primaryCalendarId } }`;
  const operation_name = 'HasuraGetCalendarIntegration';
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query, variables: { userId, resource } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) {
      /* console.error(`[${operation_name}] Hasura API errors:`, body.errors); */
      return { success: false, error: { message: 'Hasura API error during getCalendarIntegration.', details: body.errors } };
    }
    if (!body.data || !body.data.hasOwnProperty('Calendar_Integration')) {
      /* console.warn(`[${operation_name}] Unexpected response structure:`, body); */
      return { success: false, error: { message: 'Unexpected response structure during getCalendarIntegration.', details: body } };
    }
    return { success: true, data: body.data.Calendar_Integration?.[0] };
  } catch (e: any) {
    /* console.error(`[${operation_name}] Network or request error:`, e.message); */
    return { success: false, error: { message: 'Network/request error during getCalendarIntegration.', details: e.message, rawResponse: e.response?.body } };
  }
};

export const refreshGoogleToken = async (refreshTokenVal: string, clientType: CalendarIntegrationType['clientType']): Promise<SuccessResponseType<GoogleTokenResponseType> | FailureResponseType> => {
  const clientId = clientType === 'web' ? process.env.GOOGLE_CLIENT_ID_WEB : process.env.GOOGLE_CLIENT_ID_IOS;
  const clientSecret = clientType === 'web' ? process.env.GOOGLE_CLIENT_SECRET_WEB : process.env.GOOGLE_CLIENT_SECRET_IOS;
  const operation_name = 'GoogleRefreshToken';
  if (!clientId || !clientSecret) {
    const msg = `Google client ID or secret not configured for clientType: ${clientType}`;
    /* console.error(`[${operation_name}] ${msg}`); */
    return { success: false, error: { message: msg } };
  }
  try {
    const response = await got.post('https://oauth2.googleapis.com/token', {
      form: { client_id: clientId, client_secret: clientSecret, refresh_token: refreshTokenVal, grant_type: 'refresh_token' },
      responseType: 'json',
      timeout: { request: 15000 },
      retry: { // Slightly different retry for token refresh if needed, or use default
        limit: 2,
        methods: ['POST'],
        statusCodes: [408, 429, 500, 502, 503, 504],
        errorCodes: ['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'],
        calculateDelay: ({attemptCount}: {attemptCount: number}) => Math.pow(2, attemptCount - 1) * 1000 + Math.random() * 300
      }
    });
    return { success: true, data: response.body as GoogleTokenResponseType };
  } catch (e: any) {
    /* console.error(`[${operation_name}] Error refreshing Google token:`, e.message, e.response?.body); */
    return { success: false, error: { message: 'Failed to refresh Google token: ' + e.message, details: e.response?.body } };
  }
};

export const updateCalendarIntegration = async (id: string, token: string | null, expiresAt: string | null, refreshTokenVal?: string | null, syncEnabled?: boolean): Promise<GenericSuccessResponse | FailureResponseType> => {
  const operation_name = 'HasuraUpdateCalendarIntegration';
  let setClause = '_set: {';
  if (token !== undefined) setClause += `token: $token, `;
  if (expiresAt !== undefined) setClause += `expiresAt: $expiresAt, `;
  if (refreshTokenVal !== undefined) setClause += `refreshToken: $refreshToken, `;
  if (typeof syncEnabled === 'boolean') setClause += `syncEnabled: $syncEnabled, `;
  setClause += `updatedAt: "now()" }`;

  const mutation = `mutation UpdateCalendarIntegration($id: uuid!, ${token !== undefined ? '$token: String,' : ''} ${expiresAt !== undefined ? '$expiresAt: timestamptz,' : ''} ${refreshTokenVal !== undefined ? '$refreshToken: String,' : ''} ${typeof syncEnabled === 'boolean' ? '$syncEnabled: Boolean,' : ''}) { update_Calendar_Integration_by_pk(pk_columns: {id: $id}, ${setClause}) { id } }`;
  const variables: any = { id };
  if (token !== undefined) variables.token = token;
  if (expiresAt !== undefined) variables.expiresAt = expiresAt;
  if (refreshTokenVal !== undefined) variables.refreshToken = refreshTokenVal;
  if (typeof syncEnabled === 'boolean') variables.syncEnabled = syncEnabled;

  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query: mutation, variables },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during updateCalendarIntegration.', details: body.errors } }; }
    if (!body.data || !body.data.update_Calendar_Integration_by_pk) { /* console.warn(`[${operation_name}] Unexpected response:`, body); */ return { success: false, error: { message: 'Unexpected response structure or ID not found during updateCalendarIntegration.', details: body } }; }
    return { success: true };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during updateCalendarIntegration.', details: e.message, rawResponse: e.response?.body } }; }
};

export const getGoogleAPIToken = async (userId: string, resource: string): Promise<{success: true, token: string} | FailureResponseType> => { /* ... */
  const iResult = await getCalendarIntegration(userId, resource); if (!iResult.success) return { success: false, error: { message: 'Failed to acquire Google API token: Could not get calendar integration', details: iResult.error } };
  const int = iResult.data; if (!int) return { success: false, error: { message: 'Failed to acquire Google API token: No calendar integration found.' } };
  if (int.token && int.expiresAt && dayjs(int.expiresAt).isAfter(dayjs().add(5, 'minutes'))) return { success: true, token: int.token };
  if (!int.refreshToken) { /* console.warn(`User ${userId} resource ${resource} needs refresh but no refresh token.`); */ if (int.id && int.syncEnabled !== false) await updateCalendarIntegration(int.id, null, null, null, false).catch(e => console.warn("Failed to disable sync:", e.message)); return { success: false, error: { message: 'Refresh needed but no refresh token available.' } }; }
  const rResult = await refreshGoogleToken(int.refreshToken, int.clientType); if (!rResult.success) { if (int.id && int.syncEnabled !== false) await updateCalendarIntegration(int.id, null, null, null, false).catch(e => console.warn("Failed to disable sync:", e.message)); return { success: false, error: { message: 'Token refresh failed', details: rResult.error } }; }
  const { access_token, expires_in } = rResult.data; const newExp = dayjs().add(expires_in, 'seconds').toISOString();
  if (!int.id) { /* console.error(`Critical: Integration ID missing for user ${userId} post-refresh.`); */ return { success: false, error: { message: 'Integration ID missing post-refresh.' }}; }
  const uResult = await updateCalendarIntegration(int.id, access_token, newExp, int.refreshToken, typeof int.syncEnabled === 'boolean' ? int.syncEnabled : true);
  if (!uResult.success) return { success: false, error: { message: 'Failed to update integration with new token', details: uResult.error } };
  return { success: true, token: access_token };
};
export const createGoogleEvent = async (userId: string, calendarIdVal: string, clientTypeVal: CalendarIntegrationType['clientType'], summaryVal: string, startDateTimeVal: string, endDateTimeVal: string, timezoneVal: string, descriptionVal?: string, attendeesVal?: { email: string }[], conferenceSolutionVal?: 'eventHangout' | 'hangoutsMeet' | null): Promise<CreateGoogleEventResponse> => { /* ... */
  const operation_name = "GoogleCreateEvent";
  const tokenResult = await getGoogleAPIToken(userId, 'google_calendar'); if (!tokenResult.success) return { success: false, error: { message: 'Token acquisition failure for Google event.', details: tokenResult.error } };
  const oAuth2Client = new Auth.OAuth2Client(); oAuth2Client.setCredentials({ access_token: tokenResult.token });
  const calendar = google.calendar({ version: 'v3', auth: oAuth2Client }); const generatedId = uuidv4();
  const event: any = { summary: summaryVal, description: descriptionVal, start: { dateTime: startDateTimeVal, timeZone: timezoneVal }, end: { dateTime: endDateTimeVal, timeZone: timezoneVal }, attendees: attendeesVal, reminders: { useDefault: true } };
  if (conferenceSolutionVal) event.conferenceData = { createRequest: { requestId: generatedId, conferenceSolutionKey: { type: conferenceSolutionVal } } };
  try {
    // Note: googleapis library might have its own retry. If insufficient, wrap with async-retry.
    const gEvent = await calendar.events.insert({ calendarId: calendarIdVal, requestBody: event, conferenceDataVersion: conferenceSolutionVal ? 1 : 0 });
    if (!gEvent.data.id) return { success: false, error: { message: 'Google API did not return event ID.', details: gEvent.data }};
    const gEventId = gEvent.data.id; return { success: true, data: { id: `${gEventId}#${calendarIdVal}`, googleEventId: gEventId, generatedId, calendarId: calendarIdVal, generatedEventId: generatedId.split('_')?.[0] } };
  } catch (e: any) { /* console.error(`[${operation_name}] Error creating Google Calendar event:`, e.message); */ return { success: false, error: { message: 'Google Calendar API error during event creation.', details: e.response?.data || e.errors || e } }; }
};
export const upsertEventsPostPlanner = async (events: EventInput[]): Promise<UpsertEventsPostPlannerResponse> => {
  const operation_name = 'HasuraUpsertEvents';
  const uniqueEvents = _.uniqBy(events.filter(e => e), 'id'); if (uniqueEvents.length === 0) return { success: true, data: { affected_rows: 0, returning: [] } };
  const objects = uniqueEvents.map(event => ({ ...event, provider: event.provider || 'google_calendar', status: event.status || 'confirmed' }));
  const mutation = `mutation UpsertEvents($objects: [Event_insert_input!]!) { insert_Event(objects: $objects, on_conflict: { constraint: Event_pkey, update_columns: [summary, description, startDateTime, endDateTime, timezone, gEventId, provider, updatedAt, taskId, projectId, status, parentEventId] }) { affected_rows returning { id } } }`;
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query: mutation, variables: { objects } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 15000 }, // Longer timeout for potentially large upserts
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during event upsert.', details: body.errors } }; }
    if (!body.data || !body.data.insert_Event) { /* console.warn(`[${operation_name}] Unexpected Hasura response:`, body); */ return { success: false, error: { message: 'Unexpected Hasura response during event upsert.', details: body } }; }
    return { success: true, data: body.data.insert_Event };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during event upsert.', details: e.message, rawResponse: e.response?.body } }; }
};
export const getGlobalCalendar = async (userId: string): Promise<SuccessResponseType<GlobalCalendarType | undefined> | FailureResponseType> => {
  const operation_name = 'HasuraGetGlobalCalendar';
  const query = `query GetGlobalCalendar($userId: String!) { Calendar(where: {userId: {_eq: $userId}, type: {_eq: "global"}}, limit: 1) { id userId primaryCalendarId } }`;
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query, variables: { userId } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during getGlobalCalendar.', details: body.errors } }; }
    if (!body.data || !body.data.hasOwnProperty('Calendar')) { /* console.warn(`[${operation_name}] Unexpected response:`, body); */ return { success: false, error: { message: 'Unexpected response structure during getGlobalCalendar.', details: body } }; }
    return { success: true, data: body.data.Calendar?.[0] };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during getGlobalCalendar.', details: e.message, rawResponse: e.response?.body } }; }
};
export const listEventsForDate = async (userId: string, startDate: string, endDate: string, timezoneParam: string): Promise<SuccessResponseType<EventType[]> | FailureResponseType> => {
  const operation_name = 'HasuraListEventsForDate';
  const query = `query ListEventsForDate($userId: String!, $startDate: timestamptz!, $endDate: timestamptz!) { Event(where: {userId: {_eq: $userId}, startDateTime: {_gte: $startDate}, endDateTime: {_lte: $endDate}, _or: [{isDeleted: {_is_null: true}}, {isDeleted: {_eq: false}}]}, order_by: {startDateTime: asc}) { id userId summary startDateTime endDateTime timezone } }`;
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query, variables: { userId, startDate, endDate } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during listEventsForDate.', details: body.errors } }; }
    if (!body.data || !body.data.hasOwnProperty('Event')) { /* console.warn(`[${operation_name}] Unexpected response:`, body); */ return { success: false, error: { message: 'Unexpected response structure during listEventsForDate.', details: body } }; }
    return { success: true, data: body.data.Event || [] };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during listEventsForDate.', details: e.message, rawResponse: e.response?.body } }; }
};
export const listEventsForUserGivenDates = async (userId: string, senderStartDate: string, senderEndDate: string): Promise<SuccessResponseType<EventType[]> | FailureResponseType> => {
  const operation_name = 'HasuraListEventsForUserGivenDates';
  const query = `query ListEventsForUserGivenDates($userId: String!, $startDate: timestamptz!, $endDate: timestamptz!) { Event(where: {userId: {_eq: $userId}, startDateTime: {_gte: $startDate}, endDateTime: {_lte: $endDate}, _or: [{isDeleted: {_is_null: true}}, {isDeleted: {_eq: false}}]}, order_by: {startDateTime: asc}) { id userId summary startDateTime endDateTime timezone } }`;
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query, variables: { userId, startDate: senderStartDate, endDate: senderEndDate } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during listEventsForUserGivenDates.', details: body.errors } }; }
    if (!body.data || !body.data.hasOwnProperty('Event')) { /* console.warn(`[${operation_name}] Unexpected response:`, body); */ return { success: false, error: { message: 'Unexpected response structure during listEventsForUserGivenDates.', details: body } }; }
    return { success: true, data: body.data.Event || [] };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during listEventsForUserGivenDates.', details: e.message, rawResponse: e.response?.body } }; }
};
export const getUserPreferences = async (userId: string): Promise<SuccessResponseType<UserPreferenceType | undefined> | FailureResponseType> => {
  const operation_name = 'HasuraGetUserPreferences';
  const query = `query GetUserPreferences($userId: String!) { User_Preferences(where: {userId: {_eq: $userId}}, limit: 1) { id userId somePreference workHoursStartTime workHoursEndTime workDays slotDuration timezone bufferBetweenMeetings } }`; // Added more fields
  try {
    const response = await got.post(process.env.HASURA_ENDPOINT_URL || '', {
      json: { query, variables: { userId } },
      headers: { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET || '' },
      responseType: 'json',
      timeout: { request: 10000 },
      retry: defaultGotRetryConfig
    });
    const body = response.body as any;
    if (body.errors) { /* console.error(`[${operation_name}] Hasura errors:`, body.errors); */ return { success: false, error: { message: 'Hasura API error during getUserPreferences.', details: body.errors } }; }
    if (!body.data || !body.data.hasOwnProperty('User_Preferences')) { /* console.warn(`[${operation_name}] Unexpected response:`, body); */ return { success: false, error: { message: 'Unexpected response structure during getUserPreferences.', details: body } }; }
    return { success: true, data: body.data.User_Preferences?.[0] };
  } catch (e: any) { /* console.error(`[${operation_name}] Network error:`, e.message); */ return { success: false, error: { message: 'Network error during getUserPreferences.', details: e.message, rawResponse: e.response?.body } }; }
};
export const sendAgendaEmail = async (to: string, name: string, title: string, body: string): Promise<EmailResponse> => { /* ... */
  // Note: sendEmail itself needs retry logic if it makes network calls. For now, this wrapper doesn't add retries.
  const operation_name = "SendAgendaEmail";
  try { await sendEmail({ template: 'agenda', locals: { name, title, body, to }, subject: `Your Meeting Agenda: ${title}`, to }); return { success: true }; }
  catch (e: any) { console.log(`Error sending agenda email to ${to}:`, e.message); return { success: false, error: { message: 'Failed to send agenda email.', details: e.message } }; }
};
export const sendSummaryEmail = async (to: string, name: string, title: string, summary: string): Promise<EmailResponse> => { /* ... */
  try { await sendEmail({ template: 'summary', locals: { name, title, summary, to }, subject: `Your Meeting Summary: ${title}`, to }); return { success: true }; }
  catch (e: any) { console.log(`Error sending summary email to ${to}:`, e.message); return { success: false, error: { message: 'Failed to send summary email.', details: e.message } }; }
};
export const emailTaskBreakDown = async (to: string, name: string, title: string, tasks: string): Promise<EmailResponse> => { /* ... */
  try { await sendEmail({ template: 'task_breakdown', locals: { name, title, tasks, to }, subject: `Your Task Breakdown for: ${title}`, to }); return { success: true }; }
  catch (e: any) { console.log(`Error sending task breakdown email to ${to}:`, e.message); return { success: false, error: { message: 'Failed to send task breakdown email.', details: e.message } }; }
};
export const sendGenericTaskEmail = async (to: string, name: string, title: string, body: string): Promise<EmailResponse> => { /* ... */
  try { await sendEmail({ template: 'generic_task', locals: { name, title, body, to }, subject: title, to }); return { success: true }; }
  catch (e: any) { console.log(`Error sending generic task email to ${to}:`, e.message); return { success: false, error: { message: 'Failed to send generic task email.', details: e.message } }; }
};
export const sendMeetingRequestTemplate = async (to: string, name: string, title: string, body: string, yesLink: string, noLink: string): Promise<EmailResponse> => { /* ... */
  try { await sendEmail({ template: 'meeting_request', locals: { name, title, body, yesLink, noLink, to }, subject: `Meeting Request: ${title}`, to }); return { success: true }; }
  catch (e: any) { console.log(`Error sending meeting request email to ${to}:`, e.message); return { success: false, error: { message: 'Failed to send meeting request email.', details: e.message } }; }
};
export const createAgenda = async (userId: string, clientType: CalendarIntegrationType['clientType'], userTimezone: string, userDate: string, promptVal: string, email?: string, nameVal?: string): Promise<GenericSuccessResponse | FailureResponseType> => { /* ... */
  try {
    const openAIRes = await callOpenAI(`Create agenda for ${userDate} in ${userTimezone}.`, promptVal);
    if (!openAIRes.success || !openAIRes.content) { console.log('createAgenda: OpenAI fail', openAIRes.error); return { success: false, error: { message: 'Failed to create agenda due to OpenAI call failed or no content.', details: openAIRes.error } }; }
    const agendaSum = "Generated Agenda Event"; const agendaDesc = openAIRes.content;
    const gCalRes = await getGlobalCalendar(userId);
    if (!gCalRes.success || !gCalRes.data?.primaryCalendarId) { console.log('createAgenda: GlobalCal fail', gCalRes.error); return { success: false, error: { message: 'Failed to create agenda due to global calendar retrieval failure.', details: gCalRes.error } }; }
    const startDT = dayjs.tz(`${userDate}T09:00:00`, userTimezone).toISOString(); const endDT = dayjs.tz(`${userDate}T10:00:00`, userTimezone).toISOString();
    const createGEventRes = await createGoogleEvent(userId, gCalRes.data.primaryCalendarId, clientType, agendaSum, startDT, endDT, userTimezone, agendaDesc);
  if (!createGEventRes.success) { /* console.error('createAgenda: CreateGEvent fail', createGEventRes.error); */ return { success: false, error: { message: 'Failed to create agenda due to Google event creation failure.', details: createGEventRes.error } }; }
    const eventToUpsert: EventInput = { userId, calendarId: gCalRes.data.id, gEventId: createGEventRes.data.googleEventId, summary: agendaSum, description: agendaDesc, startDateTime: startDT, endDateTime: endDT, timezone: userTimezone, provider: 'google_calendar', status: 'confirmed' };
    const upsertRes = await upsertEventsPostPlanner([eventToUpsert]);
  if (!upsertRes.success) { /* console.error('createAgenda: Upsert fail', upsertRes.error); */ return { success: false, error: { message: 'Failed to create agenda due to database event upsert failure.', details: upsertRes.error } }; }
    if (email && nameVal) {
      const emailRes = await sendAgendaEmail(email, nameVal, "Your Generated Agenda", agendaDesc);
      if (!emailRes.success) { console.log('createAgenda: Email fail', emailRes.error); return { success: false, error: { message: 'Failed to create agenda due to email sending failure.', details: emailRes.error } }; }
    }
    return { success: true };
  } catch (e: any) { console.log('Unexpected error in createAgenda:', e.message); return { success: false, error: { message: 'Unexpected error during agenda creation.', details: e.message } }; }
};
export const createSummaryOfTimePeriod = async (userId: string, startDate: string, endDate: string, timezone: string, email?: string, name?: string): Promise<SuccessResponseType<string> | FailureResponseType> => { /* ... */
  try {
    const eventsResult = await listEventsForDate(userId, startDate, endDate, timezone);
    if (!eventsResult.success) { console.log('createSummary: listEventsForDate failed', eventsResult.error); return { success: false, error: { message: 'Failed to create summary due to event listing failure.', details: eventsResult.error } }; }
    if (!eventsResult.data || eventsResult.data.length === 0) { console.log('createSummary: No events found.'); return { success: false, error: { message: 'No events found to summarize.' } }; }
    const eventsText = eventsResult.data.map(event => `${event.summary} (from ${event.startDateTime} to ${event.endDateTime})`).join('\n');
    const prompt = `Summarize the following events that occurred between ${startDate} and ${endDate}:\n${eventsText}`;
    const openAIResult = await callOpenAI("You are an assistant that summarizes a list of calendar events.", prompt);
    if (!openAIResult.success || !openAIResult.content) { console.log('createSummary: callOpenAI failed', openAIResult.error); return { success: false, error: { message: 'Failed to create summary due to OpenAI call failure.', details: openAIResult.error } }; }
    const summaryText = openAIResult.content;
    if (email && name) {
      const emailResult = await sendSummaryEmail(email, name, `Summary for ${startDate} to ${endDate}`, summaryText);
      if (!emailResult.success) { console.log('createSummary: sendSummaryEmail failed', emailResult.error); return { success: false, error: { message: 'Failed to send summary email.', details: emailResult.error } }; }
    }
    return { success: true, data: summaryText };
  } catch (e: any) { console.log('Unexpected error in createSummaryOfTimePeriod:', e.message); return { success: false, error: { message: 'Unexpected error during summary creation.', details: e.message } }; }
};
const createEventHelper = async (userId: string, clientType: CalendarIntegrationType['clientType'], userTimezone: string, eventSummary: string, eventDescription: string | undefined, startDateTime: string, endDateTime: string, isAllDay: boolean): Promise<CreateGoogleEventResponse> => { /* ... */
    const globalCalResult = await getGlobalCalendar(userId);
    if (!globalCalResult.success || !globalCalResult.data?.primaryCalendarId) { console.log('EventHelper: GlobalCal fail', globalCalResult.error); return { success: false, error: { message: 'Global calendar retrieval failed for event creation.', details: globalCalResult.error } }; }
    const calendarIdToUse = globalCalResult.data.primaryCalendarId;
    let eventStartDT = startDateTime; let eventEndDT = endDateTime;
    if(isAllDay) { eventStartDT = dayjs(startDateTime).format('YYYY-MM-DD'); eventEndDT = dayjs(endDateTime).add(1, 'day').format('YYYY-MM-DD'); }
    return createGoogleEvent(userId, calendarIdToUse, clientType, eventSummary, eventStartDT, eventEndDT, userTimezone, eventDescription);
};
export const breakDownTask = async (userId: string, clientType: CalendarIntegrationType['clientType'], userTimezone: string, taskTitle: string, taskDescription: string, isAllDay: boolean, startDate: string, endDate: string, email?: string, name?: string): Promise<GenericSuccessResponse | FailureResponseType> => { /* ... */
  try {
    const openAIResult = await callOpenAI("You are an assistant that breaks down a task into smaller sub-events for a calendar.", `Break down the task: "${taskTitle}" (Description: ${taskDescription}) into smaller calendar events. Main task is from ${startDate} to ${endDate} (isAllDay: ${isAllDay}).`);
    if (!openAIResult.success || !openAIResult.content) { console.log('breakDownTask: OpenAI fail', openAIResult.error); return { success: false, error: { message: 'OpenAI call failed during task breakdown.', details: openAIResult.error } }; }
    const breakdownText = openAIResult.content;
    const createEventRes = await createEventHelper(userId, clientType, userTimezone, taskTitle, breakdownText, startDate, endDate, isAllDay);
    if (!createEventRes.success) { console.log('breakDownTask: CreateGEvent fail', createEventRes.error); return { success: false, error: { message: 'Google event creation failed for task breakdown.', details: createEventRes.error } }; }
    const globalCal = await getGlobalCalendar(userId); if(!globalCal.success || !globalCal.data?.id) { console.log('breakDownTask: getGlobalCalendar for DB ID failed', globalCal.error); return { success: false, error: { message: 'Failed to get global calendar ID for DB upsert.', details: globalCal.error } }; }
    const eventToUpsert: EventInput = { userId, calendarId: globalCal.data.id, gEventId: createEventRes.data.googleEventId, summary: taskTitle, description: breakdownText, startDateTime: startDate, endDateTime: endDate, timezone: userTimezone, provider: 'google_calendar', status: 'confirmed' };
    const upsertRes = await upsertEventsPostPlanner([eventToUpsert]);
    if (!upsertRes.success) { console.log('breakDownTask: Upsert fail', upsertRes.error); return { success: false, error: { message: 'Database event upsert failed for task breakdown.', details: upsertRes.error } }; }
    if (email && name) {
      const emailRes = await emailTaskBreakDown(email, name, taskTitle, breakdownText);
      if (!emailRes.success) { console.log('breakDownTask: Email fail', emailRes.error); return { success: false, error: { message: 'Email sending failed for task breakdown.', details: emailRes.error } }; }
    }
    return { success: true };
  } catch (e: any) { console.log('Unexpected error in breakDownTask:', e.message); return { success: false, error: { message: 'Unexpected error during task breakdown.', details: e.message } }; }
};
export const howToTask = async (userId: string, clientType: CalendarIntegrationType['clientType'], userTimezone: string, taskTitle: string, isAllDay: boolean, startDate: string, endDate: string, email?: string, name?: string): Promise<GenericSuccessResponse | FailureResponseType> => { /* ... */
  try {
    const openAIResult = await callOpenAI("You are an assistant that provides instructions on how to complete a task and schedules it.", `Provide instructions for task: "${taskTitle}". Schedule it from ${startDate} to ${endDate} (isAllDay: ${isAllDay}).`);
    if (!openAIResult.success || !openAIResult.content) { console.log('howToTask: OpenAI fail', openAIResult.error); return { success: false, error: { message: 'OpenAI call failed for how-to task.', details: openAIResult.error } }; }
    const howToContent = openAIResult.content;
    const createEventRes = await createEventHelper(userId, clientType, userTimezone, `How to: ${taskTitle}`, howToContent, startDate, endDate, isAllDay);
    if (!createEventRes.success) { console.log('howToTask: CreateGEvent fail', createEventRes.error); return { success: false, error: { message: 'Google event creation failed for how-to task.', details: createEventRes.error } }; }
    const globalCal = await getGlobalCalendar(userId); if(!globalCal.success || !globalCal.data?.id) { console.log('howToTask: getGlobalCalendar for DB ID failed', globalCal.error); return { success: false, error: { message: 'Failed to get global calendar ID for DB upsert (how-to).', details: globalCal.error } }; }
    const eventToUpsert: EventInput = { userId, calendarId: globalCal.data.id, gEventId: createEventRes.data.googleEventId, summary: `How to: ${taskTitle}`, description: howToContent, startDateTime: startDate, endDateTime: endDate, timezone: userTimezone, provider: 'google_calendar', status: 'confirmed' };
    const upsertRes = await upsertEventsPostPlanner([eventToUpsert]);
    if (!upsertRes.success) { console.log('howToTask: Upsert fail', upsertRes.error); return { success: false, error: { message: 'Database event upsert failed for how-to task.', details: upsertRes.error } }; }
    if (email && name) {
      const emailRes = await sendGenericTaskEmail(email, name, `Instructions for: ${taskTitle}`, howToContent);
      if (!emailRes.success) { console.log('howToTask: Email fail', emailRes.error); return { success: false, error: { message: 'Email sending failed for how-to task.', details: emailRes.error } }; }
    }
    return { success: true };
  } catch (e: any) { console.log('Unexpected error in howToTask:', e.message); return { success: false, error: { message: 'Unexpected error during how-to task processing.', details: e.message } }; }
};
export const meetingRequest = async (userId: string, clientType: CalendarIntegrationType['clientType'], userTimezone: string, userDateContext: string, attendees: string, subject: string, promptVal: string, durationMinutes: number, shareAvailability: boolean, availabilityUserDateStart?: string, availabilityUserDateEnd?: string, emailTo?: string, emailName?: string, yesLink?: string, noLink?: string): Promise<GenericSuccessResponse | FailureResponseType> => { /* ... */
    try {
        let availabilitySummary = "Not applicable.";
        if (shareAvailability) {
            if (!availabilityUserDateStart || !availabilityUserDateEnd) return { success: false, error: { message: "Availability start and end dates are required when shareAvailability is true." } };
            const genAvailRes = await generateAvailability(userId, availabilityUserDateStart, availabilityUserDateEnd, userTimezone /*, clientType - clientType not used by generateAvailability directly */);
            if (!genAvailRes.success) { console.log('meetingRequest: generateAvailability failed', genAvailRes.error); return { success: false, error: { message: 'Failed to generate availability.', details: genAvailRes.error } }; }
            if (!genAvailRes.data || genAvailRes.data.length === 0) { console.log('meetingRequest: No availability slots found.'); return { success: false, error: { message: 'No availability slots found to share.' } }; }
            const slotsByDate = _.groupBy(genAvailRes.data, slot => dayjs(slot.startDate).tz(userTimezone).format('YYYY-MM-DD'));
            let dailySummaries: string[] = [];
            for (const date in slotsByDate) {
                const slots = slotsByDate[date].map(slot => `${dayjs(slot.startDate).tz(userTimezone).format('h:mm A')} - ${dayjs(slot.endDate).tz(userTimezone).format('h:mm A')}`).join(', ');
                const dailySummaryRes = await callOpenAI("Summarize daily availability.", `Summarize these availability slots for ${date}: ${slots}`);
                if (!dailySummaryRes.success || !dailySummaryRes.content) { console.log(`meetingRequest: OpenAI daily summary failed for ${date}`, dailySummaryRes.error); return { success: false, error: { message: `Failed to summarize availability for date ${date}.`, details: dailySummaryRes.error } }; }
                dailySummaries.push(dailySummaryRes.content);
            }
            if (dailySummaries.length === 0) return { success: false, error: { message: 'No availability slots found after processing.' } }; // Should be caught by earlier check
            const combinedSummaryRes = await callOpenAI("Combine daily availability summaries.", `Combine these daily availability summaries:\n${dailySummaries.join('\n')}`);
            if (!combinedSummaryRes.success || !combinedSummaryRes.content) { console.log('meetingRequest: OpenAI combined summary failed', combinedSummaryRes.error); return { success: false, error: { message: 'Failed to generate combined availability summary.', details: combinedSummaryRes.error } }; }
            availabilitySummary = combinedSummaryRes.content;
        }
        const emailDraftPrompt = `Draft a meeting request email. Subject: ${subject} Attendees: ${attendees} User's request: ${promptVal} Meeting duration: ${durationMinutes} minutes. Contextual user date: ${userDateContext}. User's timezone: ${userTimezone}. ${shareAvailability ? `Include this availability: ${availabilitySummary}` : "Ask for their availability."} Polite, clear call to action. Placeholders for response links if applicable.`;
        const emailBodyRes = await callOpenAI("Draft a meeting request email.", emailDraftPrompt);
        if (!emailBodyRes.success || !emailBodyRes.content) { console.log('meetingRequest: OpenAI email draft failed', emailBodyRes.error); return { success: false, error: { message: 'Failed to draft meeting request email body.', details: emailBodyRes.error } }; }
        if (emailTo && emailName && yesLink && noLink) {
            const sendEmailRes = await sendMeetingRequestTemplate(emailTo, emailName, subject, emailBodyRes.content, yesLink, noLink);
            if (!sendEmailRes.success) { console.log('meetingRequest: sendMeetingRequestTemplate failed', sendEmailRes.error); return { success: false, error: { message: 'Failed to send meeting request email.', details: sendEmailRes.error } }; }
        } else { console.log('meetingRequest: Email recipient details not provided. Drafted body:', emailBodyRes.content); }
        return { success: true };
    } catch (e: any) { console.log('Unexpected error in meetingRequest:', e.message); return { success: false, error: { message: 'Unexpected error during meeting request processing.', details: e.message } }; }
};
export const createDaySchedule = async ( userId: string, clientType: CalendarIntegrationType['clientType'], userDate: string, userTimezone: string, prompt: string, isAllDay: boolean, email?: string, name?: string ): Promise<GenericSuccessResponse | FailureResponseType> => { /* ... */
  try {
    const dayStart = dayjs.tz(userDate, userTimezone).startOf('day').toISOString(); const dayEnd = dayjs.tz(userDate, userTimezone).endOf('day').toISOString();
    const existingEventsRes = await listEventsForUserGivenDates(userId, dayStart, dayEnd);
    if (!existingEventsRes.success) { console.log('createDaySchedule: listEventsForUserGivenDates failed', existingEventsRes.error); return { success: false, error: { message: 'Failed to list existing events for schedule context.', details: existingEventsRes.error } }; }
    const existingEventsText = existingEventsRes.data.map(e => `${e.summary} from ${dayjs(e.startDateTime).tz(userTimezone).format('h:mm A')} to ${dayjs(e.endDateTime).tz(userTimezone).format('h:mm A')}`).join('\n') || "No existing events scheduled.";
    const openAIPrompt = `Given the user's request: "${prompt}", and their existing schedule for ${userDate} in ${userTimezone}:\n${existingEventsText}\n\nCreate a schedule of new tasks as a JSON array. Each task object should have "start_time" (e.g., "9:00 AM"), "end_time" (e.g., "10:30 AM"), "task" (summary), and optionally "description". Ensure new tasks do not overlap with existing events unless the prompt explicitly asks to replace or modify them. For an all-day schedule, the tasks should collectively represent the day's plan without specific times, just a list of tasks and descriptions. This is an ${isAllDay ? 'all-day' : 'itemized time'} schedule.`;
    const openAIResponse = await callOpenAI("You are a scheduling assistant.", openAIPrompt);
    if (!openAIResponse.success || !openAIResponse.content) { console.log('createDaySchedule: callOpenAI failed', openAIResponse.error); return { success: false, error: { message: 'Failed to generate schedule via OpenAI.', details: openAIResponse.error } }; }
    let parsedTasks: ParsedScheduleTask[];
    try { parsedTasks = JSON.parse(openAIResponse.content); }
    catch (e: any) { console.log('createDaySchedule: Failed to parse OpenAI response as JSON', e.message); return { success: false, error: { message: 'Failed to parse schedule from OpenAI response as JSON.', details: e.message, rawResponse: openAIResponse.content } }; }
    if (!Array.isArray(parsedTasks)) { console.log('createDaySchedule: OpenAI response is not a valid array', parsedTasks); return { success: false, error: { message: 'OpenAI schedule response is not a valid array.', parsedResponse: parsedTasks } }; }
    if (parsedTasks.length === 0) {
      console.log('createDaySchedule: No new tasks parsed from OpenAI response.');
      if (email && name) { const emailResult = await sendGenericTaskEmail(email, name, `Your Schedule for ${userDate}`, "No new tasks were scheduled based on your request and current calendar."); if (!emailResult.success) { console.log('createDaySchedule: Failed to send no-tasks email.', emailResult.error); return { success: false, error: { message: 'Failed to send schedule update email (no new tasks).', details: emailResult.error } }; } }
      return { success: true };
    }
    const globalCalendarResult = await getGlobalCalendar(userId);
    if (!globalCalendarResult.success || !globalCalendarResult.data?.primaryCalendarId || !globalCalendarResult.data?.id) { console.log('createDaySchedule: Failed to get global calendar or primaryCalendarId/id.', globalCalendarResult.error); return { success: false, error: { message: 'Failed to get global calendar for scheduling.', details: globalCalendarResult.error } }; }
    const { primaryCalendarId: googleCalendarIdForEvents, id: dbCalendarId } = globalCalendarResult.data;
    const eventsToUpsert: EventInput[] = [];
    if (isAllDay) {
      const allDayTaskSummary = `Day Schedule: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`; const allDayTaskDescription = parsedTasks.map(task => `${task.task}${task.description ? `:\n${task.description}` : ''}`).join('\n\n---\n\n');
      const allDayStartDate = dayjs.tz(userDate, userTimezone).startOf('day').format('YYYY-MM-DD'); const allDayEndDate = dayjs.tz(userDate, userTimezone).add(1, 'day').startOf('day').format('YYYY-MM-DD');
      const createEventRes = await createGoogleEvent(userId, googleCalendarIdForEvents, clientType, allDayTaskSummary, allDayStartDate, allDayEndDate, userTimezone, allDayTaskDescription);
      if (!createEventRes.success) { console.log('createDaySchedule: Failed to create all-day Google event.', createEventRes.error); return { success: false, error: { message: 'Failed to create all-day Google Calendar event.', details: createEventRes.error } }; }
      eventsToUpsert.push({ userId, calendarId: dbCalendarId, gEventId: createEventRes.data.googleEventId, summary: allDayTaskSummary, description: allDayTaskDescription, startDateTime: allDayStartDate, endDateTime: allDayEndDate, timezone: userTimezone, provider: 'google_calendar', status: 'confirmed' });
    } else {
      for (const task of parsedTasks) {
        const taskStart = dayjs.tz(`${userDate} ${task.start_time}`, 'YYYY-MM-DD h:mm A', userTimezone); const taskEnd = dayjs.tz(`${userDate} ${task.end_time}`, 'YYYY-MM-DD h:mm A', userTimezone);
        if (!taskStart.isValid() || !taskEnd.isValid()) { console.log(`createDaySchedule: Invalid time format for task "${task.task}"`); return { success: false, error: { message: `Invalid time format for task "${task.task}". Please use HH:MM AM/PM.`, details: { task } }}; }
        const startDateTime = taskStart.toISOString(); const endDateTime = taskEnd.toISOString();
        const overlaps = existingEventsRes.data.some(existingEvent => dayjs(startDateTime).isBefore(dayjs(existingEvent.endDateTime)) && dayjs(endDateTime).isAfter(dayjs(existingEvent.startDateTime)));
        if (overlaps) { console.log(`createDaySchedule: Task "${task.task}" overlaps. Skipping.`); continue; }
        const createEventRes = await createGoogleEvent(userId, googleCalendarIdForEvents, clientType, task.task, startDateTime, endDateTime, userTimezone, task.description);
        if (!createEventRes.success) { console.log('createDaySchedule: Failed to create Google event for task.', task, createEventRes.error); return { success: false, error: { message: `Failed to create Google Calendar event for task: "${task.task}".`, details: createEventRes.error } }; }
        eventsToUpsert.push({ userId, calendarId: dbCalendarId, gEventId: createEventRes.data.googleEventId, summary: task.task, description: task.description, startDateTime, endDateTime, timezone: userTimezone, provider: 'google_calendar', status: 'confirmed' });
      }
    }
    if (eventsToUpsert.length === 0) {
        console.log('createDaySchedule: No new non-overlapping tasks to schedule.');
        if (email && name) { const emailBody = "Your day schedule was processed. After checking for overlaps with existing events, no new tasks were added to your calendar."; const emailResult = await sendGenericTaskEmail(email, name, `Your Schedule for ${userDate}`, emailBody); if (!emailResult.success) { console.log('createDaySchedule: Failed to send no-new-tasks email.', emailResult.error); return { success: false, error: { message: 'Failed to send schedule update email (no new tasks after filtering).', details: emailResult.error } }; } }
        return { success: true };
    }
    const upsertResult = await upsertEventsPostPlanner(eventsToUpsert);
    if (!upsertResult.success) { console.log('createDaySchedule: upsertEventsPostPlanner failed', upsertResult.error); return { success: false, error: { message: 'Failed to save scheduled events to database.', details: upsertResult.error } }; }
    if (email && name) {
      const emailBodyContent = openAIResponse.content;
      const emailResult = await sendGenericTaskEmail(email, name, `Your Daily Schedule for ${userDate}`, emailBodyContent);
      if (!emailResult.success) { console.log('createDaySchedule: emailDailySchedule failed', emailResult.error); return { success: false, error: { message: 'Failed to send daily schedule email.', details: emailResult.error } }; }
    }
    return { success: true };
  } catch (e: any) { console.log('Unexpected error in createDaySchedule:', e.message, e); return { success: false, error: { message: 'Unexpected error during day schedule creation.', details: e.message } }; }
};

// --- Availability Generation Functions (Refactored) ---
export const generateAvailableSlotsForDate = (
  date: string, // YYYY-MM-DD format for the target day
  senderPreferences: UserPreferenceType, // Contains work hours, slot duration, timezone
  notAvailableSlotsInEventTimezone: AvailabilitySlot[], // Existing busy slots for the user, in event's target timezone
  receiverTimezone: string, // Timezone for which the slots should be presented
  isFirstDay: boolean, // Is this the first day of the overall window?
  isLastDay: boolean, // Is this the last day of the overall window?
  windowStartTimeInReceiverTimezone?: string, // HH:mm, only if isFirstDay is true
  windowEndTimeInReceiverTimezone?: string,   // HH:mm, only if isLastDay is true
): AvailabilitySlot[] => {
  const availableSlots: AvailabilitySlot[] = [];
  const senderTz = senderPreferences.timezone || 'UTC'; // Default to UTC if not specified
  const slotDuration = senderPreferences.slotDuration || 30;
  const bufferMinutes = senderPreferences.bufferBetweenMeetings || 0;

  // Parse sender's work hours in their timezone
  // Default to 9 AM - 5 PM if not specified
  const workStartHour = parseInt((senderPreferences.workHoursStartTime || '09:00').split(':')[0]);
  const workStartMinute = parseInt((senderPreferences.workHoursStartTime || '09:00').split(':')[1]);
  const workEndHour = parseInt((senderPreferences.workHoursEndTime || '17:00').split(':')[0]);
  const workEndMinute = parseInt((senderPreferences.workHoursEndTime || '17:00').split(':')[1]);

  let dayStart = dayjs.tz(date, senderTz).hour(workStartHour).minute(workStartMinute).second(0).millisecond(0);
  let dayEnd = dayjs.tz(date, senderTz).hour(workEndHour).minute(workEndMinute).second(0).millisecond(0);

  // Adjust start time if it's the first day of a specific window
  if (isFirstDay && windowStartTimeInReceiverTimezone) {
    const windowStart = dayjs.tz(`${date} ${windowStartTimeInReceiverTimezone}`, 'YYYY-MM-DD HH:mm', receiverTimezone).tz(senderTz);
    if (windowStart.isAfter(dayStart)) {
      dayStart = windowStart;
    }
  }

  // Adjust end time if it's the last day of a specific window
  if (isLastDay && windowEndTimeInReceiverTimezone) {
    const windowEnd = dayjs.tz(`${date} ${windowEndTimeInReceiverTimezone}`, 'YYYY-MM-DD HH:mm', receiverTimezone).tz(senderTz);
    if (windowEnd.isBefore(dayEnd)) {
      dayEnd = windowEnd;
    }
  }

  let currentSlotStart = dayStart;

  while (currentSlotStart.add(slotDuration, 'minutes').isBefore(dayEnd) || currentSlotStart.add(slotDuration, 'minutes').isSame(dayEnd)) {
    const currentSlotEnd = currentSlotStart.add(slotDuration, 'minutes');
    let isSlotAvailable = true;

    // Check against existing events (notAvailableSlotsInEventTimezone are already in receiver's timezone)
    // Convert current slot to receiver's timezone for comparison
    const currentSlotStartInReceiverTz = currentSlotStart.tz(receiverTimezone);
    const currentSlotEndInReceiverTz = currentSlotEnd.tz(receiverTimezone);

    for (const busySlot of notAvailableSlotsInEventTimezone) {
      const busyStart = dayjs(busySlot.startDate); // Assuming these are already Dayjs objects or ISO strings
      const busyEnd = dayjs(busySlot.endDate);
      // Check for overlap: (StartA < EndB) and (EndA > StartB)
      if (currentSlotStartInReceiverTz.isBefore(busyEnd) && currentSlotEndInReceiverTz.isAfter(busyStart)) {
        isSlotAvailable = false;
        break;
      }
    }

    if (isSlotAvailable) {
      // Store slots in UTC, but ensure they are presented based on receiverTimezone later if needed
      availableSlots.push({
        startDate: currentSlotStart.toISOString(), // Store in UTC
        endDate: currentSlotEnd.toISOString(),   // Store in UTC
      });
    }
    currentSlotStart = currentSlotEnd.add(bufferMinutes, 'minutes');
  }
  return availableSlots;
};

export const generateAvailableSlotsforTimeWindow = (
  startDate: string, // YYYY-MM-DD
  endDate: string,   // YYYY-MM-DD
  senderPreferences: UserPreferenceType,
  notAvailableFromEvents: EventType[], // All events for the user within a broader range
  receiverTimezone: string,
  windowStartTimeInReceiverTimezone?: string, // HH:mm for the first day
  windowEndTimeInReceiverTimezone?: string    // HH:mm for the last day
): { availableSlots: AvailabilitySlot[] } => {
  let allSlots: AvailabilitySlot[] = [];
  let currentDate = dayjs.tz(startDate, receiverTimezone).startOf('day');
  const finalEndDate = dayjs.tz(endDate, receiverTimezone).endOf('day');

  // Convert existing events to notAvailableSlots in the receiver's timezone for comparison
  const notAvailableSlotsInReceiverTz = notAvailableFromEvents.map(event => ({
    startDate: dayjs(event.startDateTime).tz(receiverTimezone).toISOString(), // Convert to receiver's TZ then to ISO
    endDate: dayjs(event.endDateTime).tz(receiverTimezone).toISOString()
  }));


  while (currentDate.isBefore(finalEndDate) || currentDate.isSame(finalEndDate, 'day')) {
    if (senderPreferences.workDays && !senderPreferences.workDays.includes(currentDate.day())) {
      currentDate = currentDate.add(1, 'day');
      continue; // Skip non-working days
    }

    const isFirstDay = currentDate.isSame(dayjs.tz(startDate, receiverTimezone).startOf('day'), 'day');
    const isLastDay = currentDate.isSame(finalEndDate.startOf('day'), 'day');

    const dailySlots = generateAvailableSlotsForDate(
      currentDate.format('YYYY-MM-DD'),
      senderPreferences,
      notAvailableSlotsInReceiverTz, // Pass existing events
      receiverTimezone,
      isFirstDay,
      isLastDay,
      isFirstDay ? windowStartTimeInReceiverTimezone : undefined,
      isLastDay ? windowEndTimeInReceiverTimezone : undefined
    );
    allSlots = allSlots.concat(dailySlots);
    currentDate = currentDate.add(1, 'day');
  }
  return { availableSlots: _.uniqWith(allSlots, _.isEqual) };
};

export const generateAvailability = async (
    userId: string,
    availabilityScanStartDate: string, // YYYY-MM-DD
    availabilityScanEndDate: string,   // YYYY-MM-DD
    receiverGeneratedTimezone: string, // Target timezone for the slots
    // clientType is not directly used here but might be used by listEvents if it were more complex
): Promise<SuccessResponseType<AvailabilitySlot[]> | FailureResponseType> => {
  try {
    const prefsResult = await getUserPreferences(userId);
    if (!prefsResult.success) {
      console.log('generateAvailability: getUserPreferences failed', prefsResult.error);
      return { success: false, error: { message: 'Failed to get user preferences for availability generation.', details: prefsResult.error } };
    }
    if (!prefsResult.data) {
      console.log('generateAvailability: User preferences not found.');
      return { success: false, error: { message: 'User preferences not found, cannot generate availability.' } };
    }
    const senderPreferences = prefsResult.data;

    // Fetch events for the user for the given date range to check for conflicts
    // The range for fetching events should cover the entire scan period in UTC to be safe.
    const scanStartUtc = dayjs.tz(availabilityScanStartDate, senderPreferences.timezone || receiverGeneratedTimezone).startOf('day').utc().toISOString();
    const scanEndUtc = dayjs.tz(availabilityScanEndDate, senderPreferences.timezone || receiverGeneratedTimezone).endOf('day').utc().toISOString();

    const eventsResult = await listEventsForUserGivenDates(userId, scanStartUtc, scanEndUtc);
    if (!eventsResult.success) {
      console.log('generateAvailability: listEventsForUserGivenDates failed', eventsResult.error);
      return { success: false, error: { message: 'Failed to list existing events for availability generation.', details: eventsResult.error } };
    }
    const existingEvents = eventsResult.data; // These are already in UTC from Hasura (assuming timestamptz)

    // Assuming windowStartTime and windowEndTime are not used for this top-level call,
    // meaning we generate for full workdays within the date range.
    const availabilityResult = generateAvailableSlotsforTimeWindow(
      availabilityScanStartDate,
      availabilityScanEndDate,
      senderPreferences,
      existingEvents,
      receiverGeneratedTimezone // Slots should be generated considering this as the target display timezone context
    );

    return { success: true, data: availabilityResult.availableSlots };

  } catch (e: any) {
    console.log('Unexpected error in generateAvailability:', e.message, e);
    return { success: false, error: { message: 'Unexpected error during availability generation.', details: e.message } };
  }
};
