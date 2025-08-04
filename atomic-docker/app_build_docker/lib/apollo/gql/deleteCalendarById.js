"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteCalendarById($id: String!) {
    deleteCalendarById(input: { id: $id }) {
      # Renamed and using input object
      calendar {
        # Standard PostGraphile payload often returns the deleted object or its ID
        id # Commonly, only the ID of the deleted object is returned
        # title # Other fields might be available if the PG function returns the full record
      }
      # clientMutationId # Optional, for Relay compatibility
      # deletedCalendarId # Alternative way PostGraphile might return the ID
    }
  }
`;
// Note: The exact return fields (e.g., 'calendar { id }' vs 'deletedCalendarId')
// depend on PostGraphile's default CRUD mutations or how a custom delete function is defined.
// Returning just the ID is common. The original query returned many fields, which is less typical for PostGraphile deletes.
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ2FsZW5kYXJCeUlkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGVsZXRlQ2FsZW5kYXJCeUlkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7O0NBYWpCLENBQUM7QUFDRixpRkFBaUY7QUFDakYsOEZBQThGO0FBQzlGLDRIQUE0SCIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVDYWxlbmRhckJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gICAgZGVsZXRlQ2FsZW5kYXJCeUlkKGlucHV0OiB7IGlkOiAkaWQgfSkge1xuICAgICAgIyBSZW5hbWVkIGFuZCB1c2luZyBpbnB1dCBvYmplY3RcbiAgICAgIGNhbGVuZGFyIHtcbiAgICAgICAgIyBTdGFuZGFyZCBQb3N0R3JhcGhpbGUgcGF5bG9hZCBvZnRlbiByZXR1cm5zIHRoZSBkZWxldGVkIG9iamVjdCBvciBpdHMgSURcbiAgICAgICAgaWQgIyBDb21tb25seSwgb25seSB0aGUgSUQgb2YgdGhlIGRlbGV0ZWQgb2JqZWN0IGlzIHJldHVybmVkXG4gICAgICAgICMgdGl0bGUgIyBPdGhlciBmaWVsZHMgbWlnaHQgYmUgYXZhaWxhYmxlIGlmIHRoZSBQRyBmdW5jdGlvbiByZXR1cm5zIHRoZSBmdWxsIHJlY29yZFxuICAgICAgfVxuICAgICAgIyBjbGllbnRNdXRhdGlvbklkICMgT3B0aW9uYWwsIGZvciBSZWxheSBjb21wYXRpYmlsaXR5XG4gICAgICAjIGRlbGV0ZWRDYWxlbmRhcklkICMgQWx0ZXJuYXRpdmUgd2F5IFBvc3RHcmFwaGlsZSBtaWdodCByZXR1cm4gdGhlIElEXG4gICAgfVxuICB9XG5gO1xuLy8gTm90ZTogVGhlIGV4YWN0IHJldHVybiBmaWVsZHMgKGUuZy4sICdjYWxlbmRhciB7IGlkIH0nIHZzICdkZWxldGVkQ2FsZW5kYXJJZCcpXG4vLyBkZXBlbmQgb24gUG9zdEdyYXBoaWxlJ3MgZGVmYXVsdCBDUlVEIG11dGF0aW9ucyBvciBob3cgYSBjdXN0b20gZGVsZXRlIGZ1bmN0aW9uIGlzIGRlZmluZWQuXG4vLyBSZXR1cm5pbmcganVzdCB0aGUgSUQgaXMgY29tbW9uLiBUaGUgb3JpZ2luYWwgcXVlcnkgcmV0dXJuZWQgbWFueSBmaWVsZHMsIHdoaWNoIGlzIGxlc3MgdHlwaWNhbCBmb3IgUG9zdEdyYXBoaWxlIGRlbGV0ZXMuXG4iXX0=