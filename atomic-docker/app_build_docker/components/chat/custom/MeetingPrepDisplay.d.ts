import React from 'react';
import { AggregatedPrepResults } from '@lib/dataTypes/Messaging/MessagingTypes';
interface MeetingPrepDisplayProps {
    briefing: AggregatedPrepResults;
}
declare const MeetingPrepDisplay: React.FC<MeetingPrepDisplayProps>;
export default MeetingPrepDisplay;
