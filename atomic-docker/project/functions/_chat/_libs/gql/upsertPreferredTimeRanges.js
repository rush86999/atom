export default `
    mutation UpsertPreferredTimeRanges($preferredTimeRanges: [PreferredTimeRange_insert_input!]!) {
        insert_PreferredTimeRange(objects: $preferredTimeRanges, on_conflict: {constraint: PreferredTimeRange_pkey, update_columns: [
        dayOfWeek,
        endTime,
        startTime,
    ]}) {
      affected_rows
      returning {
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
  }
  `;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7R0FvQlosQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbiAgICBtdXRhdGlvbiBVcHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzKCRwcmVmZXJyZWRUaW1lUmFuZ2VzOiBbUHJlZmVycmVkVGltZVJhbmdlX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICBpbnNlcnRfUHJlZmVycmVkVGltZVJhbmdlKG9iamVjdHM6ICRwcmVmZXJyZWRUaW1lUmFuZ2VzLCBvbl9jb25mbGljdDoge2NvbnN0cmFpbnQ6IFByZWZlcnJlZFRpbWVSYW5nZV9wa2V5LCB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICBkYXlPZldlZWssXG4gICAgICAgIGVuZFRpbWUsXG4gICAgICAgIHN0YXJ0VGltZSxcbiAgICBdfSkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgIGVuZFRpbWVcbiAgICAgICAgZXZlbnRJZFxuICAgICAgICBpZFxuICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuICBgO1xuIl19