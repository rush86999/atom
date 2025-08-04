"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const useDataFetching_1 = require("./hooks/useDataFetching");
// Mock data representing a company's internal knowledge base for the desktop app
const allArticles = [
    {
        id: "kb-d-1",
        title: "Desktop: How to Set Up Your VPN",
        content: "To set up your VPN on a desktop, please download the GlobalProtect client from the IT portal.",
        category: "IT",
        lastUpdated: "2024-06-18",
    },
    {
        id: "kb-d-2",
        title: "Desktop: Submitting Expense Reports",
        content: 'All expense reports for desktop users must be submitted through the "Expenses" web portal.',
        category: "HR",
        lastUpdated: "2024-07-05",
    },
    {
        id: "kb-d-3",
        title: "Desktop: Requesting Time Off",
        content: "Paid time off (PTO) can be requested via the Workday portal. There is no separate desktop application for this.",
        category: "HR",
        lastUpdated: "2024-05-22",
    },
    {
        id: "kb-d-4",
        title: "Desktop: Git Branching Strategy",
        content: "Our standard Git branching strategy is GitFlow. Use your preferred Git client on your desktop.",
        category: "Engineering",
        lastUpdated: "2024-07-28",
    },
];
/**
 * A single article component for displaying search results.
 */
const ArticleCard = ({ article }) => ((0, jsx_runtime_1.jsxs)("div", { style: {
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "16px",
        marginBottom: "16px",
        backgroundColor: "#f9f9f9",
    }, children: [(0, jsx_runtime_1.jsx)("h3", { style: { marginTop: 0 }, children: article.title }), (0, jsx_runtime_1.jsx)("p", { children: article.content }), (0, jsx_runtime_1.jsxs)("div", { style: { fontSize: "0.9em", color: "#555" }, children: [(0, jsx_runtime_1.jsx)("span", { style: { fontWeight: "bold" }, children: "Category:" }), " ", article.category, " |", " ", (0, jsx_runtime_1.jsx)("span", { style: { fontWeight: "bold" }, children: "Last Updated:" }), " ", article.lastUpdated] })] }));
/**
 * Internal Support Agent component for the desktop application.
 * It provides a searchable interface for a mock knowledge base.
 */
