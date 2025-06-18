SET check_function_bodies = false;
CREATE OR REPLACE FUNCTION public."set_current_timestamp_updatedAt"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  _new record;
BEGIN
  _new := NEW;
  _new."updatedAt" = NOW();
  RETURN _new;
END;
$$;
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  _new record;
BEGIN
  _new := NEW;
  _new."updated_at" = NOW();
  RETURN _new;
END;
$$;
CREATE TABLE public."Attendee" (
    id text DEFAULT public.gen_random_uuid() NOT NULL,
    name text NOT NULL,
    "userId" uuid NOT NULL,
    "contactId" text,
    emails jsonb,
    "phoneNumbers" jsonb,
    "imAddresses" jsonb,
    "eventId" text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "additionalGuests" integer DEFAULT 0,
    comment text,
    optional boolean DEFAULT false NOT NULL,
    "responseStatus" text,
    resource boolean DEFAULT false NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Attendee" IS 'attendees to an event';
CREATE TABLE public."Autopilot" (
    id uuid NOT NULL,
    "userId" uuid NOT NULL,
    "scheduleAt" timestamp without time zone NOT NULL,
    timezone text NOT NULL,
    payload jsonb,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL
);
COMMENT ON TABLE public."Autopilot" IS 'autopilot to create recurring scheduled triggers';
CREATE TABLE public."Calendar" (
    id text DEFAULT public.gen_random_uuid() NOT NULL,
    "userId" uuid NOT NULL,
    title text,
    "backgroundColor" text,
    account jsonb,
    "accessLevel" text,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    modifiable boolean DEFAULT false NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "defaultReminders" jsonb,
    resource text,
    "primary" boolean DEFAULT false,
    "globalPrimary" boolean DEFAULT false,
    "colorId" text,
    "foregroundColor" text,
    "pageToken" text,
    "syncToken" text
);
CREATE TABLE public."Calendar_Integration" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "userId" uuid NOT NULL,
    token text,
    "refreshToken" text,
    resource text,
    name text NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "expiresAt" timestamp with time zone,
    "syncEnabled" boolean DEFAULT false NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "appId" text,
    "appEmail" text,
    "appAccountId" text,
    username text,
    password text,
    "contactName" text,
    "contactEmail" text,
    colors jsonb,
    "pageToken" text,
    "syncToken" text,
    "clientType" text,
    "contactFirstName" text,
    "contactLastName" text,
    "phoneCountry" text,
    "phoneNumber" text
);
CREATE TABLE public."Calendar_Push_Notification" (
    id text NOT NULL,
    "userId" uuid NOT NULL,
    "resourceId" text NOT NULL,
    "calendarId" text NOT NULL,
    token text NOT NULL,
    "resourceUri" text NOT NULL,
    expiration timestamp with time zone,
    "calendarIntegrationId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "createdDate" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Calendar_Push_Notification" IS 'calendar push notification for calendars';

COMMENT ON TABLE public."Calendar_Integration" IS 'integrations for the calendar';
CREATE TABLE public."Category" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    name text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "userId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "copyAvailability" boolean DEFAULT false,
    "copyTimeBlocking" boolean,
    "copyTimePreference" boolean DEFAULT false,
    "copyReminders" boolean DEFAULT false,
    "copyPriorityLevel" boolean DEFAULT false,
    "copyModifiable" boolean DEFAULT false,
    "defaultAvailability" boolean DEFAULT false,
    "defaultTimeBlocking" jsonb,
    "defaultTimePreference" jsonb,
    "defaultReminders" jsonb,
    "defaultPriorityLevel" integer,
    "defaultModifiable" boolean,
    "copyIsBreak" boolean,
    color text,
    "defaultIsBreak" boolean DEFAULT false,
    "copyMeetingModifiable" boolean DEFAULT false,
    "copyExternalMeetingModifiable" boolean DEFAULT false,
    "copyIsMeeting" boolean DEFAULT false,
    "copyIsExternalMeeting" boolean DEFAULT false,
    "defaultIsMeeting" boolean DEFAULT false,
    "defaultIsExternalMeeting" boolean DEFAULT false,
    "defaultMeetingModifiable" boolean DEFAULT true,
    "defaultExternalMeetingModifiable" boolean DEFAULT true
);
COMMENT ON TABLE public."Category" IS 'category for events';
CREATE TABLE public."Category_Event" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "categoryId" uuid NOT NULL,
    "eventId" text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "userId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Category_Event" IS 'many to many relationship';
