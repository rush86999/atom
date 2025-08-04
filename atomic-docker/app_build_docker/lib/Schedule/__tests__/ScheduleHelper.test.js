"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const ScheduleHelper_1 = require("../ScheduleHelper");
const apiBackendHelper = __importStar(require("@lib/api-backend-helper"));
const client_1 = require("@apollo/client");
// Mock the api-backend-helper module
jest.mock('@lib/api-backend-helper', () => ({
    scheduleMeeting: jest.fn(),
}));
describe('ScheduleHelper', () => {
    describe('requestScheduleMeeting', () => {
        let mockClient; // eslint-disable-line @typescript-eslint/no-explicit-any
        beforeEach(() => {
            jest.clearAllMocks();
            mockClient = new client_1.ApolloClient({ cache: new client_1.InMemoryCache() }); // Mock ApolloClient
        });
        it('should call callScheduleMeetingApi with the correct payload', async () => {
            const mockUserId = 'user-123';
            const mockParticipantNames = ['Alice', 'Bob'];
            const mockDurationMinutes = 60;
            const mockPreferredDate = '2024-08-15';
            const mockPreferredStartTimeFrom = '10:00:00';
            const mockPreferredStartTimeTo = '11:00:00';
            const expectedPayload = {
                participantNames: mockParticipantNames,
                durationMinutes: mockDurationMinutes,
                preferredDate: mockPreferredDate,
                preferredStartTimeFrom: mockPreferredStartTimeFrom,
                preferredStartTimeTo: mockPreferredStartTimeTo,
            };
            apiBackendHelper.scheduleMeeting.mockResolvedValueOnce({
                success: true,
            });
            await (0, ScheduleHelper_1.requestScheduleMeeting)(mockClient, mockUserId, mockParticipantNames, mockDurationMinutes, mockPreferredDate, mockPreferredStartTimeFrom, mockPreferredStartTimeTo);
            expect(apiBackendHelper.scheduleMeeting).toHaveBeenCalledTimes(1);
            expect(apiBackendHelper.scheduleMeeting).toHaveBeenCalledWith(expectedPayload);
        });
        it('should return the response from callScheduleMeetingApi on success', async () => {
            const mockResponse = { meetingId: 'meeting-456', status: 'PENDING' };
            apiBackendHelper.scheduleMeeting.mockResolvedValueOnce(mockResponse);
            const result = await (0, ScheduleHelper_1.requestScheduleMeeting)(mockClient, 'user-123', ['Alice'], 30, '2024-08-16', '14:00:00', '15:00:00');
            expect(result).toEqual(mockResponse);
        });
        it('should throw an error if callScheduleMeetingApi throws an error', async () => {
            const mockError = new Error('API Failure');
            apiBackendHelper.scheduleMeeting.mockRejectedValueOnce(mockError);
            await expect((0, ScheduleHelper_1.requestScheduleMeeting)(mockClient, 'user-123', ['Bob'], 45, '2024-08-17', '09:00:00', '10:00:00')).rejects.toThrow('API Failure');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU2NoZWR1bGVIZWxwZXIudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlNjaGVkdWxlSGVscGVyLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUFBQSxzREFBMkQ7QUFDM0QsMEVBQTREO0FBQzVELDJDQUE2RDtBQUU3RCxxQ0FBcUM7QUFDckMsSUFBSSxDQUFDLElBQUksQ0FBQyx5QkFBeUIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQzFDLGVBQWUsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0NBQzNCLENBQUMsQ0FBQyxDQUFDO0FBRUosUUFBUSxDQUFDLGdCQUFnQixFQUFFLEdBQUcsRUFBRTtJQUM5QixRQUFRLENBQUMsd0JBQXdCLEVBQUUsR0FBRyxFQUFFO1FBQ3RDLElBQUksVUFBNkIsQ0FBQyxDQUFDLHlEQUF5RDtRQUU1RixVQUFVLENBQUMsR0FBRyxFQUFFO1lBQ2QsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO1lBQ3JCLFVBQVUsR0FBRyxJQUFJLHFCQUFZLENBQUMsRUFBRSxLQUFLLEVBQUUsSUFBSSxzQkFBYSxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsb0JBQW9CO1FBQ3JGLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLDZEQUE2RCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzNFLE1BQU0sVUFBVSxHQUFHLFVBQVUsQ0FBQztZQUM5QixNQUFNLG9CQUFvQixHQUFHLENBQUMsT0FBTyxFQUFFLEtBQUssQ0FBQyxDQUFDO1lBQzlDLE1BQU0sbUJBQW1CLEdBQUcsRUFBRSxDQUFDO1lBQy9CLE1BQU0saUJBQWlCLEdBQUcsWUFBWSxDQUFDO1lBQ3ZDLE1BQU0sMEJBQTBCLEdBQUcsVUFBVSxDQUFDO1lBQzlDLE1BQU0sd0JBQXdCLEdBQUcsVUFBVSxDQUFDO1lBQzVDLE1BQU0sZUFBZSxHQUFHO2dCQUN0QixnQkFBZ0IsRUFBRSxvQkFBb0I7Z0JBQ3RDLGVBQWUsRUFBRSxtQkFBbUI7Z0JBQ3BDLGFBQWEsRUFBRSxpQkFBaUI7Z0JBQ2hDLHNCQUFzQixFQUFFLDBCQUEwQjtnQkFDbEQsb0JBQW9CLEVBQUUsd0JBQXdCO2FBQy9DLENBQUM7WUFFRCxnQkFBZ0IsQ0FBQyxlQUE2QixDQUFDLHFCQUFxQixDQUFDO2dCQUNwRSxPQUFPLEVBQUUsSUFBSTthQUNkLENBQUMsQ0FBQztZQUVILE1BQU0sSUFBQSx1Q0FBc0IsRUFDMUIsVUFBVSxFQUNWLFVBQVUsRUFDVixvQkFBb0IsRUFDcEIsbUJBQW1CLEVBQ25CLGlCQUFpQixFQUNqQiwwQkFBMEIsRUFDMUIsd0JBQXdCLENBQ3pCLENBQUM7WUFFRixNQUFNLENBQUMsZ0JBQWdCLENBQUMsZUFBZSxDQUFDLENBQUMscUJBQXFCLENBQUMsQ0FBQyxDQUFDLENBQUM7WUFDbEUsTUFBTSxDQUFDLGdCQUFnQixDQUFDLGVBQWUsQ0FBQyxDQUFDLG9CQUFvQixDQUMzRCxlQUFlLENBQ2hCLENBQUM7UUFDSixDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQyxtRUFBbUUsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNqRixNQUFNLFlBQVksR0FBRyxFQUFFLFNBQVMsRUFBRSxhQUFhLEVBQUUsTUFBTSxFQUFFLFNBQVMsRUFBRSxDQUFDO1lBQ3BFLGdCQUFnQixDQUFDLGVBQTZCLENBQUMscUJBQXFCLENBQ25FLFlBQVksQ0FDYixDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSxJQUFBLHVDQUFzQixFQUN6QyxVQUFVLEVBQ1YsVUFBVSxFQUNWLENBQUMsT0FBTyxDQUFDLEVBQ1QsRUFBRSxFQUNGLFlBQVksRUFDWixVQUFVLEVBQ1YsVUFBVSxDQUNYLENBQUM7WUFFRixNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsT0FBTyxDQUFDLFlBQVksQ0FBQyxDQUFDO1FBQ3ZDLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLGlFQUFpRSxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQy9FLE1BQU0sU0FBUyxHQUFHLElBQUksS0FBSyxDQUFDLGFBQWEsQ0FBQyxDQUFDO1lBQzFDLGdCQUFnQixDQUFDLGVBQTZCLENBQUMscUJBQXFCLENBQ25FLFNBQVMsQ0FDVixDQUFDO1lBRUYsTUFBTSxNQUFNLENBQ1YsSUFBQSx1Q0FBc0IsRUFDcEIsVUFBVSxFQUNWLFVBQVUsRUFDVixDQUFDLEtBQUssQ0FBQyxFQUNQLEVBQUUsRUFDRixZQUFZLEVBQ1osVUFBVSxFQUNWLFVBQVUsQ0FDWCxDQUNGLENBQUMsT0FBTyxDQUFDLE9BQU8sQ0FBQyxhQUFhLENBQUMsQ0FBQztRQUNuQyxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyByZXF1ZXN0U2NoZWR1bGVNZWV0aW5nIH0gZnJvbSAnLi4vU2NoZWR1bGVIZWxwZXInO1xuaW1wb3J0ICogYXMgYXBpQmFja2VuZEhlbHBlciBmcm9tICdAbGliL2FwaS1iYWNrZW5kLWhlbHBlcic7XG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIEluTWVtb3J5Q2FjaGUgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbi8vIE1vY2sgdGhlIGFwaS1iYWNrZW5kLWhlbHBlciBtb2R1bGVcbmplc3QubW9jaygnQGxpYi9hcGktYmFja2VuZC1oZWxwZXInLCAoKSA9PiAoe1xuICBzY2hlZHVsZU1lZXRpbmc6IGplc3QuZm4oKSxcbn0pKTtcblxuZGVzY3JpYmUoJ1NjaGVkdWxlSGVscGVyJywgKCkgPT4ge1xuICBkZXNjcmliZSgncmVxdWVzdFNjaGVkdWxlTWVldGluZycsICgpID0+IHtcbiAgICBsZXQgbW9ja0NsaWVudDogQXBvbGxvQ2xpZW50PGFueT47IC8vIGVzbGludC1kaXNhYmxlLWxpbmUgQHR5cGVzY3JpcHQtZXNsaW50L25vLWV4cGxpY2l0LWFueVxuXG4gICAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgICAgIG1vY2tDbGllbnQgPSBuZXcgQXBvbGxvQ2xpZW50KHsgY2FjaGU6IG5ldyBJbk1lbW9yeUNhY2hlKCkgfSk7IC8vIE1vY2sgQXBvbGxvQ2xpZW50XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGNhbGwgY2FsbFNjaGVkdWxlTWVldGluZ0FwaSB3aXRoIHRoZSBjb3JyZWN0IHBheWxvYWQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrVXNlcklkID0gJ3VzZXItMTIzJztcbiAgICAgIGNvbnN0IG1vY2tQYXJ0aWNpcGFudE5hbWVzID0gWydBbGljZScsICdCb2InXTtcbiAgICAgIGNvbnN0IG1vY2tEdXJhdGlvbk1pbnV0ZXMgPSA2MDtcbiAgICAgIGNvbnN0IG1vY2tQcmVmZXJyZWREYXRlID0gJzIwMjQtMDgtMTUnO1xuICAgICAgY29uc3QgbW9ja1ByZWZlcnJlZFN0YXJ0VGltZUZyb20gPSAnMTA6MDA6MDAnO1xuICAgICAgY29uc3QgbW9ja1ByZWZlcnJlZFN0YXJ0VGltZVRvID0gJzExOjAwOjAwJztcbiAgICAgIGNvbnN0IGV4cGVjdGVkUGF5bG9hZCA9IHtcbiAgICAgICAgcGFydGljaXBhbnROYW1lczogbW9ja1BhcnRpY2lwYW50TmFtZXMsXG4gICAgICAgIGR1cmF0aW9uTWludXRlczogbW9ja0R1cmF0aW9uTWludXRlcyxcbiAgICAgICAgcHJlZmVycmVkRGF0ZTogbW9ja1ByZWZlcnJlZERhdGUsXG4gICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZUZyb206IG1vY2tQcmVmZXJyZWRTdGFydFRpbWVGcm9tLFxuICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVUbzogbW9ja1ByZWZlcnJlZFN0YXJ0VGltZVRvLFxuICAgICAgfTtcblxuICAgICAgKGFwaUJhY2tlbmRIZWxwZXIuc2NoZWR1bGVNZWV0aW5nIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIH0pO1xuXG4gICAgICBhd2FpdCByZXF1ZXN0U2NoZWR1bGVNZWV0aW5nKFxuICAgICAgICBtb2NrQ2xpZW50LFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICBtb2NrUGFydGljaXBhbnROYW1lcyxcbiAgICAgICAgbW9ja0R1cmF0aW9uTWludXRlcyxcbiAgICAgICAgbW9ja1ByZWZlcnJlZERhdGUsXG4gICAgICAgIG1vY2tQcmVmZXJyZWRTdGFydFRpbWVGcm9tLFxuICAgICAgICBtb2NrUHJlZmVycmVkU3RhcnRUaW1lVG9cbiAgICAgICk7XG5cbiAgICAgIGV4cGVjdChhcGlCYWNrZW5kSGVscGVyLnNjaGVkdWxlTWVldGluZykudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KGFwaUJhY2tlbmRIZWxwZXIuc2NoZWR1bGVNZWV0aW5nKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgZXhwZWN0ZWRQYXlsb2FkXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gdGhlIHJlc3BvbnNlIGZyb20gY2FsbFNjaGVkdWxlTWVldGluZ0FwaSBvbiBzdWNjZXNzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3BvbnNlID0geyBtZWV0aW5nSWQ6ICdtZWV0aW5nLTQ1NicsIHN0YXR1czogJ1BFTkRJTkcnIH07XG4gICAgICAoYXBpQmFja2VuZEhlbHBlci5zY2hlZHVsZU1lZXRpbmcgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2UoXG4gICAgICAgIG1vY2tSZXNwb25zZVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcmVxdWVzdFNjaGVkdWxlTWVldGluZyhcbiAgICAgICAgbW9ja0NsaWVudCxcbiAgICAgICAgJ3VzZXItMTIzJyxcbiAgICAgICAgWydBbGljZSddLFxuICAgICAgICAzMCxcbiAgICAgICAgJzIwMjQtMDgtMTYnLFxuICAgICAgICAnMTQ6MDA6MDAnLFxuICAgICAgICAnMTU6MDA6MDAnXG4gICAgICApO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKG1vY2tSZXNwb25zZSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHRocm93IGFuIGVycm9yIGlmIGNhbGxTY2hlZHVsZU1lZXRpbmdBcGkgdGhyb3dzIGFuIGVycm9yJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0Vycm9yID0gbmV3IEVycm9yKCdBUEkgRmFpbHVyZScpO1xuICAgICAgKGFwaUJhY2tlbmRIZWxwZXIuc2NoZWR1bGVNZWV0aW5nIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWVPbmNlKFxuICAgICAgICBtb2NrRXJyb3JcbiAgICAgICk7XG5cbiAgICAgIGF3YWl0IGV4cGVjdChcbiAgICAgICAgcmVxdWVzdFNjaGVkdWxlTWVldGluZyhcbiAgICAgICAgICBtb2NrQ2xpZW50LFxuICAgICAgICAgICd1c2VyLTEyMycsXG4gICAgICAgICAgWydCb2InXSxcbiAgICAgICAgICA0NSxcbiAgICAgICAgICAnMjAyNC0wOC0xNycsXG4gICAgICAgICAgJzA5OjAwOjAwJyxcbiAgICAgICAgICAnMTA6MDA6MDAnXG4gICAgICAgIClcbiAgICAgICkucmVqZWN0cy50b1Rocm93KCdBUEkgRmFpbHVyZScpO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuIl19