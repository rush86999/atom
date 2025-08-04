"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.nanoid = void 0;
exports.cn = cn;
exports.fetcher = fetcher;
exports.formatDate = formatDate;
const clsx_1 = require("clsx");
const nanoid_1 = require("nanoid");
const tailwind_merge_1 = require("tailwind-merge");
function cn(...inputs) {
    return (0, tailwind_merge_1.twMerge)((0, clsx_1.clsx)(inputs));
}
exports.nanoid = (0, nanoid_1.customAlphabet)('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', 7); // 7-character random string
async function fetcher(input, init) {
    const res = await fetch(input, init);
    if (!res.ok) {
        const json = await res.json();
        if (json.error) {
            const error = new Error(json.error);
            error.status = res.status;
            throw error;
        }
        else {
            throw new Error('An unexpected error occurred');
        }
    }
    return res.json();
}
function formatDate(input) {
    const date = new Date(input);
    return date.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
    });
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXRpbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1dGlscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFJQSxnQkFFQztBQU9ELDBCQW9CQztBQUVELGdDQU9DO0FBMUNELCtCQUE2QztBQUM3QyxtQ0FBd0M7QUFDeEMsbURBQXlDO0FBRXpDLFNBQWdCLEVBQUUsQ0FBQyxHQUFHLE1BQW9CO0lBQ3hDLE9BQU8sSUFBQSx3QkFBTyxFQUFDLElBQUEsV0FBSSxFQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUM7QUFDL0IsQ0FBQztBQUVZLFFBQUEsTUFBTSxHQUFHLElBQUEsdUJBQWMsRUFDbEMsZ0VBQWdFLEVBQ2hFLENBQUMsQ0FDRixDQUFDLENBQUMsNEJBQTRCO0FBRXhCLEtBQUssVUFBVSxPQUFPLENBQzNCLEtBQWtCLEVBQ2xCLElBQWtCO0lBRWxCLE1BQU0sR0FBRyxHQUFHLE1BQU0sS0FBSyxDQUFDLEtBQUssRUFBRSxJQUFJLENBQUMsQ0FBQztJQUVyQyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsRUFBRSxDQUFDO1FBQ1osTUFBTSxJQUFJLEdBQUcsTUFBTSxHQUFHLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDOUIsSUFBSSxJQUFJLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDZixNQUFNLEtBQUssR0FBRyxJQUFJLEtBQUssQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUVqQyxDQUFDO1lBQ0YsS0FBSyxDQUFDLE1BQU0sR0FBRyxHQUFHLENBQUMsTUFBTSxDQUFDO1lBQzFCLE1BQU0sS0FBSyxDQUFDO1FBQ2QsQ0FBQzthQUFNLENBQUM7WUFDTixNQUFNLElBQUksS0FBSyxDQUFDLDhCQUE4QixDQUFDLENBQUM7UUFDbEQsQ0FBQztJQUNILENBQUM7SUFFRCxPQUFPLEdBQUcsQ0FBQyxJQUFJLEVBQUUsQ0FBQztBQUNwQixDQUFDO0FBRUQsU0FBZ0IsVUFBVSxDQUFDLEtBQTZCO0lBQ3RELE1BQU0sSUFBSSxHQUFHLElBQUksSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQzdCLE9BQU8sSUFBSSxDQUFDLGtCQUFrQixDQUFDLE9BQU8sRUFBRTtRQUN0QyxLQUFLLEVBQUUsTUFBTTtRQUNiLEdBQUcsRUFBRSxTQUFTO1FBQ2QsSUFBSSxFQUFFLFNBQVM7S0FDaEIsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGNsc3gsIHR5cGUgQ2xhc3NWYWx1ZSB9IGZyb20gJ2Nsc3gnO1xuaW1wb3J0IHsgY3VzdG9tQWxwaGFiZXQgfSBmcm9tICduYW5vaWQnO1xuaW1wb3J0IHsgdHdNZXJnZSB9IGZyb20gJ3RhaWx3aW5kLW1lcmdlJztcblxuZXhwb3J0IGZ1bmN0aW9uIGNuKC4uLmlucHV0czogQ2xhc3NWYWx1ZVtdKSB7XG4gIHJldHVybiB0d01lcmdlKGNsc3goaW5wdXRzKSk7XG59XG5cbmV4cG9ydCBjb25zdCBuYW5vaWQgPSBjdXN0b21BbHBoYWJldChcbiAgJzAxMjM0NTY3ODlBQkNERUZHSElKS0xNTk9QUVJTVFVWV1hZWmFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6JyxcbiAgN1xuKTsgLy8gNy1jaGFyYWN0ZXIgcmFuZG9tIHN0cmluZ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZmV0Y2hlcjxKU09OID0gYW55PihcbiAgaW5wdXQ6IFJlcXVlc3RJbmZvLFxuICBpbml0PzogUmVxdWVzdEluaXRcbik6IFByb21pc2U8SlNPTj4ge1xuICBjb25zdCByZXMgPSBhd2FpdCBmZXRjaChpbnB1dCwgaW5pdCk7XG5cbiAgaWYgKCFyZXMub2spIHtcbiAgICBjb25zdCBqc29uID0gYXdhaXQgcmVzLmpzb24oKTtcbiAgICBpZiAoanNvbi5lcnJvcikge1xuICAgICAgY29uc3QgZXJyb3IgPSBuZXcgRXJyb3IoanNvbi5lcnJvcikgYXMgRXJyb3IgJiB7XG4gICAgICAgIHN0YXR1czogbnVtYmVyO1xuICAgICAgfTtcbiAgICAgIGVycm9yLnN0YXR1cyA9IHJlcy5zdGF0dXM7XG4gICAgICB0aHJvdyBlcnJvcjtcbiAgICB9IGVsc2Uge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkJyk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHJlcy5qc29uKCk7XG59XG5cbmV4cG9ydCBmdW5jdGlvbiBmb3JtYXREYXRlKGlucHV0OiBzdHJpbmcgfCBudW1iZXIgfCBEYXRlKTogc3RyaW5nIHtcbiAgY29uc3QgZGF0ZSA9IG5ldyBEYXRlKGlucHV0KTtcbiAgcmV0dXJuIGRhdGUudG9Mb2NhbGVEYXRlU3RyaW5nKCdlbi1VUycsIHtcbiAgICBtb250aDogJ2xvbmcnLFxuICAgIGRheTogJ251bWVyaWMnLFxuICAgIHllYXI6ICdudW1lcmljJyxcbiAgfSk7XG59XG4iXX0=