CREATE TABLE public."Chat_Meeting_Preference" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "userId" uuid NOT NULL,
    timezone text,
    "sendUpdates" text DEFAULT 'all'::text,
    "guestsCanInviteOthers" boolean DEFAULT true,
    transparency text DEFAULT 'opaque'::text,
    visibility text DEFAULT 'default'::text,
    "useDefaultAlarms" boolean DEFAULT true,
    reminders jsonb,
    duration integer DEFAULT 30,
    "enableConference" boolean DEFAULT false,
    "conferenceApp" text DEFAULT 'google'::text,
    "bufferTime" jsonb,
    "anyoneCanAddSelf" boolean DEFAULT false,
    "guestsCanSeeOtherGuests" boolean DEFAULT true,
    name text,
    "primaryEmail" text,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "lockAfter" boolean DEFAULT true
);
COMMENT ON TABLE public."Chat_Meeting_Preference" IS 'meeting preferences for chat';
CREATE TABLE public."Conference" (
    id text DEFAULT public.gen_random_uuid() NOT NULL,
    "requestId" uuid DEFAULT public.gen_random_uuid() NOT NULL,
    type text,
    status text,
    "calendarId" text NOT NULL,
    "iconUri" text,
    name text,
    notes text,
    "entryPoints" jsonb,
    parameters jsonb,
    app text,
    "userId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "createdDate" timestamp with time zone DEFAULT now(),
    deleted boolean DEFAULT false NOT NULL,
    key text,
    "hangoutLink" text,
    "joinUrl" text,
    "startUrl" text,
    "zoomPrivateMeeting" boolean DEFAULT false,
    "isHost" boolean DEFAULT false
);
COMMENT ON TABLE public."Conference" IS 'zoom or google meet conferences, will be modified to match each service';
CREATE TABLE public."Contact" (
    id text DEFAULT public.gen_random_uuid() NOT NULL,
    name text,
    "firstName" text,
    "middleName" text,
    "lastName" text,
    "maidenName" text,
    "namePrefix" text,
    "nameSuffix" text,
    nickname text,
    "phoneticFirstName" text,
    "phoneticMiddleName" text,
    "phoneticLastName" text,
    company text,
    "jobTitle" text,
    department text,
    notes text,
    "imageAvailable" boolean DEFAULT false NOT NULL,
    image text,
    "contactType" text DEFAULT 'person'::text NOT NULL,
    emails jsonb,
    "phoneNumbers" jsonb,
    "imAddresses" jsonb,
    "linkAddresses" jsonb,
    "userId" uuid NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    app text
);
CREATE TABLE public."Contact_Event" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "contactId" text NOT NULL,
    "eventId" text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "userId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Contact_Event" IS 'many to many relationships for contact and events';
