"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteConferencesWithIds = void 0;
const deleteConferencesByIds_1 = __importDefault(require("@lib/apollo/gql/deleteConferencesByIds"));
const deleteConferencesWithIds = async (client, ids) => {
    try {
        const res = await client.mutate({
            mutation: deleteConferencesByIds_1.default,
            variables: {
                ids,
            },
        });
        console.log(res?.data?.delete_Conference?.affected_rows, 'successfully removed conferences for event');
    }
    catch (e) {
        console.log(e, ' unable to remove attendees for event');
    }
};
exports.deleteConferencesWithIds = deleteConferencesWithIds;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ29uZmVyZW5jZUhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkNvbmZlcmVuY2VIZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQ0Esb0dBQTRFO0FBRXJFLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxFQUMzQyxNQUEyQyxFQUMzQyxHQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sR0FBRyxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FFNUI7WUFDRCxRQUFRLEVBQUUsZ0NBQXNCO1lBQ2hDLFNBQVMsRUFBRTtnQkFDVCxHQUFHO2FBQ0o7U0FDRixDQUFDLENBQUM7UUFFSCxPQUFPLENBQUMsR0FBRyxDQUNULEdBQUcsRUFBRSxJQUFJLEVBQUUsaUJBQWlCLEVBQUUsYUFBYSxFQUMzQyw0Q0FBNEMsQ0FDN0MsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsdUNBQXVDLENBQUMsQ0FBQztJQUMxRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBckJXLFFBQUEsd0JBQXdCLDRCQXFCbkMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBkZWxldGVDb25mZXJlbmNlc0J5SWRzIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9kZWxldGVDb25mZXJlbmNlc0J5SWRzJztcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUNvbmZlcmVuY2VzV2l0aElkcyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaWRzOiBzdHJpbmdbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBkZWxldGVfQ29uZmVyZW5jZTogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlQ29uZmVyZW5jZXNCeUlkcyxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZHMsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/LmRlbGV0ZV9Db25mZXJlbmNlPy5hZmZlY3RlZF9yb3dzLFxuICAgICAgJ3N1Y2Nlc3NmdWxseSByZW1vdmVkIGNvbmZlcmVuY2VzIGZvciBldmVudCdcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcmVtb3ZlIGF0dGVuZGVlcyBmb3IgZXZlbnQnKTtcbiAgfVxufTtcbiJdfQ==