export interface AtomMessage {
    id: string;
    text: string;
}
export interface OAuth2Token {
    access_token: string;
    refresh_token?: string | null;
    scope?: string;
    token_type?: string;
    expiry_date?: number | null;
    id_token?: string | null;
    [key: string]: any;
}
export interface SkillError {
    code: string;
    message: string;
    details?: any;
}
export interface CalendarSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface HubSpotSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface SlackSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface ZoomSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface GraphSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface StripeSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface QBSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface WebResearchSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
/**
 * Represents the structure of an error payload from the Python Flask services.
 */
export interface PythonErrorPayload {
    code: string;
    message: string;
    details?: any;
}
/**
 * Generic type for responses from the Python Flask services.
 * These services should return a JSON object with an "ok" boolean field,
 * and either "data" on success or "error" on failure.
 */
export interface PythonApiResponse<T> {
    ok: boolean;
    data?: T;
    error?: PythonErrorPayload;
}
export interface InitiateResearchData {
    project_page_id: string;
    task_page_ids: string[];
}
export interface ProcessResearchQueueData {
    message: string;
    processed_tasks: number;
    failed_tasks: number;
    synthesis_outcome?: any;
}
export interface CreateNoteData {
    page_id: string;
    url?: string;
    summary?: string;
    key_points?: string;
}
export interface NotionSearchResultData {
    id: string;
    title?: string;
    url?: string;
    content?: string;
    [key: string]: any;
}
export interface NotionSimilarNoteResult {
    note_id: string;
    score: number;
    updated_at?: string;
    user_id?: string;
}
export interface CalendarEvent {
    id: string;
    summary: string;
    description?: string;
    startTime: string;
    endTime: string;
    location?: string;
    htmlLink?: string;
    conferenceData?: ConferenceData;
}
export interface ConferenceSolution {
    key?: {
        type?: string;
        [key: string]: any;
    };
    name?: string;
    iconUri?: string;
    [key: string]: any;
}
export interface ConferenceEntryPoint {
    entryPointType?: 'video' | 'phone' | 'sip' | 'more';
    uri?: string;
    label?: string;
    pin?: string;
    accessCode?: string;
    meetingCode?: string;
    passcode?: string;
    password?: string;
    [key: string]: any;
}
export interface ConferenceData {
    createRequest?: {
        requestId?: string;
        conferenceSolutionKey?: {
            type?: string;
        };
        status?: {
            statusCode?: 'success' | 'failure' | 'pending';
        };
        [key: string]: any;
    };
    entryPoints?: ConferenceEntryPoint[];
    conferenceSolution?: ConferenceSolution;
    conferenceId?: string;
    signature?: string;
    notes?: string;
    [key: string]: any;
}
export interface CreateEventResponse {
    success: boolean;
    eventId?: string;
    message: string;
    htmlLink?: string;
}
export interface SkillResponse<T = any> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface Email {
    id: string;
    sender: string;
    recipient: string;
    subject: string;
    body: string;
    timestamp: string;
    read: boolean;
}
export interface SendEmailResponse {
    success: boolean;
    emailId?: string;
    message: string;
}
export interface ReadEmailResponse {
    success: boolean;
    email?: Email;
    message?: string;
}
export interface SearchResult {
    title: string;
    link: string;
    snippet: string;
}
export interface ZapTriggerResponse {
    success: boolean;
    zapName?: string;
    runId?: string;
    message: string;
}
export interface HubSpotContactProperties {
    email: string;
    firstname?: string;
    lastname?: string;
    company?: string;
}
export interface HubSpotContact {
    id: string;
    properties: {
        hs_object_id: string;
        createdate: string;
        lastmodifieddate: string;
        email?: string;
        firstname?: string;
        lastname?: string;
        company?: string;
        [key: string]: any;
    };
    createdAt: string;
    updatedAt: string;
    archived: boolean;
}
export interface CreateHubSpotContactResponse {
    success: boolean;
    contactId?: string;
    message?: string;
    hubSpotContact?: HubSpotContact;
}
export interface HubSpotEmailEngagementProperties {
    activityTimestamp: number;
    subject: string;
    htmlBody: string;
    direction?: 'INCOMING' | 'OUTGOING';
}
export interface HubSpotEngagementAssociation {
    to: {
        id: string;
    };
    types: {
        associationCategory: string;
        associationTypeId: number;
    }[];
}
export interface HubSpotEngagement {
    id: string;
    properties: {
        hs_object_id: string;
        hs_engagement_type: 'EMAIL' | 'MEETING' | 'CALL' | 'NOTE' | 'TASK';
        hs_timestamp?: string;
        hs_body_preview?: string;
        hs_email_subject?: string;
        hs_email_direction?: 'INCOMING' | 'OUTGOING';
        createdate?: string;
        lastmodifieddate?: string;
        [key: string]: any;
    };
    associations?: {
        contacts?: {
            results: {
                id: string;
                type: string;
            }[];
        };
        companies?: {
            results: {
                id: string;
                type: string;
            }[];
        };
    };
    createdAt: string;
    updatedAt: string;
    archived: boolean;
}
export interface LogEngagementResponse {
    success: boolean;
    engagementId?: string;
    message: string;
    hubSpotEngagement?: HubSpotEngagement;
}
export interface GetContactActivitiesResponse {
    success: boolean;
    activities: HubSpotEngagement[];
    message?: string;
    nextPage?: string;
}
export interface SlackChannel {
    id: string;
    name?: string;
    is_channel?: boolean;
    is_group?: boolean;
    is_im?: boolean;
    is_mpim?: boolean;
    is_private?: boolean;
    is_archived?: boolean;
    is_general?: boolean;
    num_members?: number;
    topic?: {
        value: string;
        creator: string;
        last_set: number;
    };
    purpose?: {
        value: string;
        creator: string;
        last_set: number;
    };
    created?: number;
    creator?: string;
}
export interface SlackMessageData {
    ts?: string;
    channel?: string;
    message?: {
        text?: string;
        user?: string;
        bot_id?: string;
        ts?: string;
        type?: string;
        subtype?: string;
        [key: string]: any;
    };
}
export interface SlackMessageResponse {
    ok: boolean;
    ts?: string;
    channel?: string;
    error?: string;
}
export interface ListSlackChannelsData {
    channels?: SlackChannel[];
    nextPageCursor?: string;
}
export interface CalendlyUser {
    uri: string;
    name: string;
    slug: string;
    email: string;
    scheduling_url: string;
    timezone: string;
    avatar_url?: string | null;
    created_at: string;
    updated_at: string;
}
export interface CalendlyEventType {
    uri: string;
    name: string;
    active: boolean;
    slug: string;
    scheduling_url: string;
    duration: number;
    kind: 'solo' | 'group';
    pooling_type?: 'round_robin' | 'collective' | null;
    type: string;
    color: string;
    created_at: string;
    updated_at: string;
}
export interface CalendlyScheduledEventLocation {
    type: 'physical' | 'inbound_call' | 'outbound_call' | 'custom' | 'google_conference' | 'gotomeeting_conference' | 'microsoft_teams_conference' | 'zoom_conference' | string;
    location?: string | null;
}
export interface CalendlyInvitee {
    uri: string;
    email: string;
    name: string;
    first_name?: string | null;
    last_name?: string | null;
    status: 'active' | 'canceled';
    questions_and_answers: {
        question: string;
        answer: string;
        position: number;
    }[];
    timezone: string;
    event_uri: string;
    cancel_url: string;
    reschedule_url: string;
    created_at: string;
    updated_at: string;
}
export interface CalendlyScheduledEvent {
    uri: string;
    name: string;
    status: 'active' | 'canceled';
    start_time: string;
    end_time: string;
    event_type: string;
    location: CalendlyScheduledEventLocation;
    created_at: string;
    updated_at: string;
}
export interface CalendlyPagination {
    count: number;
    next_page?: string | null;
    previous_page?: string | null;
    next_page_token?: string | null;
    previous_page_token?: string | null;
}
export interface NLUResponseData {
    intent: string | null;
    entities: Record<string, any>;
    confidence?: number;
    recognized_phrase?: string;
    clarification_question?: string;
    partially_understood_intent?: string;
    sub_tasks?: Array<{
        intent: string;
        entities: Record<string, any>;
        summary_for_sub_task?: string;
    }>;
    original_query?: string;
}
export interface ProcessedNLUResponse extends NLUResponseData {
    originalMessage: string;
    error?: string;
    requires_clarification?: boolean;
    clarification_question?: string;
    conversation_context?: any;
    sub_tasks?: Array<{
        intent: string | null;
        entities: Record<string, any>;
        summary_for_sub_task?: string;
    }>;
}
export interface QuickBooksAuthTokens {
    accessToken: string;
    refreshToken: string;
    realmId: string;
    accessTokenExpiresAt: number;
    refreshTokenExpiresAt: number;
    tokenCreatedAt: number;
}
export interface ListQBInvoicesData {
    invoices: QuickBooksInvoice[];
    queryResponse?: any;
}
export interface QuickBooksInvoice {
    Id: string;
    DocNumber?: string;
    TxnDate?: string;
    DueDate?: string;
    CustomerRef?: {
        value: string;
        name?: string;
    };
    BillEmail?: {
        Address: string;
    };
    TotalAmt?: number;
    Balance?: number;
    CurrencyRef?: {
        value: string;
        name?: string;
    };
    Line?: any[];
    PrivateNote?: string;
    CustomerMemo?: string;
    EmailStatus?: 'EmailSent' | 'NotSet' | string;
    [key: string]: any;
}
export interface ListStripePaymentsData {
    payments: StripePaymentIntent[];
    has_more: boolean;
}
export interface StripeCharge {
    id: string;
    amount: number;
    currency: string;
    status: 'succeeded' | 'pending' | 'failed';
    created: number;
    receipt_url?: string | null;
    description?: string | null;
}
export interface StripePaymentIntent {
    id: string;
    amount: number;
    currency: string;
    status: 'succeeded' | 'requires_payment_method' | 'requires_confirmation' | 'requires_action' | 'processing' | 'canceled';
    created: number;
    customer?: string | null;
    description?: string | null;
    latest_charge?: StripeCharge | string | null;
}
export interface SlackMessageFile {
    id: string;
    created: number;
    timestamp: number;
    name: string;
    title: string;
    mimetype: string;
    filetype: string;
    pretty_type: string;
    user?: string;
    editable?: boolean;
    size: number;
    mode?: string;
    is_external?: boolean;
    external_type?: string;
    is_public?: boolean;
    public_url_shared?: boolean;
    display_as_bot?: boolean;
    username?: string;
    url_private?: string;
    url_private_download?: string;
    permalink?: string;
    permalink_public?: string;
}
export interface SlackMessageReaction {
    name: string;
    users: string[];
    count: number;
}
export interface SlackMessage {
    id: string;
    threadId?: string;
    userId?: string;
    userName?: string;
    botId?: string;
    channelId?: string;
    channelName?: string;
    text?: string;
    blocks?: any[];
    files?: SlackMessageFile[];
    reactions?: SlackMessageReaction[];
    timestamp: string;
    permalink?: string;
    raw?: any;
}
export interface ListMSTeamsMeetingsData {
    events: MSGraphEvent[];
    nextLink?: string;
}
export interface MSGraphDateTimeTimeZone {
    dateTime: string;
    timeZone: string;
}
export interface MSGraphOnlineMeetingInfo {
    joinUrl?: string | null;
    conferenceId?: string | null;
    tollNumber?: string | null;
    [key: string]: any;
}
export interface MSGraphEvent {
    id: string;
    subject?: string | null;
    bodyPreview?: string | null;
    body?: {
        contentType?: 'html' | 'text';
        content?: string | null;
    } | null;
    start?: MSGraphDateTimeTimeZone | null;
    end?: MSGraphDateTimeTimeZone | null;
    isOnlineMeeting?: boolean | null;
    onlineMeetingProvider?: 'teamsForBusiness' | 'skypeForBusiness' | 'skypeForConsumer' | string | null;
    onlineMeeting?: MSGraphOnlineMeetingInfo | null;
    webLink?: string | null;
    attendees?: {
        emailAddress?: {
            address?: string | null;
            name?: string | null;
        };
        type?: 'required' | 'optional' | 'resource';
        status?: {
            response?: string;
            time?: string;
        };
    }[];
    location?: {
        displayName?: string | null;
        locationType?: 'default' | 'conferenceRoom' | 'homeAddress' | 'businessAddress' | string;
        uniqueId?: string | null;
        address?: any;
        coordinates?: any;
    } | null;
    locations?: any[];
    organizer?: {
        emailAddress?: {
            name?: string | null;
            address?: string | null;
        };
    } | null;
    [key: string]: any;
}
export interface MSGraphTokenResponse {
    token_type: string;
    expires_in: number;
    ext_expires_in?: number;
    access_token: string;
}
export interface MSTeamsMessageAttachment {
    id: string;
    name?: string | null;
    contentType?: string | null;
    contentUrl?: string | null;
    size?: number | null;
}
export interface MSTeamsMessageMentionedUser {
    id?: string | null;
    displayName?: string | null;
    userIdentityType?: string | null;
}
export interface MSTeamsMessageMention {
    id: number;
    mentionText?: string | null;
    mentioned?: {
        user?: MSTeamsMessageMentionedUser | null;
        application?: any | null;
        conversation?: any | null;
        tag?: any | null;
    } | null;
}
export interface MSTeamsMessage {
    id: string;
    chatId?: string | null;
    teamId?: string | null;
    channelId?: string | null;
    replyToId?: string | null;
    userId?: string | null;
    userName?: string | null;
    content: string;
    contentType: 'html' | 'text';
    createdDateTime: string;
    lastModifiedDateTime?: string | null;
    webUrl?: string | null;
    attachments?: MSTeamsMessageAttachment[] | null;
    mentions?: MSTeamsMessageMention[] | null;
    raw?: any;
}
export interface ZoomTokenResponse {
    access_token: string;
    token_type: string;
    expires_in: number;
    scope: string;
}
export interface ListZoomMeetingsData {
    meetings: ZoomMeeting[];
    page_count?: number;
    page_number?: number;
    page_size?: number;
    total_records?: number;
    next_page_token?: string;
}
export interface ZoomMeeting {
    uuid: string;
    id: string;
    host_id?: string;
    topic: string;
    type: number;
    start_time?: string;
    duration?: number;
    timezone?: string;
    agenda?: string;
    created_at: string;
    join_url: string;
    [key: string]: any;
}
export type NotionTaskStatus = 'To Do' | 'In Progress' | 'Done' | 'Blocked' | 'Cancelled';
export type NotionTaskPriority = 'High' | 'Medium' | 'Low';
export interface NotionTask {
    id: string;
    description: string;
    dueDate?: string | null;
    status: NotionTaskStatus;
    priority?: NotionTaskPriority | null;
    listName?: string | null;
    createdDate: string;
    url: string;
    notes?: string | null;
    last_edited_time?: string;
}
export interface CreateNotionTaskParams {
    description: string;
    dueDate?: string | null;
    status?: NotionTaskStatus;
    priority?: NotionTaskPriority | null;
    listName?: string | null;
    notes?: string | null;
    notionTasksDbId: string;
    parentId?: string | null;
}
export interface NotionTaskResponse {
    success: boolean;
    message: string;
    taskId?: string;
    taskUrl?: string;
    error?: string;
}
export interface QueryNotionTasksParams {
    status?: NotionTaskStatus | NotionTaskStatus[];
    dueDateBefore?: string | null;
    dueDateAfter?: string | null;
    dateQuery?: string | null;
    priority?: NotionTaskPriority | null;
    listName?: string | null;
    descriptionContains?: string | null;
    notionTasksDbId: string;
    limit?: number;
}
export interface TaskQueryResponse {
    success: boolean;
    tasks: NotionTask[];
    message?: string;
    error?: string;
}
export interface UpdateNotionTaskParams {
    taskId: string;
    description?: string;
    dueDate?: string | null;
    status?: NotionTaskStatus;
    priority?: NotionTaskPriority | null;
    listName?: string | null;
    notes?: string | null;
}
export interface CreateTaskData {
    taskId: string;
    taskUrl: string;
    message?: string;
}
export interface UpdateTaskData {
    taskId: string;
    updatedProperties: string[];
    message?: string;
}
export type EmailActionType = 'FIND_SPECIFIC_INFO' | 'GET_SENDER' | 'GET_SUBJECT' | 'GET_DATE' | 'GET_FULL_CONTENT' | 'SUMMARIZE_EMAIL';
export interface ResolvedAttendee {
    email: string;
    name?: string;
    userId?: string;
    source: 'atom_user' | 'google_contact' | 'hubspot_contact' | 'email_direct' | 'unresolved';
    status?: 'found' | 'not_found' | 'error_resolving';
    errorMessage?: string;
}
export interface ContactSkillResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface UserWorkTime {
    dayOfWeek: 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
    startTime: string;
    endTime: string;
}
export interface UserAvailability {
    userId: string;
    workTimes: UserWorkTime[];
    calendarEvents: CalendarEvent[];
}
export interface NotionPageContext {
    id: string;
    title: string;
    url?: string;
    briefSnippet?: string;
}
export interface EmailContext {
    id: string;
    subject: string;
    sender?: string;
    receivedDate?: string;
    url?: string;
    briefSnippet?: string;
}
export interface TaskContext {
    id: string;
    description: string;
    dueDate?: string | null;
    status?: NotionTaskStatus;
    url?: string;
}
export interface MeetingPreparationData {
    targetMeeting: CalendarEvent;
    relatedNotionPages?: NotionPageContext[];
    relatedEmails?: EmailContext[];
    relatedTasks?: TaskContext[];
    keyPointsFromLastMeeting?: string;
    errorMessage?: string;
}
export interface PrepareForMeetingResponse extends SkillResponse<MeetingPreparationData> {
}
export interface PrepareForMeetingEntities {
    meeting_identifier?: string;
    meeting_date_time?: string;
}
export interface WeeklyDigestData {
    periodStart: string;
    periodEnd: string;
    completedTasks: NotionTask[];
    attendedMeetings: CalendarEvent[];
    upcomingCriticalTasks: NotionTask[];
    upcomingCriticalMeetings: CalendarEvent[];
    errorMessage?: string;
}
export interface GenerateWeeklyDigestResponse extends SkillResponse<{
    digest: WeeklyDigestData;
    formattedSummary: string;
}> {
}
export interface GenerateWeeklyDigestEntities {
    time_period?: 'this week' | 'last week' | string;
}
export type PotentialFollowUpType = 'action_item' | 'decision' | 'question' | 'information';
export interface PotentialFollowUp {
    type: PotentialFollowUpType;
    description: string;
    suggestedAssignee?: string;
    sourceContext?: string;
    existingTaskFound?: boolean;
    existingTaskId?: string;
    existingTaskUrl?: string;
}
export interface ExtractedFollowUpItems {
    action_items: Array<{
        description: string;
        assignee?: string;
    }>;
    decisions: Array<{
        description: string;
    }>;
    questions: Array<{
        description: string;
    }>;
}
export interface FollowUpSuggestionData {
    contextName: string;
    sourceDocumentSummary?: string;
    suggestions: PotentialFollowUp[];
    errorMessage?: string;
}
export interface SuggestFollowUpsResponse extends SkillResponse<FollowUpSuggestionData> {
}
export interface SuggestFollowUpsEntities {
    context_identifier: string;
    context_type?: 'meeting' | 'project' | string;
}
/**
 * Represents the parsed entities from the NLU service for a RequestMeetingPreparation intent.
 * This should align with the 'entities' structure defined for intent #35 in nluService.ts.
 */