CREATE TABLE public."Event" (
    id text NOT NULL,
    "userId" uuid NOT NULL,
    title text,
    "startDate" timestamp without time zone DEFAULT now() NOT NULL,
    "endDate" timestamp without time zone DEFAULT now() NOT NULL,
    "allDay" boolean DEFAULT false,
    "recurrenceRule" jsonb,
    location jsonb,
    notes text,
    attachments jsonb,
    links jsonb,
    timezone text,
    "createdDate" timestamp with time zone DEFAULT now(),
    deleted boolean DEFAULT false,
    "taskId" uuid,
    "taskType" text,
    priority integer DEFAULT 1,
    "followUpEventId" text,
    "isFollowUp" boolean DEFAULT false,
    "isPreEvent" boolean DEFAULT false,
    "isPostEvent" boolean DEFAULT false,
    "preEventId" text,
    "postEventId" text,
    modifiable boolean DEFAULT false,
    "forEventId" text,
    "conferenceId" text,
    "maxAttendees" integer DEFAULT 1,
    "sendUpdates" text,
    "anyoneCanAddSelf" boolean DEFAULT false,
    "guestsCanInviteOthers" boolean DEFAULT true,
    "guestsCanSeeOtherGuests" boolean DEFAULT true,
    "originalStartDate" timestamp with time zone DEFAULT now(),
    "originalAllDay" boolean DEFAULT false,
    status text,
    summary text,
    transparency text,
    visibility text,
    "recurringEventId" text,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "iCalUID" text,
    "htmlLink" text,
    "colorId" text,
    creator jsonb,
    organizer jsonb,
    "endTimeUnspecified" boolean DEFAULT false,
    recurrence jsonb,
    "originalTimezone" text,
    "attendeesOmitted" boolean DEFAULT false,
    "extendedProperties" jsonb,
    "hangoutLink" text,
    "guestsCanModify" boolean DEFAULT false,
    locked boolean DEFAULT false,
    source jsonb,
    "eventType" text,
    "privateCopy" boolean DEFAULT false,
    "calendarId" text NOT NULL,
    "backgroundColor" text,
    "foregroundColor" text,
    "useDefaultAlarms" boolean DEFAULT true,
    "positiveImpactScore" integer DEFAULT 0,
    "negativeImpactScore" integer DEFAULT 0,
    "positiveImpactDayOfWeek" integer,
    "positiveImpactTime" time without time zone,
    "negativeImpactDayOfWeek" integer,
    "negativeImpactTime" time without time zone,
    "preferredDayOfWeek" integer,
    "preferredTime" time without time zone,
    "isExternalMeeting" boolean,
    "isExternalMeetingModifiable" boolean,
    "isMeetingModifiable" boolean,
    "isMeeting" boolean,
    "dailyTaskList" boolean,
    "weeklyTaskList" boolean,
    "isBreak" boolean,
    "preferredStartTimeRange" time without time zone,
    "preferredEndTimeRange" time without time zone,
    "copyAvailability" boolean,
    "copyTimeBlocking" boolean,
    "copyTimePreference" boolean,
    "copyReminders" boolean,
    "copyPriorityLevel" boolean,
    "copyModifiable" boolean,
    "copyCategories" boolean,
    "copyIsBreak" boolean,
    "timeBlocking" jsonb,
    "userModifiedAvailability" boolean DEFAULT false,
    "userModifiedTimeBlocking" boolean DEFAULT false,
    "userModifiedTimePreference" boolean DEFAULT false,
    "userModifiedReminders" boolean DEFAULT false,
    "userModifiedPriorityLevel" boolean DEFAULT false,
    "userModifiedCategories" boolean DEFAULT false,
    "userModifiedModifiable" boolean DEFAULT false,
    "userModifiedIsBreak" boolean DEFAULT false,
    "softDeadline" timestamp without time zone,
    "hardDeadline" timestamp without time zone,
    "copyMeetingModifiable" boolean DEFAULT false,
    "copyExternalMeetingModifiable" boolean DEFAULT false,
    "userModifiedMeetingModifiable" boolean DEFAULT false,
    "userModifiedExternalMeetingModifiable" boolean DEFAULT false,
    "copyIsMeeting" boolean DEFAULT false,
    "copyIsExternalMeeting" boolean DEFAULT false,
    "userModifiedIsMeeting" boolean DEFAULT false,
    "userModifiedIsExternalMeeting" boolean DEFAULT false,
    duration integer,
    "copyDuration" boolean DEFAULT false,
    "userModifiedDuration" boolean DEFAULT false,
    method text,
    unlink boolean DEFAULT false,
    "copyColor" boolean DEFAULT false,
    "userModifiedColor" boolean DEFAULT false,
    "byWeekDay" jsonb,
    "localSynced" boolean DEFAULT false,
    "meetingId" text,
    "eventId" text
);
CREATE TABLE public."Event_Trigger" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    resource text NOT NULL,
    name text NOT NULL,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "userId" uuid NOT NULL,
    "resourceId" text NOT NULL
);
COMMENT ON TABLE public."Event_Trigger" IS 'event triggers created to sync data';
CREATE TABLE public."Invite" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "userId" uuid NOT NULL,
    emails jsonb,
    "phoneNumbers" jsonb,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    name text,
    "eventId" uuid,
    "imAddresses" jsonb,
    categories jsonb,
    "availableSlots" jsonb,
    "emailId" text,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "contactId" text,
    "phoneId" text
);
COMMENT ON TABLE public."Invite" IS 'invite table for custom calendars';
CREATE TABLE public."Meeting_Assist" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "eventId" text,
    "userId" uuid NOT NULL,
    summary text,
    notes text,
    "windowStartDate" timestamp without time zone NOT NULL,
    "windowEndDate" timestamp without time zone NOT NULL,
    timezone text,
    location jsonb,
    priority integer DEFAULT 1 NOT NULL,
    "sendUpdates" text DEFAULT 'all'::text,
    "guestsCanInviteOthers" boolean DEFAULT true NOT NULL,
    transparency text DEFAULT 'opaque'::text,
    visibility text DEFAULT 'default'::text,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "colorId" text,
    "backgroundColor" text,
    "foregroundColor" text,
    "useDefaultAlarms" boolean DEFAULT false NOT NULL,
    reminders jsonb,
    "cancelIfAnyRefuse" boolean DEFAULT false,
    "enableHostPreferences" boolean DEFAULT true,
    "enableAttendeePreferences" boolean DEFAULT true,
    "startDate" timestamp without time zone,
    "endDate" timestamp without time zone,
    "attendeeCount" integer DEFAULT 1,
    "expireDate" timestamp without time zone,
    "attendeeRespondedCount" integer DEFAULT 1,
    cancelled boolean DEFAULT false,
    duration integer DEFAULT 30,
    "enableConference" boolean DEFAULT false,
    "conferenceApp" text,
    "calendarId" text NOT NULL,
    "bufferTime" jsonb,
    "anyoneCanAddSelf" boolean DEFAULT true,
    "guestsCanSeeOtherGuests" boolean DEFAULT true,
    "minThresholdCount" integer,
    "allowAttendeeUpdatePreferences" boolean DEFAULT false,
    "guaranteeAvailability" boolean DEFAULT false,
    frequency text DEFAULT 'weekly'::text,
    "interval" integer DEFAULT 1,
    until timestamp without time zone,
    "originalMeetingId" uuid,
    "attendeeCanModify" boolean DEFAULT false,
    "lockAfter" boolean DEFAULT false
);
COMMENT ON TABLE public."Meeting_Assist" IS 'meeting assist for scheduling meetings using AI';
CREATE TABLE public."Meeting_Assist_Attendee" (
    id text NOT NULL,
    name text,
    "hostId" uuid NOT NULL,
    "userId" uuid DEFAULT gen_random_uuid() NOT NULL,
    emails jsonb,
    "contactId" text,
    "phoneNumbers" jsonb,
    "imAddresses" jsonb,
    "meetingId" uuid NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    timezone text,
    "externalAttendee" boolean DEFAULT false NOT NULL,
    "primaryEmail" text
);
COMMENT ON TABLE public."Meeting_Assist_Attendee" IS 'attendees for meeting assist using AI';
CREATE TABLE public."Meeting_Assist_Calendar" (
    id text NOT NULL,
    "attendeeId" text NOT NULL,
    title text,
    "backgroundColor" text,
    account jsonb,
    "accessLevel" text,
    modifiable boolean DEFAULT false NOT NULL,
    "defaultReminders" jsonb,
    resource text,
    "primary" boolean DEFAULT false,
    "colorId" text,
    "foregroundColor" text
);
COMMENT ON TABLE public."Meeting_Assist_Calendar" IS 'temporary calendar holder for meeting assist using AI';
CREATE TABLE public."Meeting_Assist_Comment" (
    id uuid NOT NULL,
    "userId" uuid NOT NULL,
    content text NOT NULL,
    "meetingId" uuid NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "replyId" uuid,
    username text NOT NULL,
    "profileId" uuid,
    avatar text
);
COMMENT ON TABLE public."Meeting_Assist_Comment" IS 'comments on new meeting assists using AI';
CREATE TABLE public."Meeting_Assist_Event" (
    id text NOT NULL,
    summary text,
    notes text,
    "startDate" timestamp without time zone DEFAULT now() NOT NULL,
    "endDate" timestamp without time zone DEFAULT now() NOT NULL,
    "allDay" boolean DEFAULT false NOT NULL,
    "recurrenceRule" jsonb,
    location jsonb,
    attachments jsonb,
    links jsonb,
    timezone text,
    transparency text,
    visibility text,
    "recurringEventId" text,
    "iCalUID" text,
    "htmlLink" text,
    "colorId" text,
    creator jsonb,
    organizer jsonb,
    "endTimeUnspecified" boolean DEFAULT false,
    recurrence jsonb,
    "attendeesOmitted" boolean DEFAULT false,
    "extendedProperties" jsonb,
    "hangoutLink" text,
    "guestsCanModify" boolean DEFAULT false,
    locked boolean DEFAULT false,
    source jsonb,
    "eventType" text,
    "privateCopy" boolean DEFAULT false,
    "calendarId" text NOT NULL,
    "backgroundColor" text,
    "foregroundColor" text,
    "useDefaultAlarms" boolean DEFAULT true,
    "externalUser" boolean DEFAULT true,
    "createdDate" timestamp with time zone DEFAULT now(),
    "updatedAt" timestamp with time zone DEFAULT now(),
    "attendeeId" text NOT NULL,
    "meetingId" uuid,
    "eventId" text
);
COMMENT ON TABLE public."Meeting_Assist_Event" IS 'temporary events holding for outside users for meeting assist';
CREATE TABLE public."Meeting_Assist_Invite" (
    id text NOT NULL,
    "hostId" uuid NOT NULL,
    email text,
    "hostName" text,
    "meetingId" uuid NOT NULL,
    name text NOT NULL,
    "createdDate" timestamp without time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "userId" uuid,
    response text DEFAULT 'PENDING'::text,
    "contactId" text
);
COMMENT ON TABLE public."Meeting_Assist_Invite" IS 'meeting assist invite links';
CREATE TABLE public."Meeting_Assist_Preferred_Time_Range" (
    id uuid NOT NULL,
    "meetingId" uuid NOT NULL,
    "dayOfWeek" integer,
    "startTime" time without time zone NOT NULL,
    "endTime" time without time zone NOT NULL,
    "hostId" uuid NOT NULL,
    "attendeeId" text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL
);
COMMENT ON TABLE public."Meeting_Assist_Preferred_Time_Range" IS 'preferred times for meeting assist using AI';
CREATE TABLE public."PreferredTimeRange" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "eventId" text NOT NULL,
    "dayOfWeek" integer,
    "startTime" time without time zone NOT NULL,
    "endTime" time without time zone NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now() NOT NULL,
    "userId" uuid NOT NULL
);
COMMENT ON TABLE public."PreferredTimeRange" IS 'preferred time ranges for event';
CREATE TABLE public."Relationship" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    name text NOT NULL,
    label text NOT NULL,
    "contactId" text NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "userId" uuid NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Relationship" IS 'relationships to contacts';
