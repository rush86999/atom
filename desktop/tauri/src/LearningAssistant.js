"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const tauri_1 = require("@tauri-apps/api/tauri");
function LearningAssistant() {
    const [notionDatabaseId, setNotionDatabaseId] = (0, react_1.useState)('');
    const [isLoading, setIsLoading] = (0, react_1.useState)(false);
    const [message, setMessage] = (0, react_1.useState)('');
    const [error, setError] = (0, react_1.useState)('');
    const handleGeneratePlan = async () => {
        setIsLoading(true);
        setMessage('');
        setError('');
        try {
            await (0, tauri_1.invoke)('generate_learning_plan', {
                notionDatabaseId,
            });
            setMessage('Learning plan generated!');
        }
        catch (err) {
            setError(err.toString());
        }
        finally {
            setIsLoading(false);
        }
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "learning-assistant-container", children: [(0, jsx_runtime_1.jsx)("h2", { children: "Personalized Learning Assistant" }), isLoading && (0, jsx_runtime_1.jsx)("p", { children: "Loading..." }), message && (0, jsx_runtime_1.jsx)("p", { className: "success", children: message }), error && (0, jsx_runtime_1.jsx)("p", { className: "error", children: error }), (0, jsx_runtime_1.jsxs)("div", { className: "setting", children: [(0, jsx_runtime_1.jsx)("label", { children: "Notion Database ID" }), (0, jsx_runtime_1.jsx)("input", { type: "text", value: notionDatabaseId, onChange: (e) => setNotionDatabaseId(e.target.value), placeholder: "Enter Notion Database ID for the report" })] }), (0, jsx_runtime_1.jsx)("button", { onClick: handleGeneratePlan, children: "Generate Learning Plan" })] }));
}
exports.default = LearningAssistant;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiTGVhcm5pbmdBc3Npc3RhbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJMZWFybmluZ0Fzc2lzdGFudC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsaUNBQWlDO0FBQ2pDLGlEQUErQztBQUUvQyxTQUFTLGlCQUFpQjtJQUN4QixNQUFNLENBQUMsZ0JBQWdCLEVBQUUsbUJBQW1CLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDN0QsTUFBTSxDQUFDLFNBQVMsRUFBRSxZQUFZLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsS0FBSyxDQUFDLENBQUM7SUFDbEQsTUFBTSxDQUFDLE9BQU8sRUFBRSxVQUFVLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDM0MsTUFBTSxDQUFDLEtBQUssRUFBRSxRQUFRLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFFdkMsTUFBTSxrQkFBa0IsR0FBRyxLQUFLLElBQUksRUFBRTtRQUNwQyxZQUFZLENBQUMsSUFBSSxDQUFDLENBQUM7UUFDbkIsVUFBVSxDQUFDLEVBQUUsQ0FBQyxDQUFDO1FBQ2YsUUFBUSxDQUFDLEVBQUUsQ0FBQyxDQUFDO1FBQ2IsSUFBSSxDQUFDO1lBQ0gsTUFBTSxJQUFBLGNBQU0sRUFBQyx3QkFBd0IsRUFBRTtnQkFDckMsZ0JBQWdCO2FBQ2pCLENBQUMsQ0FBQztZQUNILFVBQVUsQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO1FBQ3pDLENBQUM7UUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1lBQ2xCLFFBQVEsQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLENBQUMsQ0FBQztRQUMzQixDQUFDO2dCQUFTLENBQUM7WUFDVCxZQUFZLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDdEIsQ0FBQztJQUNILENBQUMsQ0FBQztJQUVGLE9BQU8sQ0FDTCxpQ0FBSyxTQUFTLEVBQUMsOEJBQThCLGFBQzNDLDZFQUF3QyxFQUN2QyxTQUFTLElBQUksdURBQWlCLEVBQzlCLE9BQU8sSUFBSSw4QkFBRyxTQUFTLEVBQUMsU0FBUyxZQUFFLE9BQU8sR0FBSyxFQUMvQyxLQUFLLElBQUksOEJBQUcsU0FBUyxFQUFDLE9BQU8sWUFBRSxLQUFLLEdBQUssRUFDMUMsaUNBQUssU0FBUyxFQUFDLFNBQVMsYUFDdEIsbUVBQWlDLEVBQ2pDLGtDQUNFLElBQUksRUFBQyxNQUFNLEVBQ1gsS0FBSyxFQUFFLGdCQUFnQixFQUN2QixRQUFRLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLG1CQUFtQixDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLEVBQ3BELFdBQVcsRUFBQyx5Q0FBeUMsR0FDckQsSUFDRSxFQUNOLG1DQUFRLE9BQU8sRUFBRSxrQkFBa0IsdUNBQWlDLElBQ2hFLENBQ1AsQ0FBQztBQUNKLENBQUM7QUFFRCxrQkFBZSxpQkFBaUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVzZVN0YXRlIH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IHsgaW52b2tlIH0gZnJvbSAnQHRhdXJpLWFwcHMvYXBpL3RhdXJpJztcblxuZnVuY3Rpb24gTGVhcm5pbmdBc3Npc3RhbnQoKSB7XG4gIGNvbnN0IFtub3Rpb25EYXRhYmFzZUlkLCBzZXROb3Rpb25EYXRhYmFzZUlkXSA9IHVzZVN0YXRlKCcnKTtcbiAgY29uc3QgW2lzTG9hZGluZywgc2V0SXNMb2FkaW5nXSA9IHVzZVN0YXRlKGZhbHNlKTtcbiAgY29uc3QgW21lc3NhZ2UsIHNldE1lc3NhZ2VdID0gdXNlU3RhdGUoJycpO1xuICBjb25zdCBbZXJyb3IsIHNldEVycm9yXSA9IHVzZVN0YXRlKCcnKTtcblxuICBjb25zdCBoYW5kbGVHZW5lcmF0ZVBsYW4gPSBhc3luYyAoKSA9PiB7XG4gICAgc2V0SXNMb2FkaW5nKHRydWUpO1xuICAgIHNldE1lc3NhZ2UoJycpO1xuICAgIHNldEVycm9yKCcnKTtcbiAgICB0cnkge1xuICAgICAgYXdhaXQgaW52b2tlKCdnZW5lcmF0ZV9sZWFybmluZ19wbGFuJywge1xuICAgICAgICBub3Rpb25EYXRhYmFzZUlkLFxuICAgICAgfSk7XG4gICAgICBzZXRNZXNzYWdlKCdMZWFybmluZyBwbGFuIGdlbmVyYXRlZCEnKTtcbiAgICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgICAgc2V0RXJyb3IoZXJyLnRvU3RyaW5nKCkpO1xuICAgIH0gZmluYWxseSB7XG4gICAgICBzZXRJc0xvYWRpbmcoZmFsc2UpO1xuICAgIH1cbiAgfTtcblxuICByZXR1cm4gKFxuICAgIDxkaXYgY2xhc3NOYW1lPVwibGVhcm5pbmctYXNzaXN0YW50LWNvbnRhaW5lclwiPlxuICAgICAgPGgyPlBlcnNvbmFsaXplZCBMZWFybmluZyBBc3Npc3RhbnQ8L2gyPlxuICAgICAge2lzTG9hZGluZyAmJiA8cD5Mb2FkaW5nLi4uPC9wPn1cbiAgICAgIHttZXNzYWdlICYmIDxwIGNsYXNzTmFtZT1cInN1Y2Nlc3NcIj57bWVzc2FnZX08L3A+fVxuICAgICAge2Vycm9yICYmIDxwIGNsYXNzTmFtZT1cImVycm9yXCI+e2Vycm9yfTwvcD59XG4gICAgICA8ZGl2IGNsYXNzTmFtZT1cInNldHRpbmdcIj5cbiAgICAgICAgPGxhYmVsPk5vdGlvbiBEYXRhYmFzZSBJRDwvbGFiZWw+XG4gICAgICAgIDxpbnB1dFxuICAgICAgICAgIHR5cGU9XCJ0ZXh0XCJcbiAgICAgICAgICB2YWx1ZT17bm90aW9uRGF0YWJhc2VJZH1cbiAgICAgICAgICBvbkNoYW5nZT17KGUpID0+IHNldE5vdGlvbkRhdGFiYXNlSWQoZS50YXJnZXQudmFsdWUpfVxuICAgICAgICAgIHBsYWNlaG9sZGVyPVwiRW50ZXIgTm90aW9uIERhdGFiYXNlIElEIGZvciB0aGUgcmVwb3J0XCJcbiAgICAgICAgLz5cbiAgICAgIDwvZGl2PlxuICAgICAgPGJ1dHRvbiBvbkNsaWNrPXtoYW5kbGVHZW5lcmF0ZVBsYW59PkdlbmVyYXRlIExlYXJuaW5nIFBsYW48L2J1dHRvbj5cbiAgICA8L2Rpdj5cbiAgKTtcbn1cblxuZXhwb3J0IGRlZmF1bHQgTGVhcm5pbmdBc3Npc3RhbnQ7XG4iXX0=