const Support = () => {
    const { data: articles, loading, error, fetchData, } = (0, useDataFetching_1.useDataFetching)();
    const [query, setQuery] = (0, react_1.useState)("");
    // Function to simulate searching for articles.
    const searchArticles = (0, react_1.useCallback)((searchTerm) => {
        const dataFetcher = () => new Promise((resolve) => {
            setTimeout(() => {
                try {
                    if (!searchTerm) {
                        resolve(allArticles);
                    }
                    else {
                        const lowercasedQuery = searchTerm.toLowerCase();
                        const results = allArticles.filter((article) => article.title.toLowerCase().includes(lowercasedQuery) ||
                            article.content.toLowerCase().includes(lowercasedQuery));
                        resolve(results);
                    }
                }
                catch (e) {
                    // In a real app, you might reject the promise here.
                    // For this simulation, we'll just resolve with an empty array on error.
                    resolve([]);
                }
            }, 500); // 0.5-second delay
        });
        fetchData(dataFetcher);
    }, [fetchData]);
    // Perform an initial search to show all articles when the component mounts.
    (0, react_1.useEffect)(() => {
        searchArticles("");
    }, [searchArticles]);
    const handleSearch = (e) => {
        e.preventDefault();
        searchArticles(query);
    };
    return ((0, jsx_runtime_1.jsxs)("div", { style: { padding: "20px", fontFamily: "Arial, sans-serif" }, children: [(0, jsx_runtime_1.jsx)("h1", { children: "Internal Support Agent (Desktop)" }), (0, jsx_runtime_1.jsx)("p", { children: "Search the knowledge base for articles and solutions." }), (0, jsx_runtime_1.jsxs)("form", { onSubmit: handleSearch, style: { margin: "20px 0", display: "flex", gap: "10px" }, children: [(0, jsx_runtime_1.jsx)("input", { type: "text", value: query, onChange: (e) => setQuery(e.target.value), placeholder: "e.g., 'vpn'", style: {
                            width: "300px",
                            padding: "10px",
                            fontSize: "1em",
                            border: "1px solid #ccc",
                            borderRadius: "4px",
                        }, disabled: loading }), (0, jsx_runtime_1.jsx)("button", { type: "submit", disabled: loading, style: {
                            padding: "10px 15px",
                            cursor: "pointer",
                            border: "none",
                            backgroundColor: "purple",
                            color: "white",
                            borderRadius: "4px",
                        }, children: loading ? "Searching..." : "Search" })] }), error && ((0, jsx_runtime_1.jsxs)("div", { style: { color: "red", marginBottom: "20px" }, children: ["Error: ", error.message] })), (0, jsx_runtime_1.jsx)("div", { children: loading ? ((0, jsx_runtime_1.jsx)("p", { children: "Loading articles..." })) : articles && articles.length > 0 ? (articles.map((article) => ((0, jsx_runtime_1.jsx)(ArticleCard, { article: article }, article.id)))) : ((0, jsx_runtime_1.jsx)("p", { children: "No articles found. Try a different search term or an empty search to see all articles." })) })] }));
};
exports.default = Support;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU3VwcG9ydC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlN1cHBvcnQudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUFnRTtBQUNoRSw2REFBMEQ7QUFXMUQsaUZBQWlGO0FBQ2pGLE1BQU0sV0FBVyxHQUFjO0lBQzdCO1FBQ0UsRUFBRSxFQUFFLFFBQVE7UUFDWixLQUFLLEVBQUUsaUNBQWlDO1FBQ3hDLE9BQU8sRUFDTCwrRkFBK0Y7UUFDakcsUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLFFBQVE7UUFDWixLQUFLLEVBQUUscUNBQXFDO1FBQzVDLE9BQU8sRUFDTCw0RkFBNEY7UUFDOUYsUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLFFBQVE7UUFDWixLQUFLLEVBQUUsOEJBQThCO1FBQ3JDLE9BQU8sRUFDTCxpSEFBaUg7UUFDbkgsUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLFFBQVE7UUFDWixLQUFLLEVBQUUsaUNBQWlDO1FBQ3hDLE9BQU8sRUFDTCxnR0FBZ0c7UUFDbEcsUUFBUSxFQUFFLGFBQWE7UUFDdkIsV0FBVyxFQUFFLFlBQVk7S0FDMUI7Q0FDRixDQUFDO0FBRUY7O0dBRUc7QUFDSCxNQUFNLFdBQVcsR0FBRyxDQUFDLEVBQUUsT0FBTyxFQUF3QixFQUFFLEVBQUUsQ0FBQyxDQUN6RCxpQ0FDRSxLQUFLLEVBQUU7UUFDTCxNQUFNLEVBQUUsZ0JBQWdCO1FBQ3hCLFlBQVksRUFBRSxLQUFLO1FBQ25CLE9BQU8sRUFBRSxNQUFNO1FBQ2YsWUFBWSxFQUFFLE1BQU07UUFDcEIsZUFBZSxFQUFFLFNBQVM7S0FDM0IsYUFFRCwrQkFBSSxLQUFLLEVBQUUsRUFBRSxTQUFTLEVBQUUsQ0FBQyxFQUFFLFlBQUcsT0FBTyxDQUFD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LENBQ0wsR0FDRyxJQUNGLENBQ1AsQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLGtCQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VTdGF0ZSwgdXNlRWZmZWN0LCB1c2VDYWxsYmFjayB9IGZyb20gXCJyZWFjdFwiO1xuaW1wb3J0IHsgdXNlRGF0YUZldGNoaW5nIH0gZnJvbSBcIi4vaG9va3MvdXNlRGF0YUZldGNoaW5nXCI7XG5cbi8vIERlZmluZSB0aGUgc3RydWN0dXJlIGZvciBhIGtub3dsZWRnZSBiYXNlIGFydGljbGVcbmV4cG9ydCBpbnRlcmZhY2UgQXJ0aWNsZSB7XG4gIGlkOiBzdHJpbmc7XG4gIHRpdGxlOiBzdHJpbmc7XG4gIGNvbnRlbnQ6IHN0cmluZztcbiAgY2F0ZWdvcnk6IFwiSFJcIiB8IFwiSVRcIiB8IFwiRW5naW5lZXJpbmdcIjtcbiAgbGFzdFVwZGF0ZWQ6IHN0cmluZztcbn1cblxuLy8gTW9jayBkYXRhIHJlcHJlc2VudGluZyBhIGNvbXBhbnkncyBpbnRlcm5hbCBrbm93bGVkZ2UgYmFzZSBmb3IgdGhlIGRlc2t0b3AgYXBwXG5jb25zdCBhbGxBcnRpY2xlczogQXJ0aWNsZVtdID0gW1xuICB7XG4gICAgaWQ6IFwia2ItZC0xXCIsXG4gICAgdGl0bGU6IFwiRGVza3RvcDogSG93IHRvIFNldCBVcCBZb3VyIFZQTlwiLFxuICAgIGNvbnRlbnQ6XG4gICAgICBcIlRvIHNldCB1cCB5b3VyIFZQTiBvbiBhIGRlc2t0b3AsIHBsZWFzZSBkb3dubG9hZCB0aGUgR2xvYmFsUHJvdGVjdCBjbGllbnQgZnJvbSB0aGUgSVQgcG9ydGFsLlwiLFxuICAgIGNhdGVnb3J5OiBcIklUXCIsXG4gICAgbGFzdFVwZGF0ZWQ6IFwiMjAyNC0wNi0xOFwiLFxuICB9LFxuICB7XG4gICAgaWQ6IFwia2ItZC0yXCIsXG4gICAgdGl0bGU6IFwiRGVza3RvcDogU3VibWl0dGluZyBFeHBlbnNlIFJlcG9ydHNcIixcbiAgICBjb250ZW50OlxuICAgICAgJ0FsbCBleHBlbnNlIHJlcG9ydHMgZm9yIGRlc2t0b3AgdXNlcnMgbXVzdCBiZSBzdWJtaXR0ZWQgdGhyb3VnaCB0aGUgXCJFeHBlbnNlc1wiIHdlYiBwb3J0YWwuJyxcbiAgICBjYXRlZ29yeTogXCJIUlwiLFxuICAgIGxhc3RVcGRhdGVkOiBcIjIwMjQtMDctMDVcIixcbiAgfSxcbiAge1xuICAgIGlkOiBcImtiLWQtM1wiLFxuICAgIHRpdGxlOiBcIkRlc2t0b3A6IFJlcXVlc3RpbmcgVGltZSBPZmZcIixcbiAgICBjb250ZW50OlxuICAgICAgXCJQYWlkIHRpbWUgb2ZmIChQVE8pIGNhbiBiZSByZXF1ZXN0ZWQgdmlhIHRoZSBXb3JrZGF5IHBvcnRhbC4gVGhlcmUgaXMgbm8gc2VwYXJhdGUgZGVza3RvcCBhcHBsaWNhdGlvbiBmb3IgdGhpcy5cIixcbiAgICBjYXRlZ29yeTogXCJIUlwiLFxuICAgIGxhc3RVcGRhdGVkOiBcIjIwMjQtMDUtMjJcIixcbiAgfSxcbiAge1xuICAgIGlkOiBcImtiLWQtNFwiLFxuICAgIHRpdGxlOiBcIkRlc2t0b3A6IEdpdCBCcmFuY2hpbmcgU3RyYXRlZ3lcIixcbiAgICBjb250ZW50OlxuICAgICAgXCJPdXIgc3RhbmRhcmQgR2l0IGJyYW5jaGluZyBzdHJhdGVneSBpcyBHaXRGbG93LiBVc2UgeW91ciBwcmVmZXJyZWQgR2l0IGNsaWVudCBvbiB5b3VyIGRlc2t0b3AuXCIsXG4gICAgY2F0ZWdvcnk6IFwiRW5naW5lZXJpbmdcIixcbiAgICBsYXN0VXBkYXRlZDogXCIyMDI0LTA3LTI4XCIsXG4gIH0sXG5dO1xuXG4vKipcbiAqIEEgc2luZ2xlIGFydGljbGUgY29tcG9uZW50IGZvciBkaXNwbGF5aW5nIHNlYXJjaCByZXN1bHRzLlxuICovXG5jb25zdCBBcnRpY2xlQ2FyZCA9ICh7IGFydGljbGUgfTogeyBhcnRpY2xlOiBBcnRpY2xlIH0pID0+IChcbiAgPGRpdlxuICAgIHN0eWxlPXt7XG4gICAgICBib3JkZXI6IFwiMXB4IHNvbGlkICNkZGRcIixcbiAgICAgIGJvcmRlclJhZGl1czogXCI4cHhcIixcbiAgICAgIHBhZGRpbmc6IFwiMTZweFwiLFxuICAgICAgbWFyZ2luQm90dG9tOiBcIjE2cHhcIixcbiAgICAgIGJhY2tncm91bmRDb2xvcjogXCIjZjlmOWY5XCIsXG4gICAgfX1cbiAgPlxuICAgIDxoMyBzdHlsZT17eyBtYXJnaW5Ub3A6IDAgfX0+e2FydGljbGUudGl0bGV9PC9oMz5cbiAgICA8cD57YXJ0aWNsZS5jb250ZW50fTwvcD5cbiAgICA8ZGl2IHN0eWxlPXt7IGZvbnRTaXplOiBcIjAuOWVtXCIsIGNvbG9yOiBcIiM1NTVcIiB9fT5cbiAgICAgIDxzcGFuIHN0eWxlPXt7IGZvbnRXZWlnaHQ6IFwiYm9sZFwiIH19PkNhdGVnb3J5Ojwvc3Bhbj4ge2FydGljbGUuY2F0ZWdvcnl9IHx7XCIgXCJ9XG4gICAgICA8c3BhbiBzdHlsZT17eyBmb250V2VpZ2h0OiBcImJvbGRcIiB9fT5MYXN0IFVwZGF0ZWQ6PC9zcGFuPntcIiBcIn1cbiAgICAgIHthcnRpY2xlLmxhc3RVcGRhdGVkfVxuICAgIDwvZGl2PlxuICA8L2Rpdj5cbik7XG5cbi8qKlxuICogSW50ZXJuYWwgU3VwcG9ydCBBZ2VudCBjb21wb25lbnQgZm9yIHRoZSBkZXNrdG9wIGFwcGxpY2F0aW9uLlxuICogSXQgcHJvdmlkZXMgYSBzZWFyY2hhYmxlIGludGVyZmFjZSBmb3IgYSBtb2NrIGtub3dsZWRnZSBiYXNlLlxuICovXG5jb25zdCBTdXBwb3J0OiBSZWFjdC5GQyA9ICgpID0+IHtcbiAgY29uc3Qge1xuICAgIGRhdGE6IGFydGljbGVzLFxuICAgIGxvYWRpbmcsXG4gICAgZXJyb3IsXG4gICAgZmV0Y2hEYXRhLFxuICB9ID0gdXNlRGF0YUZldGNoaW5nPEFydGljbGVbXT4oKTtcbiAgY29uc3QgW3F1ZXJ5LCBzZXRRdWVyeV0gPSB1c2VTdGF0ZShcIlwiKTtcblxuICAvLyBGdW5jdGlvbiB0byBzaW11bGF0ZSBzZWFyY2hpbmcgZm9yIGFydGljbGVzLlxuICBjb25zdCBzZWFyY2hBcnRpY2xlcyA9IHVzZUNhbGxiYWNrKFxuICAgIChzZWFyY2hUZXJtOiBzdHJpbmcpID0+IHtcbiAgICAgIGNvbnN0IGRhdGFGZXRjaGVyID0gKCkgPT5cbiAgICAgICAgbmV3IFByb21pc2U8QXJ0aWNsZVtdPigocmVzb2x2ZSkgPT4ge1xuICAgICAgICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgaWYgKCFzZWFyY2hUZXJtKSB7XG4gICAgICAgICAgICAgICAgcmVzb2x2ZShhbGxBcnRpY2xlcyk7XG4gICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgY29uc3QgbG93ZXJjYXNlZFF1ZXJ5ID0gc2VhcmNoVGVybS50b0xvd2VyQ2FzZSgpO1xuICAgICAgICAgICAgICAgIGNvbnN0IHJlc3VsdHMgPSBhbGxBcnRpY2xlcy5maWx0ZXIoXG4gICAgICAgICAgICAgICAgICAoYXJ0aWNsZSkgPT5cbiAgICAgICAgICAgICAgICAgICAgYXJ0aWNsZS50aXRsZS50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKGxvd2VyY2FzZWRRdWVyeSkgfHxcbiAgICAgICAgICAgICAgICAgICAgYXJ0aWNsZS5jb250ZW50LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMobG93ZXJjYXNlZFF1ZXJ5KSxcbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIHJlc29sdmUocmVzdWx0cyk7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgICAgLy8gSW4gYSByZWFsIGFwcCwgeW91IG1pZ2h0IHJlamVjdCB0aGUgcHJvbWlzZSBoZXJlLlxuICAgICAgICAgICAgICAvLyBGb3IgdGhpcyBzaW11bGF0aW9uLCB3ZSdsbCBqdXN0IHJlc29sdmUgd2l0aCBhbiBlbXB0eSBhcnJheSBvbiBlcnJvci5cbiAgICAgICAgICAgICAgcmVzb2x2ZShbXSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSwgNTAwKTsgLy8gMC41LXNlY29uZCBkZWxheVxuICAgICAgICB9KTtcbiAgICAgIGZldGNoRGF0YShkYXRhRmV0Y2hlcik7XG4gICAgfSxcbiAgICBbZmV0Y2hEYXRhXSxcbiAgKTtcblxuICAvLyBQZXJmb3JtIGFuIGluaXRpYWwgc2VhcmNoIHRvIHNob3cgYWxsIGFydGljbGVzIHdoZW4gdGhlIGNvbXBvbmVudCBtb3VudHMuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgc2VhcmNoQXJ0aWNsZXMoXCJcIik7XG4gIH0sIFtzZWFyY2hBcnRpY2xlc10pO1xuXG4gIGNvbnN0IGhhbmRsZVNlYXJjaCA9IChlOiBSZWFjdC5Gb3JtRXZlbnQpID0+IHtcbiAgICBlLnByZXZlbnREZWZhdWx0KCk7XG4gICAgc2VhcmNoQXJ0aWNsZXMocXVlcnkpO1xuICB9O1xuXG4gIHJldHVybiAoXG4gICAgPGRpdiBzdHlsZT17eyBwYWRkaW5nOiBcIjIwcHhcIiwgZm9udEZhbWlseTogXCJBcmlhbCwgc2Fucy1zZXJpZlwiIH19PlxuICAgICAgPGgxPkludGVybmFsIFN1cHBvcnQgQWdlbnQgKERlc2t0b3ApPC9oMT5cbiAgICAgIDxwPlNlYXJjaCB0aGUga25vd2xlZGdlIGJhc2UgZm9yIGFydGljbGVzIGFuZCBzb2x1dGlvbnMuPC9wPlxuXG4gICAgICA8Zm9ybVxuICAgICAgICBvblN1Ym1pdD17aGFuZGxlU2VhcmNofVxuICAgICAgICBzdHlsZT17eyBtYXJnaW46IFwiMjBweCAwXCIsIGRpc3BsYXk6IFwiZmxleFwiLCBnYXA6IFwiMTBweFwiIH19XG4gICAgICA+XG4gICAgICAgIDxpbnB1dFxuICAgICAgICAgIHR5cGU9XCJ0ZXh0XCJcbiAgICAgICAgICB2YWx1ZT17cXVlcnl9XG4gICAgICAgICAgb25DaGFuZ2U9eyhlKSA9PiBzZXRRdWVyeShlLnRhcmdldC52YWx1ZSl9XG4gICAgICAgICAgcGxhY2Vob2xkZXI9XCJlLmcuLCAndnBuJ1wiXG4gICAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICAgIHdpZHRoOiBcIjMwMHB4XCIsXG4gICAgICAgICAgICBwYWRkaW5nOiBcIjEwcHhcIixcbiAgICAgICAgICAgIGZvbnRTaXplOiBcIjFlbVwiLFxuICAgICAgICAgICAgYm9yZGVyOiBcIjFweCBzb2xpZCAjY2NjXCIsXG4gICAgICAgICAgICBib3JkZXJSYWRpdXM6IFwiNHB4XCIsXG4gICAgICAgICAgfX1cbiAgICAgICAgICBkaXNhYmxlZD17bG9hZGluZ31cbiAgICAgICAgLz5cbiAgICAgICAgPGJ1dHRvblxuICAgICAgICAgIHR5cGU9XCJzdWJtaXRcIlxuICAgICAgICAgIGRpc2FibGVkPXtsb2FkaW5nfVxuICAgICAgICAgIHN0eWxlPXt7XG4gICAgICAgICAgICBwYWRkaW5nOiBcIjEwcHggMTVweFwiLFxuICAgICAgICAgICAgY3Vyc29yOiBcInBvaW50ZXJcIixcbiAgICAgICAgICAgIGJvcmRlcjogXCJub25lXCIsXG4gICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3I6IFwicHVycGxlXCIsXG4gICAgICAgICAgICBjb2xvcjogXCJ3aGl0ZVwiLFxuICAgICAgICAgICAgYm9yZGVyUmFkaXVzOiBcIjRweFwiLFxuICAgICAgICAgIH19XG4gICAgICAgID5cbiAgICAgICAgICB7bG9hZGluZyA/IFwiU2VhcmNoaW5nLi4uXCIgOiBcIlNlYXJjaFwifVxuICAgICAgICA8L2J1dHRvbj5cbiAgICAgIDwvZm9ybT5cblxuICAgICAge2Vycm9yICYmIChcbiAgICAgICAgPGRpdiBzdHlsZT17eyBjb2xvcjogXCJyZWRcIiwgbWFyZ2luQm90dG9tOiBcIjIwcHhcIiB9fT5cbiAgICAgICAgICBFcnJvcjoge2Vycm9yLm1lc3NhZ2V9XG4gICAgICAgIDwvZGl2PlxuICAgICAgKX1cblxuICAgICAgPGRpdj5cbiAgICAgICAge2xvYWRpbmcgPyAoXG4gICAgICAgICAgPHA+TG9hZGluZyBhcnRpY2xlcy4uLjwvcD5cbiAgICAgICAgKSA6IGFydGljbGVzICYmIGFydGljbGVzLmxlbmd0aCA+IDAgPyAoXG4gICAgICAgICAgYXJ0aWNsZXMubWFwKChhcnRpY2xlKSA9PiAoXG4gICAgICAgICAgICA8QXJ0aWNsZUNhcmQga2V5PXthcnRpY2xlLmlkfSBhcnRpY2xlPXthcnRpY2xlfSAvPlxuICAgICAgICAgICkpXG4gICAgICAgICkgOiAoXG4gICAgICAgICAgPHA+XG4gICAgICAgICAgICBObyBhcnRpY2xlcyBmb3VuZC4gVHJ5IGEgZGlmZmVyZW50IHNlYXJjaCB0ZXJtIG9yIGFuIGVtcHR5IHNlYXJjaCB0b1xuICAgICAgICAgICAgc2VlIGFsbCBhcnRpY2xlcy5cbiAgICAgICAgICA8L3A+XG4gICAgICAgICl9XG4gICAgICA8L2Rpdj5cbiAgICA8L2Rpdj5cbiAgKTtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IFN1cHBvcnQ7XG4iXX0=