export interface MeetingPrepNluEntities {
    meeting_reference: string;
    information_requests: InformationRequest[];
    overall_lookback_period?: string;
}
/**
 * Defines a single information request within a meeting preparation task.
 */
export interface InformationRequest {
    source: 'gmail' | 'slack' | 'notion' | 'calendar_events';
    search_parameters: GmailSearchParameters | SlackSearchParameters | NotionSearchParameters | CalendarEventsSearchParameters;
}
export interface GmailSearchParameters {
    from_sender?: string;
    subject_keywords?: string;
    body_keywords?: string;
    date_query?: string;
    has_attachment_only?: boolean;
}
export interface SlackSearchParameters {
    channel_name?: string;
    from_user?: string;
    text_keywords?: string;
    date_query?: string;
    mentions_user?: string;
}
export interface NotionSearchParameters {
    database_name_or_id?: string;
    page_title_keywords?: string;
    content_keywords?: string;
    filter_by_meeting_reference_context?: boolean;
}
export interface CalendarEventsSearchParameters {
    related_to_attendees_of_meeting_reference?: boolean;
    keywords_in_summary_or_description?: string;
    date_query_lookback?: string;
    type_filter?: 'past_events' | 'future_events' | 'all_related_events';
}
/**
 * Represents the aggregated results from all information requests for meeting preparation.
 * This is what the meeting preparation skill would aim to construct.
 */