CREATE TABLE public."Reminder" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "eventId" text NOT NULL,
    "userId" uuid NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "reminderDate" timestamp with time zone,
    timezone text,
    "updatedAt" timestamp with time zone DEFAULT now(),
    minutes integer,
    method text,
    "useDefault" boolean DEFAULT false
);
COMMENT ON TABLE public."Reminder" IS 'reminders for events';
CREATE TABLE public."Task" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    "userId" uuid NOT NULL,
    "eventId" text,
    type text DEFAULT 'Daily'::text NOT NULL,
    notes text NOT NULL,
    "completedDate" timestamp with time zone,
    important boolean DEFAULT false NOT NULL,
    "syncData" jsonb,
    status text DEFAULT 'TODO'::text NOT NULL,
    "parentId" uuid,
    "order" integer,
    priority integer DEFAULT 1,
    "softDeadline" timestamp without time zone,
    "hardDeadline" timestamp without time zone,
    duration integer,
    "updatedAt" timestamp with time zone DEFAULT now()
);
COMMENT ON TABLE public."Task" IS 'create tasks for time blocking';
CREATE TABLE public."User" (
    id uuid NOT NULL,
    email text,
    name text,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "userPreferenceId" uuid
);
CREATE TABLE public."User_Contact_Info" (
    id text NOT NULL,
    "userId" uuid NOT NULL,
    name text,
    type text DEFAULT 'email'::text NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "createdDate" timestamp with time zone DEFAULT now(),
    "primary" boolean DEFAULT false
);
COMMENT ON TABLE public."User_Contact_Info" IS 'alternative contact info for internal users either phone or email as id';
CREATE TABLE public."User_Preference" (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    "userId" uuid NOT NULL,
    "createdDate" timestamp with time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    "isPublicCalendar" boolean DEFAULT false NOT NULL,
    "publicCalendarCategories" jsonb,
    "updatedAt" timestamp with time zone DEFAULT now(),
    "startTimes" jsonb,
    "endTimes" jsonb,
    "copyAvailability" boolean,
    "copyTimeBlocking" boolean,
    "copyTimePreference" boolean,
    "copyReminders" boolean,
    "copyPriorityLevel" boolean,
    "copyModifiable" boolean,
    "copyCategories" boolean,
    "copyIsBreak" boolean,
    reminders jsonb,
    "followUp" jsonb,
    "maxWorkLoadPercent" integer DEFAULT 100,
    "maxNumberOfMeetings" integer DEFAULT 8,
    "backToBackMeetings" boolean DEFAULT false,
    "copyIsMeeting" boolean DEFAULT false,
    "copyIsExternalMeeting" boolean DEFAULT false,
    "onBoarded" boolean DEFAULT false,
    "copyColor" boolean DEFAULT false,
    "minNumberOfBreaks" integer DEFAULT 1,
    "breakLength" integer DEFAULT 20,
    "breakColor" text
);
COMMENT ON TABLE public."User_Preference" IS 'user preferences including for invites';
ALTER TABLE ONLY public."Attendee"
    ADD CONSTRAINT "Attendee_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Autopilot"
    ADD CONSTRAINT "Autopilot_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Calendar_Integration"
    ADD CONSTRAINT "Calendar_Integration_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Calendar_Push_Notification"
    ADD CONSTRAINT "Calendar_Push_Notification_calendarId_key" UNIQUE ("calendarId");
