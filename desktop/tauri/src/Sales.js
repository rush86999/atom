"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const useDataFetching_1 = require("./hooks/useDataFetching");
/**
 * Sales component for the desktop application.
 * Displays sales-related information like opportunities, contacts, and tasks.
 */
const Sales = () => {
    const { data: salesData, loading, error, fetchData, } = (0, useDataFetching_1.useDataFetching)();
    // Function to simulate fetching data from a CRM API
    const fetchSalesData = (0, react_1.useCallback)(() => {
        const dataFetcher = () => new Promise((resolve) => {
            setTimeout(() => {
                // In a real desktop app, this might come from a local database or a backend service.
                const mockDesktopCrmData = {
                    opportunities: [
                        {
                            id: "opp1",
                            name: "Desktop Synergy Corp Website Revamp",
                            stage: "Qualification",
                            value: 125000,
                        },
                        {
                            id: "opp2",
                            name: "Desktop Quantum Solutions Cloud Migration",
                            stage: "Proposal",
                            value: 355000,
                        },
                        {
                            id: "opp3",
                            name: "Desktop Innovate LLC AI Chatbot",
                            stage: "Negotiation",
                            value: 80000,
                        },
                    ],
                    contacts: [
                        {
                            id: "cont1",
                            name: "Laura Chen (Desktop)",
                            opportunityId: "opp1",
                        },
                        {
                            id: "cont2",
                            name: "David Rodriguez (Desktop)",
                            opportunityId: "opp2",
                        },
                        {
                            id: "cont3",
                            name: "Samantha Williams (Desktop)",
                            opportunityId: "opp3",
                        },
                    ],
                    tasks: [
                        {
                            id: "task1",
                            description: "Schedule desktop discovery call with Synergy Corp",
                            dueDate: "2024-08-06",
                        },
                        {
                            id: "task2",
                            description: "Finalize desktop proposal for Quantum Solutions",
                            dueDate: "2024-08-11",
                        },
                        {
                            id: "task3",
                            description: "Send updated desktop contract to Innovate LLC",
                            dueDate: "2024-07-31",
                        },
                    ],
                };
                resolve(mockDesktopCrmData);
            }, 1000); // 1-second delay
        });
        fetchData(dataFetcher);
    }, [fetchData]);
    // Fetch data when the component first mounts
    (0, react_1.useEffect)(() => {
        fetchSalesData();
    }, [fetchSalesData]);
    if (loading && !salesData) {
        // Show initial loading spinner
        return ((0, jsx_runtime_1.jsx)("div", { className: "sales-container", style: { padding: "20px" }, children: "Loading sales data..." }));
    }
    if (error) {
        return ((0, jsx_runtime_1.jsxs)("div", { className: "sales-container", style: { padding: "20px", color: "red" }, children: ["Error: ", error.message] }));
    }
    return ((0, jsx_runtime_1.jsxs)("div", { className: "sales-container", style: { padding: "20px", fontFamily: "Arial, sans-serif" }, children: [(0, jsx_runtime_1.jsxs)("div", { style: {
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                }, children: [(0, jsx_runtime_1.jsx)("h1", { children: "Sales Meeting Assistant (Desktop)" }), (0, jsx_runtime_1.jsx)("button", { onClick: () => fetchSalesData(), disabled: loading, style: { padding: "10px 15px", cursor: "pointer" }, children: loading ? "Refreshing..." : "Refresh Data" })] }), salesData ? ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)("h2", { children: "Upcoming Opportunities" }), (0, jsx_runtime_1.jsx)("ul", { children: salesData.opportunities.map((opp) => ((0, jsx_runtime_1.jsxs)("li", { children: [(0, jsx_runtime_1.jsx)("strong", { children: opp.name }), " - ", opp.stage, " ($", opp.value.toLocaleString(), ")"] }, opp.id))) }), (0, jsx_runtime_1.jsx)("h2", { children: "Key Contacts" }), (0, jsx_runtime_1.jsx)("ul", { children: salesData.contacts.map((contact) => ((0, jsx_runtime_1.jsx)("li", { children: contact.name }, contact.id))) }), (0, jsx_runtime_1.jsx)("h2", { children: "Pending Tasks" }), (0, jsx_runtime_1.jsx)("ul", { children: salesData.tasks.map((task) => ((0, jsx_runtime_1.jsxs)("li", { children: [task.description, " (Due: ", task.dueDate, ")"] }, task.id))) })] })) : ((0, jsx_runtime_1.jsx)("p", { children: "No sales data available. Click \"Refresh Data\" to load." }))] }));
};
exports.default = Sales;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU2FsZXMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJTYWxlcy50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsaUNBQXNEO0FBQ3RELDZEQUEwRDtBQTRCMUQ7OztHQUdHO0FBQ0gsTUFBTSxLQUFLLEdBQWEsR0FBRyxFQUFFO0lBQzNCLE1BQU0sRUFDSixJQUFJLEVBQUUsU0FBUyxFQUNmLE9BQU8sRUFDUCxLQUFLLEVBQ0wsU0FBUyxHQUNWLEdBQUcsSUFBQSxpQ0FBZSxHQUFhLENBQUM7SUFFakMsb0RBQW9EO0lBQ3BELE1BQU0sY0FBYyxHQUFHLElBQUEsbUJBQVcsRUFBQyxHQUFHLEVBQUU7UUFDdEMsTUFBTSxXQUFXLEdBQUcsR0FBRyxFQUFFLENBQ3ZCLElBQUksT0FBTyxDQUFZLENBQUMsT0FBTyxFQUFFLEVBQUU7WUFDakMsVUFBVSxDQUFDLEdBQUcsRUFBRTtnQkFDZCxxRkFBcUY7Z0JBQ3JGLE1BQU0sa0JBQWtCLEdBQWM7b0JBQ3BDLGFBQWEsRUFBRTt3QkFDYjs0QkFDRSxFQUFFLEVBQUUsTUFBTTs0QkFDVixJQUFJLEVBQUUscUNBQXFDOzRCQUMzQyxLQUFLLEVBQUUsZUFBZTs0QkFDdEIsS0FBSyxFQUFFLE1BQU07eUJBQ2Q7d0JBQ0Q7NEJBQ0UsRUFBRSxFQUFFLE1BQU07NEJBQ1YsSUFBSSxFQUFFLDJDQUEyQzs0QkFDakQsS0FBSyxFQUFFLFVBQVU7NEJBQ2pCLEtBQUssRUFBRSxNQUFNO3lCQUNkO3dCQUNEOzRCQUNFLEVBQUUsRUFBRSxNQUFNOzRCQUNWLElBQUksRUFBRSxpQ0FBaUM7NEJBQ3ZDLEtBQUssRUFBRSxhQUFhOzRCQUNwQixLQUFLLEVBQUUsS0FBSzt5QkFDYjtxQkFDRjtvQkFDRCxRQUFRLEVBQUU7d0JBQ1I7NEJBQ0UsRUFBRSxFQUFFLE9BQU87NEJBQ1gsSUFBSSxFQUFFLHNCQUFzQjs0QkFDNUIsYUFBYSxFQUFFLE1BQU07eUJBQ3RCO3dCQUNEOzRCQUNFLEVBQUUsRUFBRSxPQUFPOzRCQUNYLElBQUksRUFBRSwyQkFBMkI7NEJBQ2pDLGFBQWEsRUFBRSxNQUFNO3lCQUN0Qjt3QkFDRDs0QkFDRSxFQUFFLEVBQUUsT0FBTzs0QkFDWCxJQUFJLEVBQUUsNkJBQTZCOzRCQUNuQyxhQUFhLEVBQUUsTUFBTTt5QkFDdEI7cUJBQ0Y7b0JBQ0QsS0FBSyxFQUFFO3dCQUNMOzRCQUNFLEVBQUUsRUFBRSxPQUFPOzRCQUNYLFdBQVcsRUFDVCxtREFBbUQ7NEJBQ3JELE9BQU8sRUFBRSxZQUFZO3lCQUN0Qjt3QkFDRDs0QkFDRSxFQUFFLEVBQUUsT0FBTzs0QkFDWCxXQUFXLEVBQUUsaURBQWlEOzRCQUM5RCxPQUFPLEVBQUUsWUFBWTt5QkFDdEI7d0JBQ0Q7NEJBQ0UsRUFBRSxFQUFFLE9BQU87NEJBQ1gsV0FBVyxFQUFFLCtDQUErQzs0QkFDNUQsT0FBTyxFQUFFLFlBQVk7eUJBQ3RCO3FCQUNGO2lCQUNGLENBQUM7Z0JBQ0YsT0FBTyxDQUFDLGtCQUFrQixDQUFDLENBQUM7WUFDOUIsQ0FBQyxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsaUJBQWlCO1FBQzdCLENBQUMsQ0FBQyxDQUFDO1FBQ0wsU0FBUyxDQUFDLFdBQVcsQ0FBQyxDQUFDO0lBQ3pCLENBQUMsRUFBRSxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUM7SUFFaEIsNkNBQTZDO0lBQzdDLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixjQUFjLEVBQUUsQ0FBQztJQUNuQixDQUFDLEVBQUUsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDO0lBRXJCLElBQUksT0FBTyxJQUFJLENBQUMsU0FBUyxFQUFFLENBQUM7UUFDMUIsK0JBQStCO1FBQy9CLE9BQU8sQ0FDTCxnQ0FBSyxTQUFTLEVBQUMsaUJBQWlCLEVBQUMsS0FBSyxFQUFFLEVBQUUsT0FBTyxFQUFFLE1BQU0sRUFBRSxzQ0FFckQsQ0FDUCxDQUFDO0lBQ0osQ0FBQztJQUVELElBQUksS0FBSyxFQUFFLENBQUM7UUFDVixPQUFPLENBQ0wsaUNBQ0UsU0FBUyxFQUFDLGlCQUFpQixFQUMzQixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsd0JBRWhDLEtBQUssQ0FBQyxPQUFPLElBQ2pCLENBQ1AsQ0FBQztJQUNKLENBQUM7SUFFRCxPQUFPLENBQ0wsaUNBQ0UsU0FBUyxFQUFDLGlCQUFpQixFQUMzQixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsTUFBTSxFQUFFLFVBQVUsRUFBRSxtQkFBbUIsRUFBRSxhQUUzRCxpQ0FDRSxLQUFLLEVBQUU7b0JBQ0wsT0FBTyxFQUFFLE1BQU07b0JBQ2YsY0FBYyxFQUFFLGVBQWU7b0JBQy9CLFVBQVUsRUFBRSxRQUFRO2lCQUNyQixhQUVELCtFQUEwQyxFQUMxQyxtQ0FDRSxPQUFPLEVBQUUsR0FBRyxFQUFFLENBQUMsY0FBYyxFQUFFLEVBQy9CLFFBQVEsRUFBRSxPQUFPLEVBQ2pCLEtBQUssRUFBRSxFQUFFLE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSxFQUFFLFNBQVMsRUFBRSxZQUVqRCxPQUFPLENBQUMsQ0FBQyxDQUFDLGVBQWUsQ0FBQyxDQUFDLENBQUMsY0FBYyxHQUNwQyxJQUNMLEVBRUwsU0FBUyxDQUFDLENBQUMsQ0FBQyxDQUNYLDZEQUNFLG9FQUErQixFQUMvQix5Q0FDRyxTQUFTLENBQUMsYUFBYSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsRUFBRSxFQUFFLENBQUMsQ0FDcEMsMkNBQ0UsNkNBQVMsR0FBRyxDQUFDLElBQUksR0FBVSxTQUFJLEdBQUcsQ0FBQyxLQUFLLFNBQ3ZDLEdBQUcsQ0FBQyxLQUFLLENBQUMsY0FBYyxFQUFFLFVBRnBCLEdBQUcsQ0FBQyxFQUFFLENBR1YsQ0FDTixDQUFDLEdBQ0MsRUFFTCwwREFBcUIsRUFDckIseUNBQ0csU0FBUyxDQUFDLFFBQVEsQ0FBQyxHQUFHLENBQUMsQ0FBQyxPQUFPLEVBQUUsRUFBRSxDQUFDLENBQ25DLHlDQUFzQixPQUFPLENBQUMsSUFBSSxJQUF6QixPQUFPLENBQUMsRUFBRSxDQUFxQixDQUN6QyxDQUFDLEdBQ0MsRUFFTCwyREFBc0IsRUFDdEIseUNBQ0csU0FBUyxDQUFDLEtBQUssQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUFDLENBQzdCLDJDQUNHLElBQUksQ0FBQyxXQUFXLGFBQVMsSUFBSSxDQUFDLE9BQU8sVUFEL0IsSUFBSSxDQUFDLEVBQUUsQ0FFWCxDQUNOLENBQUMsR0FDQyxJQUNKLENBQ0osQ0FBQyxDQUFDLENBQUMsQ0FDRixxR0FBNkQsQ0FDOUQsSUFDRyxDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxLQUFLLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHsgdXNlRWZmZWN0LCB1c2VDYWxsYmFjayB9IGZyb20gXCJyZWFjdFwiO1xuaW1wb3J0IHsgdXNlRGF0YUZldGNoaW5nIH0gZnJvbSBcIi4vaG9va3MvdXNlRGF0YUZldGNoaW5nXCI7XG5cbi8vIERlZmluZSBUeXBlU2NyaXB0IGludGVyZmFjZXMgZm9yIGJldHRlciB0eXBlIHNhZmV0eSBhbmQgY29kZSBjbGFyaXR5XG5pbnRlcmZhY2UgT3Bwb3J0dW5pdHkge1xuICBpZDogc3RyaW5nO1xuICBuYW1lOiBzdHJpbmc7XG4gIHN0YWdlOiBzdHJpbmc7XG4gIHZhbHVlOiBudW1iZXI7XG59XG5cbmludGVyZmFjZSBDb250YWN0IHtcbiAgaWQ6IHN0cmluZztcbiAgbmFtZTogc3RyaW5nO1xuICBvcHBvcnR1bml0eUlkOiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBUYXNrIHtcbiAgaWQ6IHN0cmluZztcbiAgZGVzY3JpcHRpb246IHN0cmluZztcbiAgZHVlRGF0ZTogc3RyaW5nO1xufVxuXG5pbnRlcmZhY2UgU2FsZXNEYXRhIHtcbiAgb3Bwb3J0dW5pdGllczogT3Bwb3J0dW5pdHlbXTtcbiAgY29udGFjdHM6IENvbnRhY3RbXTtcbiAgdGFza3M6IFRhc2tbXTtcbn1cblxuLyoqXG4gKiBTYWxlcyBjb21wb25lbnQgZm9yIHRoZSBkZXNrdG9wIGFwcGxpY2F0aW9uLlxuICogRGlzcGxheXMgc2FsZXMtcmVsYXRlZCBpbmZvcm1hdGlvbiBsaWtlIG9wcG9ydHVuaXRpZXMsIGNvbnRhY3RzLCBhbmQgdGFza3MuXG4gKi9cbmNvbnN0IFNhbGVzOiBSZWFjdC5GQyA9ICgpID0+IHtcbiAgY29uc3Qge1xuICAgIGRhdGE6IHNhbGVzRGF0YSxcbiAgICBsb2FkaW5nLFxuICAgIGVycm9yLFxuICAgIGZldGNoRGF0YSxcbiAgfSA9IHVzZURhdGFGZXRjaGluZzxTYWxlc0RhdGE+KCk7XG5cbiAgLy8gRnVuY3Rpb24gdG8gc2ltdWxhdGUgZmV0Y2hpbmcgZGF0YSBmcm9tIGEgQ1JNIEFQSVxuICBjb25zdCBmZXRjaFNhbGVzRGF0YSA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICBjb25zdCBkYXRhRmV0Y2hlciA9ICgpID0+XG4gICAgICBuZXcgUHJvbWlzZTxTYWxlc0RhdGE+KChyZXNvbHZlKSA9PiB7XG4gICAgICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICAgIC8vIEluIGEgcmVhbCBkZXNrdG9wIGFwcCwgdGhpcyBtaWdodCBjb21lIGZyb20gYSBsb2NhbCBkYXRhYmFzZSBvciBhIGJhY2tlbmQgc2VydmljZS5cbiAgICAgICAgICBjb25zdCBtb2NrRGVza3RvcENybURhdGE6IFNhbGVzRGF0YSA9IHtcbiAgICAgICAgICAgIG9wcG9ydHVuaXRpZXM6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGlkOiBcIm9wcDFcIixcbiAgICAgICAgICAgICAgICBuYW1lOiBcIkRlc2t0b3AgU3luZXJneSBDb3JwIFdlYnNpdGUgUmV2YW1wXCIsXG4gICAgICAgICAgICAgICAgc3RhZ2U6IFwiUXVhbGlmaWNhdGlvblwiLFxuICAgICAgICAgICAgICAgIHZhbHVlOiAxMjUwMDAsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogXCJvcHAyXCIsXG4gICAgICAgICAgICAgICAgbmFtZTogXCJEZXNrdG9wIFF1YW50dW0gU29sdXRpb25zIENsb3VkIE1pZ3JhdGlvblwiLFxuICAgICAgICAgICAgICAgIHN0YWdlOiBcIlByb3Bvc2FsXCIsXG4gICAgICAgICAgICAgICAgdmFsdWU6IDM1NTAwMCxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGlkOiBcIm9wcDNcIixcbiAgICAgICAgICAgICAgICBuYW1lOiBcIkRlc2t0b3AgSW5ub3ZhdGUgTExDIEFJIENoYXRib3RcIixcbiAgICAgICAgICAgICAgICBzdGFnZTogXCJOZWdvdGlhdGlvblwiLFxuICAgICAgICAgICAgICAgIHZhbHVlOiA4MDAwMCxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgICBjb250YWN0czogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaWQ6IFwiY29udDFcIixcbiAgICAgICAgICAgICAgICBuYW1lOiBcIkxhdXJhIENoZW4gKERlc2t0b3ApXCIsXG4gICAgICAgICAgICAgICAgb3Bwb3J0dW5pdHlJZDogXCJvcHAxXCIsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogXCJjb250MlwiLFxuICAgICAgICAgICAgICAgIG5hbWU6IFwiRGF2aWQgUm9kcmlndWV6IChEZXNrdG9wKVwiLFxuICAgICAgICAgICAgICAgIG9wcG9ydHVuaXR5SWQ6IFwib3BwMlwiLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaWQ6IFwiY29udDNcIixcbiAgICAgICAgICAgICAgICBuYW1lOiBcIlNhbWFudGhhIFdpbGxpYW1zIChEZXNrdG9wKVwiLFxuICAgICAgICAgICAgICAgIG9wcG9ydHVuaXR5SWQ6IFwib3BwM1wiLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICAgIHRhc2tzOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogXCJ0YXNrMVwiLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgICAgICAgXCJTY2hlZHVsZSBkZXNrdG9wIGRpc2NvdmVyeSBjYWxsIHdpdGggU3luZXJneSBDb3JwXCIsXG4gICAgICAgICAgICAgICAgZHVlRGF0ZTogXCIyMDI0LTA4LTA2XCIsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogXCJ0YXNrMlwiLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiBcIkZpbmFsaXplIGRlc2t0b3AgcHJvcG9zYWwgZm9yIFF1YW50dW0gU29sdXRpb25zXCIsXG4gICAgICAgICAgICAgICAgZHVlRGF0ZTogXCIyMDI0LTA4LTExXCIsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogXCJ0YXNrM1wiLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiBcIlNlbmQgdXBkYXRlZCBkZXNrdG9wIGNvbnRyYWN0IHRvIElubm92YXRlIExMQ1wiLFxuICAgICAgICAgICAgICAgIGR1ZURhdGU6IFwiMjAyNC0wNy0zMVwiLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIHJlc29sdmUobW9ja0Rlc2t0b3BDcm1EYXRhKTtcbiAgICAgICAgfSwgMTAwMCk7IC8vIDEtc2Vjb25kIGRlbGF5XG4gICAgICB9KTtcbiAgICBmZXRjaERhdGEoZGF0YUZldGNoZXIpO1xuICB9LCBbZmV0Y2hEYXRhXSk7XG5cbiAgLy8gRmV0Y2ggZGF0YSB3aGVuIHRoZSBjb21wb25lbnQgZmlyc3QgbW91bnRzXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgZmV0Y2hTYWxlc0RhdGEoKTtcbiAgfSwgW2ZldGNoU2FsZXNEYXRhXSk7XG5cbiAgaWYgKGxvYWRpbmcgJiYgIXNhbGVzRGF0YSkge1xuICAgIC8vIFNob3cgaW5pdGlhbCBsb2FkaW5nIHNwaW5uZXJcbiAgICByZXR1cm4gKFxuICAgICAgPGRpdiBjbGFzc05hbWU9XCJzYWxlcy1jb250YWluZXJcIiBzdHlsZT17eyBwYWRkaW5nOiBcIjIwcHhcIiB9fT5cbiAgICAgICAgTG9hZGluZyBzYWxlcyBkYXRhLi4uXG4gICAgICA8L2Rpdj5cbiAgICApO1xuICB9XG5cbiAgaWYgKGVycm9yKSB7XG4gICAgcmV0dXJuIChcbiAgICAgIDxkaXZcbiAgICAgICAgY2xhc3NOYW1lPVwic2FsZXMtY29udGFpbmVyXCJcbiAgICAgICAgc3R5bGU9e3sgcGFkZGluZzogXCIyMHB4XCIsIGNvbG9yOiBcInJlZFwiIH19XG4gICAgICA+XG4gICAgICAgIEVycm9yOiB7ZXJyb3IubWVzc2FnZX1cbiAgICAgIDwvZGl2PlxuICAgICk7XG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGNsYXNzTmFtZT1cInNhbGVzLWNvbnRhaW5lclwiXG4gICAgICBzdHlsZT17eyBwYWRkaW5nOiBcIjIwcHhcIiwgZm9udEZhbWlseTogXCJBcmlhbCwgc2Fucy1zZXJpZlwiIH19XG4gICAgPlxuICAgICAgPGRpdlxuICAgICAgICBzdHlsZT17e1xuICAgICAgICAgIGRpc3BsYXk6IFwiZmxleFwiLFxuICAgICAgICAgIGp1c3RpZnlDb250ZW50OiBcInNwYWNlLWJldHdlZW5cIixcbiAgICAgICAgICBhbGlnbkl0ZW1zOiBcImNlbnRlclwiLFxuICAgICAgICB9fVxuICAgICAgPlxuICAgICAgICA8aDE+U2FsZXMgTWVldGluZyBBc3Npc3RhbnQgKERlc2t0b3ApPC9oMT5cbiAgICAgICAgPGJ1dHRvblxuICAgICAgICAgIG9uQ2xpY2s9eygpID0+IGZldGNoU2FsZXNEYXRhKCl9XG4gICAgICAgICAgZGlzYWJsZWQ9e2xvYWRpbmd9XG4gICAgICAgICAgc3R5bGU9e3sgcGFkZGluZzogXCIxMHB4IDE1cHhcIiwgY3Vyc29yOiBcInBvaW50ZXJcIiB9fVxuICAgICAgICA+XG4gICAgICAgICAge2xvYWRpbmcgPyBcIlJlZnJlc2hpbmcuLi5cIiA6IFwiUmVmcmVzaCBEYXRhXCJ9XG4gICAgICAgIDwvYnV0dG9uPlxuICAgICAgPC9kaXY+XG5cbiAgICAgIHtzYWxlc0RhdGEgPyAoXG4gICAgICAgIDw+XG4gICAgICAgICAgPGgyPlVwY29taW5nIE9wcG9ydHVuaXRpZXM8L2gyPlxuICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgIHtzYWxlc0RhdGEub3Bwb3J0dW5pdGllcy5tYXAoKG9wcCkgPT4gKFxuICAgICAgICAgICAgICA8bGkga2V5PXtvcHAuaWR9PlxuICAgICAgICAgICAgICAgIDxzdHJvbmc+e29wcC5uYW1lfTwvc3Ryb25nPiAtIHtvcHAuc3RhZ2V9ICgkXG4gICAgICAgICAgICAgICAge29wcC52YWx1ZS50b0xvY2FsZVN0cmluZygpfSlcbiAgICAgICAgICAgICAgPC9saT5cbiAgICAgICAgICAgICkpfVxuICAgICAgICAgIDwvdWw+XG5cbiAgICAgICAgICA8aDI+S2V5IENvbnRhY3RzPC9oMj5cbiAgICAgICAgICA8dWw+XG4gICAgICAgICAgICB7c2FsZXNEYXRhLmNvbnRhY3RzLm1hcCgoY29udGFjdCkgPT4gKFxuICAgICAgICAgICAgICA8bGkga2V5PXtjb250YWN0LmlkfT57Y29udGFjdC5uYW1lfTwvbGk+XG4gICAgICAgICAgICApKX1cbiAgICAgICAgICA8L3VsPlxuXG4gICAgICAgICAgPGgyPlBlbmRpbmcgVGFza3M8L2gyPlxuICAgICAgICAgIDx1bD5cbiAgICAgICAgICAgIHtzYWxlc0RhdGEudGFza3MubWFwKCh0YXNrKSA9PiAoXG4gICAgICAgICAgICAgIDxsaSBrZXk9e3Rhc2suaWR9PlxuICAgICAgICAgICAgICAgIHt0YXNrLmRlc2NyaXB0aW9ufSAoRHVlOiB7dGFzay5kdWVEYXRlfSlcbiAgICAgICAgICAgICAgPC9saT5cbiAgICAgICAgICAgICkpfVxuICAgICAgICAgIDwvdWw+XG4gICAgICAgIDwvPlxuICAgICAgKSA6IChcbiAgICAgICAgPHA+Tm8gc2FsZXMgZGF0YSBhdmFpbGFibGUuIENsaWNrIFwiUmVmcmVzaCBEYXRhXCIgdG8gbG9hZC48L3A+XG4gICAgICApfVxuICAgIDwvZGl2PlxuICApO1xufTtcblxuZXhwb3J0IGRlZmF1bHQgU2FsZXM7XG4iXX0=