export interface AggregatedPrepResults {
    meeting_reference_identified: string;
    identified_calendar_event?: CalendarEventSummary;
    results_by_source: PrepResultSourceEntry[];
    overall_summary_notes?: string;
    errors_encountered?: PrepErrorMessage[];
}
export interface PrepResultSourceEntry {
    source: 'gmail' | 'slack' | 'notion' | 'calendar_events';
    search_parameters_used: GmailSearchParameters | SlackSearchParameters | NotionSearchParameters | CalendarEventsSearchParameters;
    results: GmailMessageSnippet[] | SlackMessageSnippet[] | NotionPageSummary[] | CalendarEventSummary[];
    error_message?: string;
    count: number;
    search_query_executed?: string;
}
export interface PrepErrorMessage {
    source_attempted?: 'gmail' | 'slack' | 'notion' | 'calendar_events' | 'overall_process' | 'nlu_parsing' | 'calendar_lookup';
    message: string;
    details?: string;
}
export interface GmailMessageSnippet {
    id: string;
    threadId?: string;
    subject?: string;
    from?: string;
    date?: string;
    snippet?: string;
    link?: string;
}
export interface SlackMessageSnippet {
    ts: string;
    channel?: {
        id: string;
        name?: string;
    };
    user?: {
        id: string;
        name?: string;
    };
    text?: string;
    permalink?: string;
    files?: any[];
    reactions?: any[];
    thread_ts?: string;
}
export interface NotionPageSummary {
    id: string;
    title?: string;
    url?: string;
    last_edited_time?: string;
    created_time?: string;
    preview_text?: string;
    icon?: {
        type: string;
        emoji?: string;
        external?: {
            url: string;
        };
        file?: {
            url: string;
            expiry_time: string;
        };
    } | null;
}
export interface CalendarEventSummary {
    id: string;
    summary?: string;
    description?: string;
    start?: string;
    end?: string;
    htmlLink?: string;
    attendees?: Array<{
        email?: string;
        displayName?: string;
        responseStatus?: string;
    }>;
    organizer?: {
        email?: string;
        displayName?: string;
    };
}
/**
 * Represents the parsed entities from the NLU service for a ProcessMeetingOutcomes intent.
 * Aligns with intent #36 in nluService.ts.
 */
export interface ProcessMeetingOutcomesNluEntities {
    meeting_reference: string;
    source_document_id?: string;
    outcome_source_type?: 'transcript' | 'meeting_notes' | 'audio_recording_summary';
    requested_actions: Array<'SUMMARIZE_KEY_DECISIONS' | 'EXTRACT_ACTION_ITEMS' | 'DRAFT_FOLLOW_UP_EMAIL' | 'CREATE_TASKS_IN_NOTION'>;
    email_draft_details?: {
        recipients: string[] | string;
        additional_instructions?: string;
    };
    task_creation_details?: {
        notion_database_id?: string;
        default_assignee?: string;
    };
}
/**
 * Represents structured information extracted from meeting outcomes.
 * This would be an interim result after an LLM processes the source document.
 */
export interface ExtractedMeetingInsights {
    meeting_title_or_reference: string;
    source_document_id_processed?: string;
    key_decisions?: string[];
    action_items?: Array<{
        description: string;
        suggested_assignee?: string;
        suggested_due_date?: string;
    }>;
    overall_summary?: string;
}
/**
 * Represents the results of performing the requested post-meeting actions.
 */
export interface PostMeetingActionsResults {
    processed_meeting_reference: string;
    summary_of_decisions?: string;
    extracted_action_items_summary?: string;
    drafted_email_content?: {
        to?: string[];
        cc?: string[];
        subject?: string;
        body?: string;
    };
    created_notion_tasks?: Array<{
        taskId: string;
        taskUrl: string;
        description: string;
        assignee?: string;
        dueDate?: string;
    }>;
    errors_encountered?: Array<{
        action_attempted: 'SUMMARIZE_KEY_DECISIONS' | 'EXTRACT_ACTION_ITEMS' | 'DRAFT_FOLLOW_UP_EMAIL' | 'CREATE_TASKS_IN_NOTION' | 'SOURCE_PROCESSING';
        message: string;
        details?: string;
    }>;
}
export interface ProcessMeetingOutcomesSkillResponse extends SkillResponse<PostMeetingActionsResults> {
}
/**
 * Represents the parsed entities from the NLU service for a GetDailyPriorityBriefing intent.
 * Aligns with intent #37 in nluService.ts.
 */
export interface GetDailyPriorityBriefingNluEntities {
    date_context?: string;
    focus_areas?: Array<'tasks' | 'meetings' | 'urgent_emails' | 'urgent_slack_messages' | 'urgent_teams_messages'>;
    project_filter?: string;
    urgency_level?: 'high' | 'critical' | 'all';
}
/**
 * Represents a summarized item for the daily briefing.
 * Generic enough to hold different types of priority items.
 */
export interface BriefingItem {
    type: 'task' | 'meeting' | 'email' | 'slack_message' | 'teams_message';
    title: string;
    details?: string;
    urgency_score?: number;
    source_id?: string;
    link?: string;
    raw_item?: NotionTask | CalendarEventSummary | GmailMessageSnippet | SlackMessageSnippet | MSTeamsMessage;
}
/**
 * Represents the consolidated data for the daily priority briefing.
 * This is what the skill would construct.
 */
export interface DailyBriefingData {
    briefing_date: string;
    user_id: string;
    priority_items: BriefingItem[];
    overall_summary_message?: string;
    errors_encountered?: Array<{
        source_area: 'tasks' | 'meetings' | 'emails' | 'slack' | 'teams' | 'overall';
        message: string;
        details?: string;
    }>;
}
export interface GetDailyPriorityBriefingSkillResponse extends SkillResponse<DailyBriefingData> {
}
/**
 * Represents the parsed entities from the NLU service for a CreateTaskFromChatMessage intent.
 * Aligns with intent #38 in nluService.ts.
 */
export interface CreateTaskFromChatMessageNluEntities {
    chat_message_reference: string;
    source_platform: 'slack' | 'msteams' | 'gmail_thread_item';
    task_description_override?: string;
    target_task_list_or_project?: string;
    assignee?: string;
    due_date?: string;
    priority?: 'high' | 'medium' | 'low';
}
/**
 * Represents the fetched content of a chat message from Slack, Teams, or a Gmail item.
 * This structure would be populated by a skill that retrieves the message.
 */
export interface ChatMessageContent {
    platform: 'slack' | 'msteams' | 'gmail_thread_item';
    message_id?: string;
    channel_id?: string;
    thread_id?: string;
    sender_id?: string;
    sender_name?: string;
    text_content: string;
    html_content?: string;
    message_url?: string;
    timestamp: string;
    attachments?: Array<{
        name?: string;
        url?: string;
        type?: string;
    }>;
}
/**
 * Represents the result of attempting to create a task.
 * This would be part of the skill's output.
 */
export interface TaskCreationResultFromMessage {
    success: boolean;
    message: string;
    taskId?: string;
    taskUrl?: string;
    taskTitle?: string;
    original_message_link_included?: boolean;
}
export interface CreateTaskFromChatMessageSkillResponse extends SkillResponse<TaskCreationResultFromMessage> {
}
/**
 * Represents the NLU structure for a sub-task within a ComplexTask.
 * This is already part of ProcessedNLUResponse's sub_tasks definition,
 * but defined here for clarity in the context of execution results.
 */
export interface ComplexTaskSubTaskNlu {
    intent: string | null;
    entities: Record<string, any>;
    summary_for_sub_task?: string;
}
/**
 * Represents the result of executing a single sub-task identified within a ComplexTask.
 */
export interface ExecutedSubTaskResult {
    sub_task_nlu: ComplexTaskSubTaskNlu;
    execution_order: number;
    status: 'success' | 'failure' | 'skipped' | 'partial_success';
    message_from_handler?: string;
    error_details?: string;
    returned_data?: any;
}
/**
 * Represents the overall report of an orchestrated ComplexTask execution.
 * This would be constructed by the logic handling the main ComplexTask intent.
 */
export interface OrchestratedComplexTaskReport {
    original_user_query: string;
    overall_status: 'completed_fully' | 'completed_partially' | 'failed_entirely' | 'clarification_needed_mid_sequence';
    final_summary_message_for_user?: string;
    sub_task_results: ExecutedSubTaskResult[];
    inter_task_context?: Record<string, any>;
}
/**
 * Defines the structure of commands sent from the agent to the client (e.g., via WebSocket)
 * This should align with the command structure expected by the frontend client.
 */
export interface AgentClientCommand {
    command_id: string;
    action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
    payload?: {
        suggestedTitle?: string;
        linkedEventId?: string;
    };
}
/**
 * Defines the context object that will be passed to agent skills.
 * It includes common utilities or functions that skills might need.
 */
export interface AgentSkillContext {
    userId: string;
    sendCommandToClient: (userId: string, command: AgentClientCommand) => Promise<boolean>;
}
export type SearchResultSourceType = 'document_chunk' | 'email_snippet' | 'notion_summary';
export interface UniversalSearchResultItem {
    id: string;
    user_id: string;
    source_type: SearchResultSourceType;
    title: string;
    snippet: string;
    vector_score: number;
    original_url_or_link?: string;
    created_at?: string;
    last_modified_at?: string;
    ingested_at?: string;
    document_id?: string;
    parent_document_title?: string;
    chunk_sequence?: number;
    document_source_uri?: string;
    document_doc_type?: string;
    email_thread_id?: string;
    email_from_sender?: string;
    email_date?: string;
    notion_icon_json?: string;
    metadata_json?: string;
}
export type HybridMatchSource = 'semantic' | 'keyword';
/**
 * Represents a unified search result item from the hybrid search backend.
 * Mirrors the `UnifiedSearchResultItem` Pydantic model in `hybrid_search_service.py`.
 */
export interface HybridSearchResultItem {
    doc_id: string;
    user_id: string;
    title?: string | null;
    snippet?: string | null;
    source_uri?: string | null;
    doc_type?: string | null;
    created_at_source?: string | null;
    last_modified_source?: string | null;
    ingested_at: string;
    score?: number | null;
    match_type: HybridMatchSource;
    extracted_text_preview?: string | null;
    additional_properties?: Record<string, any> | null;
}
/**
 * Defines the structure for the filters object used in hybrid search.
 * This should be constructed by the frontend and passed to the search skill.
 */
export interface HybridSearchFilters {
    doc_types?: string[];
    date_after?: string;
    date_before?: string;
    date_field_to_filter?: 'ingested_at' | 'created_at_source' | 'last_modified_source';
    metadata_properties?: Record<string, string>;
}
export interface DropboxConnectionStatusInfo {
    isConnected: boolean;
    email?: string;
    reason?: string;
}
export interface DropboxFile {
    type: 'file' | 'folder';
    name: string;
    id: string;
    path_lower?: string;
    size?: number;
    server_modified?: string;
}
export interface TrelloBoard {
    id: string;
    name: string;
    url: string;
}
export interface TrelloList {
    id: string;
    name: string;
}
export interface TrelloCard {
    id: string;
    name: string;
    desc: string;
    url: string;
}
export interface SalesforceContact {
    Id: string;
    Name: string;
    Email?: string;
}
export interface SalesforceAccount {
    Id: string;
    Name: string;
}
export interface SalesforceOpportunity {
    Id: string;
    Name: string;
    StageName: string;
    Amount?: number;
    CloseDate: string;
}
export interface ShopifyProduct {
    id: number;
    title: string;
    vendor: string;
    product_type: string;
    status: 'active' | 'archived' | 'draft';
    variants: Array<{
        id: number;
        price: string;
        sku: string;
        inventory_quantity: number;
    }>;
}
export interface ShopifyOrder {
    id: number;
    name: string;
    email: string;
    total_price: string;
    financial_status: 'pending' | 'authorized' | 'partially_paid' | 'paid' | 'partially_refunded' | 'refunded' | 'voided';
    fulfillment_status: 'fulfilled' | 'unfulfilled' | 'partial' | null;
    line_items: Array<{
        id: number;
        name: string;
        sku: string;
        quantity: number;
        price: string;
    }>;
}
export interface XeroInvoice {
    InvoiceID: string;
    InvoiceNumber?: string;
    Contact: {
        ContactID: string;
        Name: string;
    };
    DateString: string;
    DueDateString: string;
    Total: number;
    AmountDue: number;
    Status: string;
}
export interface XeroBill {
    InvoiceID: string;
    InvoiceNumber?: string;
    Contact: {
        ContactID: string;
        Name: string;
    };
    DateString: string;
    DueDateString: string;
    Total: number;
    AmountDue: number;
    Status: string;
}
export interface XeroContact {
    ContactID: string;
    Name: string;
    EmailAddress?: string;
}
export interface Tweet {
    id_str: string;
    text: string;
    user: {
        name: string;
        screen_name: string;
    };
    created_at: string;
}
export interface ScheduleSkillActivationEntities {
    skill_to_schedule: string;
    activation_time: string;
    skill_entities: Record<string, any>;
}