ALTER TABLE ONLY public."Calendar_Push_Notification"
    ADD CONSTRAINT "Calendar_Push_Notification_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Calendar"
    ADD CONSTRAINT "Calendar_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Category_Event"
    ADD CONSTRAINT "Category_Event_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Category"
    ADD CONSTRAINT "Category_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Chat_Meeting_Preference"
    ADD CONSTRAINT "Chat_Meeting_Preference_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Chat_Meeting_Preference"
    ADD CONSTRAINT "Chat_Meeting_Preference_userId_key" UNIQUE ("userId");

ALTER TABLE ONLY public."Conference"
    ADD CONSTRAINT "Conference_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Conference"
    ADD CONSTRAINT "Conference_requestId_key" UNIQUE ("requestId");
ALTER TABLE ONLY public."Contact_Event"
    ADD CONSTRAINT "Contact_Event_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Contact"
    ADD CONSTRAINT "Contact_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Event_Trigger"
    ADD CONSTRAINT "Event_Trigger_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Event"
    ADD CONSTRAINT "Event_pkey" PRIMARY KEY (id);

ALTER TABLE ONLY public."Invite"
    ADD CONSTRAINT "Invite_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist_Attendee"
    ADD CONSTRAINT "Meeting_Assist_Attendee_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist_Calendar"
    ADD CONSTRAINT "Meeting_Assist_Calendar_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist_Comment"
    ADD CONSTRAINT "Meeting_Assist_Comment_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist_Event"
    ADD CONSTRAINT "Meeting_Assist_Event_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist_Invite"
    ADD CONSTRAINT "Meeting_Assist_Invite_pkey" PRIMARY KEY (id);

ALTER TABLE ONLY public."Meeting_Assist_Preferred_Time_Range"
    ADD CONSTRAINT "Meeting_Assist_Preferred_Time_Ranges_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Meeting_Assist"
    ADD CONSTRAINT "Meeting_Assist_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."PreferredTimeRange"
    ADD CONSTRAINT "PreferredTimeRange_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Relationship"
    ADD CONSTRAINT "Relationship_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Reminder"
    ADD CONSTRAINT "Reminder_pkey" PRIMARY KEY (id);

ALTER TABLE ONLY public."Task"
    ADD CONSTRAINT "Task_pkey" PRIMARY KEY (id);

ALTER TABLE ONLY public."User_Preference"
    ADD CONSTRAINT "UserPreference_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."User_Contact_Info"
    ADD CONSTRAINT "User_Contact_Info_pkey" PRIMARY KEY (id);

ALTER TABLE ONLY public."User"
    ADD CONSTRAINT "User_pkey" PRIMARY KEY (id);


CREATE INDEX "Attendee_contactId_skey" ON public."Attendee" USING btree ("contactId");
CREATE INDEX "Attendee_eventId_skey" ON public."Attendee" USING btree ("eventId");
CREATE INDEX "Attendee_userId_skey" ON public."Attendee" USING btree ("userId");
CREATE INDEX "Autopilot_userId_skey" ON public."Autopilot" USING btree ("userId");
CREATE INDEX "Calendar_Integration_userId_skey" ON public."Calendar_Integration" USING btree ("userId");
CREATE INDEX "Calendar_Integration_zoomId_skey" ON public."Calendar_Integration" USING btree ("appId");
CREATE INDEX "Calendar_Push_Notification_userId_skey" ON public."Calendar_Push_Notification" USING btree ("userId");
CREATE INDEX "Calendar_userId_skey" ON public."Calendar" USING btree ("userId");
CREATE UNIQUE INDEX "Category_Event_categoryId_eventId_skey" ON public."Category_Event" USING btree ("categoryId", "eventId");
CREATE UNIQUE INDEX "Category_Event_eventId_categoryId_skey" ON public."Category_Event" USING btree ("eventId", "categoryId");
CREATE INDEX "Category_Event_userId_skey" ON public."Category_Event" USING btree ("userId");
CREATE INDEX "Category_userId_skey" ON public."Category" USING btree ("userId");

CREATE INDEX "Conference_userId_skey" ON public."Conference" USING btree ("userId");
CREATE UNIQUE INDEX "Contact_Event_contactId_eventId_skey" ON public."Contact_Event" USING btree ("contactId", "eventId");
CREATE UNIQUE INDEX "Contact_Event_eventId_contactId_skey" ON public."Contact_Event" USING btree ("eventId", "contactId");
CREATE INDEX "Contact_Event_userId_skey" ON public."Contact_Event" USING btree ("userId");
CREATE INDEX "Contact_userId_skey" ON public."Contact" USING btree ("userId");


