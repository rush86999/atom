"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListPreferredTimeRangesGivenEventId($eventId: String!) {
    PreferredTimeRange(where: { eventId: { _eq: $eventId } }) {
      createdDate
      dayOfWeek
      endTime
      eventId
      id
      startTime
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0UHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7OztDQWFqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IExpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKCRldmVudElkOiBTdHJpbmchKSB7XG4gICAgUHJlZmVycmVkVGltZVJhbmdlKHdoZXJlOiB7IGV2ZW50SWQ6IHsgX2VxOiAkZXZlbnRJZCB9IH0pIHtcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkYXlPZldlZWtcbiAgICAgIGVuZFRpbWVcbiAgICAgIGV2ZW50SWRcbiAgICAgIGlkXG4gICAgICBzdGFydFRpbWVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19