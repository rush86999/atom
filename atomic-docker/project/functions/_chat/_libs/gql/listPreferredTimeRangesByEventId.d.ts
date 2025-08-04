declare const _default: "\n    query ListPreferredTimeRangesGivenEventId($eventId: String!) {\n        PreferredTimeRange(where: {eventId: {_eq: $eventId}}) {\n            createdDate\n            dayOfWeek\n            endTime\n            eventId\n            id\n            startTime\n            updatedAt\n            userId\n        }\n    }\n";
export default _default;
