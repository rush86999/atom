"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.currentTimezoneObject = exports.formattedTimezones = exports.meetingRequestUrl = void 0;
const timezones_json_1 = __importDefault(require("@lib/GPT/MeetingRequest/timezones.json"));
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
exports.meetingRequestUrl = 'https://sqbxvm6nt4.execute-api.us-east-1.amazonaws.com/prod/meeting-request-auth';
exports.formattedTimezones = timezones_json_1.default?.map((t) => ({
    value: t?.utc?.[0],
    label: t?.value,
    key: `${t?.utc?.[0]}-${(0, uuid_1.v4)()}`,
}));
console.log(exports.formattedTimezones, ' formattedTimezones');
const currentTimezone = timezones_json_1.default?.find((t) => t?.utc?.find((m) => m === date_utils_1.dayjs.tz.guess()));
exports.currentTimezoneObject = {
    label: currentTimezone?.text || date_utils_1.dayjs.tz.guess(),
    value: currentTimezone?.utc?.[0] || date_utils_1.dayjs.tz.guess(),
    key: `${currentTimezone?.utc?.[0] || date_utils_1.dayjs.tz.guess()}-${(0, uuid_1.v4)()}`,
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29uc3RhbnRzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiY29uc3RhbnRzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUNBLDRGQUErRDtBQUMvRCwrQkFBa0M7QUFDbEMsZ0RBQXdDO0FBRTNCLFFBQUEsaUJBQWlCLEdBQzVCLGtGQUFrRixDQUFDO0FBRXhFLFFBQUEsa0JBQWtCLEdBQXlCLHdCQUFTLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQzdFLEtBQUssRUFBRSxDQUFDLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQyxDQUFDO0lBQ2xCLEtBQUssRUFBRSxDQUFDLEVBQUUsS0FBSztJQUNmLEdBQUcsRUFBRSxHQUFHLENBQUMsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUMsSUFBSSxJQUFBLFNBQUksR0FBRSxFQUFFO0NBQ2hDLENBQUMsQ0FBQyxDQUFDO0FBRUosT0FBTyxDQUFDLEdBQUcsQ0FBQywwQkFBa0IsRUFBRSxxQkFBcUIsQ0FBQyxDQUFDO0FBRXZELE1BQU0sZUFBZSxHQUFHLHdCQUFTLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FDNUMsQ0FBQyxFQUFFLEdBQUcsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxrQkFBSyxDQUFDLEVBQUUsQ0FBQyxLQUFLLEVBQUUsQ0FBQyxDQUM1QyxDQUFDO0FBRVcsUUFBQSxxQkFBcUIsR0FBdUI7SUFDdkQsS0FBSyxFQUFFLGVBQWUsRUFBRSxJQUFJLElBQUksa0JBQUssQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFO0lBQ2hELEtBQUssRUFBRSxlQUFlLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQyxDQUFDLElBQUksa0JBQUssQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFO0lBQ3BELEdBQUcsRUFBRSxHQUFHLGVBQWUsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUMsSUFBSSxrQkFBSyxDQUFDLEVBQUUsQ0FBQyxLQUFLLEVBQUUsSUFBSSxJQUFBLFNBQUksR0FBRSxFQUFFO0NBQ2xFLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBUaW1lem9uZU9iamVjdFR5cGUgfSBmcm9tICdAbGliL0dQVC9NZWV0aW5nUmVxdWVzdC90eXBlcyc7XG5pbXBvcnQgdGltZXpvbmVzIGZyb20gJ0BsaWIvR1BUL01lZXRpbmdSZXF1ZXN0L3RpbWV6b25lcy5qc29uJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcblxuZXhwb3J0IGNvbnN0IG1lZXRpbmdSZXF1ZXN0VXJsID1cbiAgJ2h0dHBzOi8vc3FieHZtNm50NC5leGVjdXRlLWFwaS51cy1lYXN0LTEuYW1hem9uYXdzLmNvbS9wcm9kL21lZXRpbmctcmVxdWVzdC1hdXRoJztcblxuZXhwb3J0IGNvbnN0IGZvcm1hdHRlZFRpbWV6b25lczogVGltZXpvbmVPYmplY3RUeXBlW10gPSB0aW1lem9uZXM/Lm1hcCgodCkgPT4gKHtcbiAgdmFsdWU6IHQ/LnV0Yz8uWzBdLFxuICBsYWJlbDogdD8udmFsdWUsXG4gIGtleTogYCR7dD8udXRjPy5bMF19LSR7dXVpZCgpfWAsXG59KSk7XG5cbmNvbnNvbGUubG9nKGZvcm1hdHRlZFRpbWV6b25lcywgJyBmb3JtYXR0ZWRUaW1lem9uZXMnKTtcblxuY29uc3QgY3VycmVudFRpbWV6b25lID0gdGltZXpvbmVzPy5maW5kKCh0KSA9PlxuICB0Py51dGM/LmZpbmQoKG0pID0+IG0gPT09IGRheWpzLnR6Lmd1ZXNzKCkpXG4pO1xuXG5leHBvcnQgY29uc3QgY3VycmVudFRpbWV6b25lT2JqZWN0OiBUaW1lem9uZU9iamVjdFR5cGUgPSB7XG4gIGxhYmVsOiBjdXJyZW50VGltZXpvbmU/LnRleHQgfHwgZGF5anMudHouZ3Vlc3MoKSxcbiAgdmFsdWU6IGN1cnJlbnRUaW1lem9uZT8udXRjPy5bMF0gfHwgZGF5anMudHouZ3Vlc3MoKSxcbiAga2V5OiBgJHtjdXJyZW50VGltZXpvbmU/LnV0Yz8uWzBdIHx8IGRheWpzLnR6Lmd1ZXNzKCl9LSR7dXVpZCgpfWAsXG59O1xuIl19