CREATE UNIQUE INDEX "Event_Trigger_resourceId_skey" ON public."Event_Trigger" USING btree ("resourceId");
CREATE INDEX "Event_Trigger_userId_skey" ON public."Event_Trigger" USING btree ("userId");
CREATE INDEX "Event_calendarId_skey" ON public."Event" USING btree ("calendarId");
CREATE INDEX "Event_conferenceId_skey" ON public."Event" USING btree ("conferenceId");
CREATE UNIQUE INDEX "Event_eventId_calendarId_skey" ON public."Event" USING btree ("eventId", "calendarId");
CREATE INDEX "Event_userId_endDate_skey" ON public."Event" USING btree ("userId", "endDate");
CREATE INDEX "Event_userId_startDate_skey" ON public."Event" USING btree ("userId", "startDate");

CREATE INDEX "Invite_contactId_skey" ON public."Invite" USING btree ("contactId");
CREATE INDEX "Invite_userId_skey" ON public."Invite" USING btree ("userId");
CREATE INDEX "Meeting_Assist_Attendee_meetingId_skey" ON public."Meeting_Assist_Attendee" USING btree ("meetingId");
CREATE INDEX "Meeting_Assist_Comment_meetingId_skey" ON public."Meeting_Assist_Comment" USING btree ("meetingId");
CREATE INDEX "Meeting_Assist_Event_attendeeId_endDate_skey" ON public."Meeting_Assist_Event" USING btree ("attendeeId", "endDate");
CREATE INDEX "Meeting_Assist_Event_attendeeId_startDate_skey" ON public."Meeting_Assist_Event" USING btree ("attendeeId", "startDate");
CREATE INDEX "Meeting_Assist_Event_calendarId_skey" ON public."Meeting_Assist_Event" USING btree ("calendarId");
CREATE INDEX "Meeting_Assist_Invite_hostId_skey" ON public."Meeting_Assist_Invite" USING btree ("hostId");
CREATE INDEX "Meeting_Assist_Invite_meetingId_skey" ON public."Meeting_Assist_Invite" USING btree ("meetingId");

CREATE INDEX "Meeting_Assist_Preferred_TIme_Ranges_meetingId_skey" ON public."Meeting_Assist_Preferred_Time_Range" USING btree ("meetingId");
CREATE INDEX "Meeting_Assist_originalMeetingId_skey" ON public."Meeting_Assist" USING btree ("originalMeetingId");
CREATE INDEX "Meeting_Assist_userId_startDate_endDate_skey" ON public."Meeting_Assist" USING btree ("userId", "windowStartDate", "windowEndDate");
CREATE INDEX "PreferredTimeRange_eventId_skey" ON public."PreferredTimeRange" USING btree ("eventId");
CREATE INDEX "Relationship_userId_contactId_skey" ON public."Relationship" USING btree ("userId", "contactId");
CREATE INDEX "Reminder_eventId_skey" ON public."Reminder" USING btree ("eventId");
CREATE INDEX "Reminder_userId_skey" ON public."Reminder" USING btree ("userId");

CREATE UNIQUE INDEX "UserPreference_userId_skey" ON public."User_Preference" USING btree ("userId");
CREATE INDEX "User_Contact_info_userId_skey" ON public."User_Contact_Info" USING btree ("userId");
CREATE UNIQUE INDEX "emailId_inviteId_skey" ON public."Invite" USING btree ("emailId", id);

CREATE UNIQUE INDEX "phoneId_inviteId_skey" ON public."Invite" USING btree ("phoneId", id);





CREATE TRIGGER "set_public_Attendee_updatedAt" BEFORE UPDATE ON public."Attendee" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Attendee_updatedAt" ON public."Attendee" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Autopilot_updatedAt" BEFORE UPDATE ON public."Autopilot" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Autopilot_updatedAt" ON public."Autopilot" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Calendar_Integration_updatedAt" BEFORE UPDATE ON public."Calendar_Integration" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Calendar_Integration_updatedAt" ON public."Calendar_Integration" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Calendar_Push_Notification_updatedAt" BEFORE UPDATE ON public."Calendar_Push_Notification" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Calendar_Push_Notification_updatedAt" ON public."Calendar_Push_Notification" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';

CREATE TRIGGER "set_public_Calendar_updatedAt" BEFORE UPDATE ON public."Calendar" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Calendar_updatedAt" ON public."Calendar" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Category_Event_updatedAt" BEFORE UPDATE ON public."Category_Event" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Category_Event_updatedAt" ON public."Category_Event" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Category_updatedAt" BEFORE UPDATE ON public."Category" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Category_updatedAt" ON public."Category" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Chat_Meeting_Preference_updatedAt" BEFORE UPDATE ON public."Chat_Meeting_Preference" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Chat_Meeting_Preference_updatedAt" ON public."Chat_Meeting_Preference" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';



CREATE TRIGGER "set_public_Conference_updatedAt" BEFORE UPDATE ON public."Conference" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Conference_updatedAt" ON public."Conference" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Contact_Event_updatedAt" BEFORE UPDATE ON public."Contact_Event" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Contact_Event_updatedAt" ON public."Contact_Event" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Contact_updatedAt" BEFORE UPDATE ON public."Contact" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Contact_updatedAt" ON public."Contact" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';



CREATE TRIGGER "set_public_Event_Trigger_updated_at" BEFORE UPDATE ON public."Event_Trigger" FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
COMMENT ON TRIGGER "set_public_Event_Trigger_updated_at" ON public."Event_Trigger" IS 'trigger to set value of column "updated_at" to current timestamp on row update';
CREATE TRIGGER "set_public_Event_updatedAt" BEFORE UPDATE ON public."Event" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Event_updatedAt" ON public."Event" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';


