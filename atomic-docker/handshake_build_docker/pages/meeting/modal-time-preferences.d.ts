import type { NextPage } from 'next';
import "react-datepicker/dist/react-datepicker.css";
import { CustomAvailableTimeType, MeetingAssistType, UserPreferenceType } from "@lib/types";
type Props = {
    minDate: Date;
    maxDate: Date;
    slotDuration: number;
    hostPreferences: UserPreferenceType;
    meetingAssist: MeetingAssistType;
    onSubmit: (availableTime: CustomAvailableTimeType) => void;
    onCancel: () => void;
};
declare const ModalTimePreferences: NextPage<Props>;
export default ModalTimePreferences;
