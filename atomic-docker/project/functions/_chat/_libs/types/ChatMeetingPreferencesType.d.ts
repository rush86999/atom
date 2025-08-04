import { AppType } from './ConferenceType';
import { SendUpdatesType, TransparencyType, VisibilityType } from './EventType';
export type BufferTimeNumberType = {
    beforeEvent: number;
    afterEvent: number;
};
export type ChatMeetingPreferencesType = {
    anyoneCanAddSelf: boolean;
    bufferTime?: BufferTimeNumberType;
    conferenceApp?: AppType;
    createdDate: string;
    duration: number;
    enableConference: boolean;
    guestsCanInviteOthers: boolean;
    guestsCanSeeOtherGuests: boolean;
    id: string;
    name?: string;
    primaryEmail?: string;
    reminders?: number[];
    sendUpdates?: SendUpdatesType;
    timezone?: string;
    transparency: TransparencyType;
    updatedAt: string;
    useDefaultAlarms: boolean;
    userId: string;
    visibility: VisibilityType;
};