CREATE TRIGGER "set_public_Invite_updatedAt" BEFORE UPDATE ON public."Invite" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Invite_updatedAt" ON public."Invite" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Meeting_Assist_Attendee_updatedAt" BEFORE UPDATE ON public."Meeting_Assist_Attendee" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_Attendee_updatedAt" ON public."Meeting_Assist_Attendee" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Meeting_Assist_Comment_updatedAt" BEFORE UPDATE ON public."Meeting_Assist_Comment" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_Comment_updatedAt" ON public."Meeting_Assist_Comment" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Meeting_Assist_Event_updatedAt" BEFORE UPDATE ON public."Meeting_Assist_Event" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_Event_updatedAt" ON public."Meeting_Assist_Event" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Meeting_Assist_Invite_updatedAt" BEFORE UPDATE ON public."Meeting_Assist_Invite" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_Invite_updatedAt" ON public."Meeting_Assist_Invite" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';

CREATE TRIGGER "set_public_Meeting_Assist_Preferred_Time_Ranges_updatedAt" BEFORE UPDATE ON public."Meeting_Assist_Preferred_Time_Range" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_Preferred_Time_Ranges_updatedAt" ON public."Meeting_Assist_Preferred_Time_Range" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Meeting_Assist_updatedAt" BEFORE UPDATE ON public."Meeting_Assist" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Meeting_Assist_updatedAt" ON public."Meeting_Assist" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_PreferredTimeRange_updatedAt" BEFORE UPDATE ON public."PreferredTimeRange" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_PreferredTimeRange_updatedAt" ON public."PreferredTimeRange" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Relationship_updatedAt" BEFORE UPDATE ON public."Relationship" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Relationship_updatedAt" ON public."Relationship" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_Reminder_updatedAt" BEFORE UPDATE ON public."Reminder" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Reminder_updatedAt" ON public."Reminder" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';

CREATE TRIGGER "set_public_Task_updatedAt" BEFORE UPDATE ON public."Task" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_Task_updatedAt" ON public."Task" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';

CREATE TRIGGER "set_public_UserPreference_updatedAt" BEFORE UPDATE ON public."User_Preference" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_UserPreference_updatedAt" ON public."User_Preference" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_User_Contact_Info_updatedAt" BEFORE UPDATE ON public."User_Contact_Info" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_User_Contact_Info_updatedAt" ON public."User_Contact_Info" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';
CREATE TRIGGER "set_public_User_updatedAt" BEFORE UPDATE ON public."User" FOR EACH ROW EXECUTE FUNCTION public."set_current_timestamp_updatedAt"();
COMMENT ON TRIGGER "set_public_User_updatedAt" ON public."User" IS 'trigger to set value of column "updatedAt" to current timestamp on row update';



ALTER TABLE ONLY public."Attendee"
    ADD CONSTRAINT "Attendee_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES public."Event"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Attendee"
    ADD CONSTRAINT "Attendee_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Autopilot"
    ADD CONSTRAINT "Autopilot_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Calendar_Integration"
    ADD CONSTRAINT "Calendar_Integration_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Calendar_Push_Notification"
    ADD CONSTRAINT "Calendar_Push_Notification_calendarId_fkey" FOREIGN KEY ("calendarId") REFERENCES public."Calendar"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Calendar_Push_Notification"
    ADD CONSTRAINT "Calendar_Push_Notification_calendarIntegrationId_fkey" FOREIGN KEY ("calendarIntegrationId") REFERENCES public."Calendar_Integration"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Calendar_Push_Notification"
    ADD CONSTRAINT "Calendar_Push_Notification_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


ALTER TABLE ONLY public."Calendar"
    ADD CONSTRAINT "Calendar_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Category_Event"
    ADD CONSTRAINT "Category_Event_categoryId_fkey" FOREIGN KEY ("categoryId") REFERENCES public."Category"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Category_Event"
    ADD CONSTRAINT "Category_Event_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES public."Event"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Category_Event"
    ADD CONSTRAINT "Category_Event_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Category"
    ADD CONSTRAINT "Category_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Chat_Meeting_Preference"
    ADD CONSTRAINT "Chat_Meeting_Preference_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public."Conference"
    ADD CONSTRAINT "Conference_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Contact_Event"
    ADD CONSTRAINT "Contact_Event_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES public."Contact"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Contact_Event"
    ADD CONSTRAINT "Contact_Event_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES public."Event"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Contact_Event"
    ADD CONSTRAINT "Contact_Event_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Contact"
    ADD CONSTRAINT "Contact_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;




