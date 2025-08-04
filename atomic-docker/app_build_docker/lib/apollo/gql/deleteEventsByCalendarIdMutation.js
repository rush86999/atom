"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteEventsByCalendarId($calendarId: String!) {
    delete_Event(where: { calendarId: { _eq: $calendarId } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkTXV0YXRpb24uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVFdmVudHNCeUNhbGVuZGFySWRNdXRhdGlvbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7O0NBTWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gRGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkKCRjYWxlbmRhcklkOiBTdHJpbmchKSB7XG4gICAgZGVsZXRlX0V2ZW50KHdoZXJlOiB7IGNhbGVuZGFySWQ6IHsgX2VxOiAkY2FsZW5kYXJJZCB9IH0pIHtcbiAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICB9XG4gIH1cbmA7XG4iXX0=