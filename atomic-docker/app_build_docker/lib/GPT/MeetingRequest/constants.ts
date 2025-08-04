import { TimezoneObjectType } from '@lib/GPT/MeetingRequest/types';
import timezones from '@lib/GPT/MeetingRequest/timezones.json';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@lib/date-utils';

export const meetingRequestUrl =
  'https://sqbxvm6nt4.execute-api.us-east-1.amazonaws.com/prod/meeting-request-auth';

export const formattedTimezones: TimezoneObjectType[] = timezones?.map((t) => ({
  value: t?.utc?.[0],
  label: t?.value,
  key: `${t?.utc?.[0]}-${uuid()}`,
}));

console.log(formattedTimezones, ' formattedTimezones');

const currentTimezone = timezones?.find((t) =>
  t?.utc?.find((m) => m === dayjs.tz.guess())
);

export const currentTimezoneObject: TimezoneObjectType = {
  label: currentTimezone?.text || dayjs.tz.guess(),
  value: currentTimezone?.utc?.[0] || dayjs.tz.guess(),
  key: `${currentTimezone?.utc?.[0] || dayjs.tz.guess()}-${uuid()}`,
};