ALTER TABLE ONLY public."Event_Trigger"
    ADD CONSTRAINT "Event_Trigger_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Event"
    ADD CONSTRAINT "Event_calendarId_fkey" FOREIGN KEY ("calendarId") REFERENCES public."Calendar"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Event"
    ADD CONSTRAINT "Event_conferenceId_fkey" FOREIGN KEY ("conferenceId") REFERENCES public."Conference"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Event"
    ADD CONSTRAINT "Event_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY public."Invite"
    ADD CONSTRAINT "Invite_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES public."Contact"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Invite"
    ADD CONSTRAINT "Invite_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Attendee"
    ADD CONSTRAINT "Meeting_Assist_Attendee_meetingId_fkey" FOREIGN KEY ("meetingId") REFERENCES public."Meeting_Assist"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Calendar"
    ADD CONSTRAINT "Meeting_Assist_Calendar_attendeeId_fkey" FOREIGN KEY ("attendeeId") REFERENCES public."Meeting_Assist_Attendee"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Comment"
    ADD CONSTRAINT "Meeting_Assist_Comment_meetingId_fkey" FOREIGN KEY ("meetingId") REFERENCES public."Meeting_Assist"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Comment"
    ADD CONSTRAINT "Meeting_Assist_Comment_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Event"
    ADD CONSTRAINT "Meeting_Assist_Event_attendeeId_fkey" FOREIGN KEY ("attendeeId") REFERENCES public."Meeting_Assist_Attendee"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Invite"
    ADD CONSTRAINT "Meeting_Assist_Invite_meetingId_fkey" FOREIGN KEY ("meetingId") REFERENCES public."Meeting_Assist"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist_Preferred_Time_Range"
    ADD CONSTRAINT "Meeting_Assist_Preferred_Time_Range_attendeeId_fkey" FOREIGN KEY ("attendeeId") REFERENCES public."Meeting_Assist_Attendee"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Meeting_Assist"
    ADD CONSTRAINT "Meeting_Assist_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."PreferredTimeRange"
    ADD CONSTRAINT "PreferredTimeRange_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES public."Event"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Relationship"
    ADD CONSTRAINT "Relationship_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES public."Contact"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Reminder"
    ADD CONSTRAINT "Reminder_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES public."Event"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Reminder"
    ADD CONSTRAINT "Reminder_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Task"
    ADD CONSTRAINT "Task_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public."User_Contact_Info"
    ADD CONSTRAINT "User_Contact_Info_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public."User_Preference"
    ADD CONSTRAINT "User_Preference_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;

[end of deployment/aws/db_init_scripts/atomic-schema-up.sql]

[start of deployment/aws/db_init_scripts/optaplanner-create-schema.sql]
CREATE TABLE admin_user (
  id INT,
  username VARCHAR(255),
  password VARCHAR(255),
  role VARCHAR(255)
);

INSERT INTO admin_user (id, username, password, role) VALUES (1, 'admin', 'password', 'admin');

create table event_optaplanner (id varchar(255) not null, hostId uuid, userId uuid, primary key (id));
create table event_part_optaplanner (id int8 not null, dailyTaskList boolean not null, endDate varchar(255), eventId varchar(255), forEventId varchar(255), gap boolean not null, groupId varchar(255), hardDeadline varchar(255), hostId uuid, isExternalMeeting boolean not null, isExternalMeetingModifiable boolean not null, isMeeting boolean not null, isMeetingModifiable boolean not null, isPostEvent boolean not null, isPreEvent boolean not null, lastPart int4 not null, meetingId varchar(255), meetingLastPart int4 not null, meetingPart int4 not null, modifiable boolean not null, negativeImpactDayOfWeek int4, negativeImpactScore int4 not null, negativeImpactTime time, part int4 not null, positiveImpactDayOfWeek int4, positiveImpactScore int4 not null, positiveImpactTime time, preferredDayOfWeek int4, preferredEndTimeRange time, preferredStartTimeRange time, preferredTime time, priority int4 not null, softDeadline varchar(255), startDate varchar(255), taskId varchar(255), totalWorkingHours int4 not null, userId uuid, weeklyTaskList boolean not null, timeslot_id int8, primary key (id));
create table preferredTimeRange_optaplanner (id int8 not null, dayOfWeek int4, endTime time, eventId varchar(255), hostId uuid, startTime time, userId uuid, primary key (id));
create table timeslot_optaplanner (id int8 not null, dayOfWeek int4, endTime time, hostId uuid, monthDay varchar(255), startTime time, primary key (id));
create table user_optaplanner (id uuid not null, backToBackMeetings boolean not null, hostId uuid, maxNumberOfMeetings int4 not null, maxWorkLoadPercent int4 not null, minNumberOfBreaks int4 not null, primary key (id));
create table workTime_optaplanner (id int8 not null, dayOfWeek int4, endTime time, hostId uuid, startTime time, userId uuid, primary key (id));
create index sk_userId_event_optaplanner on event_optaplanner (userId);
create index sk_hostId_event_optaplanner on event_optaplanner (hostId);
create index sk_userId_eventPart_optaplanner on event_part_optaplanner (userId);
create index sk_groupId_eventPart_optaplanner on event_part_optaplanner (groupId);
create index sk_eventId_eventPart_optaplanner on event_part_optaplanner (eventId);
create index sk_hostId_eventPart_optaplanner on event_part_optaplanner (hostId);
create index sk_eventId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (eventId);
create index sk_userId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (userId);
create index sk_hostId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (hostId);
create index sk_timeslot_hostId_optaplanner on timeslot_optaplanner (hostId);
create index sk_hostId_user_optaplanner on user_optaplanner (hostId);
create index sk_userId_workTime_optaplanner on workTime_optaplanner (userId);
create index sk_hostId_workTime_optaplanner on workTime_optaplanner (hostId);
create sequence hibernate_sequence start 1 increment 1;
alter table if exists event_part_optaplanner add constraint FKi0pl5rc8eang05vdsc1274cmb foreign key (eventId) references event_optaplanner;
alter table if exists event_part_optaplanner add constraint FKrc6mx3f0p8evu5cpryix0pswu foreign key (timeslot_id) references timeslot_optaplanner;
alter table if exists event_part_optaplanner add constraint FK1a8wkuvkkrju0bfxo8se32eo3 foreign key (userId) references user_optaplanner;
alter table if exists preferredTimeRange_optaplanner add constraint FKdd37a30iji98r7fy0rur1v6d1 foreign key (eventId) references event_optaplanner;

[end of deployment/aws/db_init_scripts/optaplanner-create-schema.sql]
