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
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importStar(require("react"));
const dropboxSkills_1 = require("../../../../src/skills/dropboxSkills"); // Adjust path as needed
const DropboxManager = () => {
    const [userId] = (0, react_1.useState)("test-user-123"); // Placeholder
    const [connectionStatus, setConnectionStatus] = (0, react_1.useState)(null);
    const [isLoadingStatus, setIsLoadingStatus] = (0, react_1.useState)(true);
    const [files, setFiles] = (0, react_1.useState)([]);
    const [currentPath, setCurrentPath] = (0, react_1.useState)(''); // Root is an empty string
    const [isLoadingFiles, setIsLoadingFiles] = (0, react_1.useState)(false);
    const [pathHistory, setPathHistory] = (0, react_1.useState)([{ name: "Dropbox", path: '' }]);
    const [errorMessages, setErrorMessages] = (0, react_1.useState)({});
    const fetchConnectionStatus = (0, react_1.useCallback)(async () => {
        if (!userId)
            return;
        setIsLoadingStatus(true);
        setErrorMessages(prev => ({ ...prev, status: undefined }));
        try {
            const response = await (0, dropboxSkills_1.getDropboxConnectionStatus)(userId);
            if (response.ok && response.data) {
                setConnectionStatus(response.data);
            }
            else {
                setConnectionStatus({ isConnected: false, reason: response.error?.message || 'Failed to get status' });
                setErrorMessages(prev => ({ ...prev, status: response.error?.message || 'Failed to get status' }));
            }
        }
        catch (error) {
            setConnectionStatus({ isConnected: false, reason: 'Exception while fetching status' });
            setErrorMessages(prev => ({ ...prev, status: error.message || 'Exception while fetching status' }));
        }
        finally {
            setIsLoadingStatus(false);
        }
    }, [userId]);
    const handleConnectDropbox = () => {
        if (!userId) {
            setErrorMessages(prev => ({ ...prev, general: "User ID is missing." }));
            return;
        }
        // Redirect to the backend OAuth initiation URL for Dropbox
        window.location.href = `/api/auth/dropbox/initiate?user_id=${userId}`;
    };
    const handleDisconnectDropbox = (0, react_1.useCallback)(async () => {
        if (!userId)
            return;
        setErrorMessages(prev => ({ ...prev, general: undefined }));
        try {
            const response = await (0, dropboxSkills_1.disconnectDropbox)(userId);
            if (response.ok) {
                await fetchConnectionStatus();
                setFiles([]);
                setCurrentPath('');
                setPathHistory([{ name: "Dropbox", path: '' }]);
            }
            else {
                setErrorMessages(prev => ({ ...prev, general: response.error?.message || 'Failed to disconnect' }));
            }
        }
        catch (error) {
            setErrorMessages(prev => ({ ...prev, general: error.message || 'Exception during disconnect' }));
        }
    }, [userId, fetchConnectionStatus]);
    const fetchFiles = (0, react_1.useCallback)(async (path) => {
        if (!userId || !connectionStatus?.isConnected)
            return;
        setIsLoadingFiles(true);
        setFiles([]);
        setErrorMessages(prev => ({ ...prev, files: undefined }));
        try {
            const response = await (0, dropboxSkills_1.listDropboxFiles)(userId, path);
            if (response.ok && response.data?.entries) {
                setFiles(response.data.entries);
            }
            else {
                setErrorMessages(prev => ({ ...prev, files: response.error?.message || 'Failed to load files' }));
            }
        }
        catch (error) {
            setErrorMessages(prev => ({ ...prev, files: error.message || 'Exception while loading files' }));
        }
        finally {
            setIsLoadingFiles(false);
        }
    }, [userId, connectionStatus?.isConnected]);
    (0, react_1.useEffect)(() => {
        if (userId)
            fetchConnectionStatus();
    }, [userId, fetchConnectionStatus]);
    (0, react_1.useEffect)(() => {
        if (connectionStatus?.isConnected && userId) {
            fetchFiles(currentPath);
        }
        else if (!connectionStatus?.isConnected) {
            setFiles([]);
            setPathHistory([{ name: "Dropbox", path: '' }]);
        }
    }, [connectionStatus?.isConnected, currentPath, userId, fetchFiles]);
    const handleFileClick = (file) => {
        if (file.type === 'folder') {
            const newPathItem = { name: file.name, path: file.path_lower || '' };
            setPathHistory(prev => [...prev, newPathItem]);
            setCurrentPath(newPathItem.path);
        }
        else {
            console.log("Selected file:", file.name);
        }
    };
    const handleBreadcrumbClick = (index) => {
        const newPath = pathHistory.slice(0, index + 1);
        setPathHistory(newPath);
        setCurrentPath(pathHistory[index].path);
    };
    return ((0, jsx_runtime_1.jsxs)("div", { style: { fontFamily: 'Arial, sans-serif', padding: '20px', maxWidth: '800px', margin: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', marginTop: '20px' }, children: [(0, jsx_runtime_1.jsx)("h2", { style: { borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px' }, children: "Dropbox Management" }), errorMessages.general && (0, jsx_runtime_1.jsxs)("p", { style: { color: 'red' }, children: ["Error: ", errorMessages.general] }), (0, jsx_runtime_1.jsxs)("div", { style: { marginBottom: '20px' }, children: [(0, jsx_runtime_1.jsx)("h3", { children: "Connection Status" }), isLoadingStatus ? (0, jsx_runtime_1.jsx)("p", { children: "Loading status..." }) : connectionStatus?.isConnected ? ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsxs)("p", { style: { color: 'green' }, children: ["Connected as: ", connectionStatus.email || 'N/A'] }), (0, jsx_runtime_1.jsx)("button", { onClick: handleDisconnectDropbox, children: "Disconnect Dropbox" })] })) : ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("p", { style: { color: 'orange' }, children: "Not Connected." }), errorMessages.status && (0, jsx_runtime_1.jsx)("p", { style: { color: 'red' }, children: errorMessages.status }), (0, jsx_runtime_1.jsx)("button", { onClick: handleConnectDropbox, children: "Connect Dropbox" })] }))] }), connectionStatus?.isConnected && ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h3", { children: "Files and Folders" }), (0, jsx_runtime_1.jsx)("div", { children: pathHistory.map((p, index) => ((0, jsx_runtime_1.jsxs)(react_1.default.Fragment, { children: [(0, jsx_runtime_1.jsx)("button", { onClick: () => handleBreadcrumbClick(index), disabled: index === pathHistory.length - 1, children: p.name }), index < pathHistory.length - 1 && (0, jsx_runtime_1.jsx)("span", { children: " / " })] }, p.path))) }), errorMessages.files && (0, jsx_runtime_1.jsx)("p", { style: { color: 'red' }, children: errorMessages.files }), isLoadingFiles ? (0, jsx_runtime_1.jsx)("p", { children: "Loading files..." }) : ((0, jsx_runtime_1.jsx)("ul", { children: files.map(file => ((0, jsx_runtime_1.jsxs)("li", { onClick: () => handleFileClick(file), style: { cursor: file.type === 'folder' ? 'pointer' : 'default' }, children: [(0, jsx_runtime_1.jsx)("span", { children: file.type === 'folder' ? '📁' : '📄' }), " ", file.name] }, file.id))) }))] }))] }));
};
exports.default = DropboxManager;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiRHJvcGJveE1hbmFnZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJEcm9wYm94TWFuYWdlci50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBQUEsK0NBQWdFO0FBQ2hFLHdFQU04QyxDQUFDLHdCQUF3QjtBQVd2RSxNQUFNLGNBQWMsR0FBYSxHQUFHLEVBQUU7SUFDcEMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBZ0IsZUFBZSxDQUFDLENBQUMsQ0FBQyxjQUFjO0lBQ3pFLE1BQU0sQ0FBQyxnQkFBZ0IsRUFBRSxtQkFBbUIsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBcUMsSUFBSSxDQUFDLENBQUM7SUFDbkcsTUFBTSxDQUFDLGVBQWUsRUFBRSxrQkFBa0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVSxJQUFJLENBQUMsQ0FBQztJQUV0RSxNQUFNLENBQUMsS0FBSyxFQUFFLFFBQVEsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBaUIsRUFBRSxDQUFDLENBQUM7SUFDdkQsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsRUFBRSxDQUFDLENBQUMsQ0FBQywwQkFBMEI7SUFDdEYsTUFBTSxDQUFDLGNBQWMsRUFBRSxpQkFBaUIsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVSxLQUFLLENBQUMsQ0FBQztJQUNyRSxNQUFNLENBQUMsV0FBVyxFQUFFLGNBQWMsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBb0IsQ0FBQyxFQUFFLElBQUksRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQztJQUVuRyxNQUFNLENBQUMsYUFBYSxFQUFFLGdCQUFnQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUF3RCxFQUFFLENBQUMsQ0FBQztJQUU5RyxNQUFNLHFCQUFxQixHQUFHLElBQUEsbUJB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S0FBSyxJQUFJLDhCQUFHLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsWUFBRyxhQUFhLENBQUMsS0FBSyxHQUFLLEVBRTVFLGNBQWMsQ0FBQyxDQUFDLENBQUMsNkRBQXVCLENBQUMsQ0FBQyxDQUFDLENBQzFDLHlDQUNHLEtBQUssQ0FBQyxHQUFHLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FBQyxDQUNqQixnQ0FBa0IsT0FBTyxFQUFFLEdBQUcsRUFBRSxDQUFDLGVBQWUsQ0FBQyxJQUFJLENBQUMsRUFBRSxLQUFLLEVBQUUsRUFBRSxNQUFNLEVBQUUsSUFBSSxDQUFDLElBQUksS0FBSyxRQUFRLENBQUMsQ0FBQyxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsU0FBUyxFQUFFLGFBQ3ZILDJDQUFPLElBQUksQ0FBQyxJQUFJLEtBQUssUUFBUSxDQUFDLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLElBQUksR0FBUSxPQUFFLElBQUksQ0FBQyxJQUFJLEtBRHZELElBQUksQ0FBQyxFQUFFLENBRVgsQ0FDTixDQUFDLEdBQ0MsQ0FDTixJQUNHLENBQ1AsSUFDRyxDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHsgdXNlU3RhdGUsIHVzZUVmZmVjdCwgdXNlQ2FsbGJhY2sgfSBmcm9tICdyZWFjdCc7XG5pbXBvcnQge1xuICBnZXREcm9wYm94Q29ubmVjdGlvblN0YXR1cyxcbiAgZGlzY29ubmVjdERyb3Bib3gsXG4gIGxpc3REcm9wYm94RmlsZXMsXG4gIERyb3Bib3hDb25uZWN0aW9uU3RhdHVzSW5mbyxcbiAgRHJvcGJveEZpbGVcbn0gZnJvbSAnLi4vLi4vLi4vLi4vc3JjL3NraWxscy9kcm9wYm94U2tpbGxzJzsgLy8gQWRqdXN0IHBhdGggYXMgbmVlZGVkXG5cbmludGVyZmFjZSBGaWxlTGlzdEl0ZW0gZXh0ZW5kcyBEcm9wYm94RmlsZSB7XG4gIC8vIEFkZCBhbnkgVUktc3BlY2lmaWMgc3RhdGUgaWYgbmVlZGVkIGluIHRoZSBmdXR1cmUsIGUuZy4sIGZvciBpbmdlc3Rpb24gc3RhdHVzXG59XG5cbmludGVyZmFjZSBQYXRoSGlzdG9yeUl0ZW0ge1xuICBwYXRoOiBzdHJpbmc7XG4gIG5hbWU6IHN0cmluZztcbn1cblxuY29uc3QgRHJvcGJveE1hbmFnZXI6IFJlYWN0LkZDID0gKCkgPT4ge1xuICBjb25zdCBbdXNlcklkXSA9IHVzZVN0YXRlPHN0cmluZyB8IG51bGw+KFwidGVzdC11c2VyLTEyM1wiKTsgLy8gUGxhY2Vob2xkZXJcbiAgY29uc3QgW2Nvbm5lY3Rpb25TdGF0dXMsIHNldENvbm5lY3Rpb25TdGF0dXNdID0gdXNlU3RhdGU8RHJvcGJveENvbm5lY3Rpb25TdGF0dXNJbmZvIHwgbnVsbD4obnVsbCk7XG4gIGNvbnN0IFtpc0xvYWRpbmdTdGF0dXMsIHNldElzTG9hZGluZ1N0YXR1c10gPSB1c2VTdGF0ZTxib29sZWFuPih0cnVlKTtcblxuICBjb25zdCBbZmlsZXMsIHNldEZpbGVzXSA9IHVzZVN0YXRlPEZpbGVMaXN0SXRlbVtdPihbXSk7XG4gIGNvbnN0IFtjdXJyZW50UGF0aCwgc2V0Q3VycmVudFBhdGhdID0gdXNlU3RhdGU8c3RyaW5nPignJyk7IC8vIFJvb3QgaXMgYW4gZW1wdHkgc3RyaW5nXG4gIGNvbnN0IFtpc0xvYWRpbmdGaWxlcywgc2V0SXNMb2FkaW5nRmlsZXNdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpO1xuICBjb25zdCBbcGF0aEhpc3RvcnksIHNldFBhdGhIaXN0b3J5XSA9IHVzZVN0YXRlPFBhdGhIaXN0b3J5SXRlbVtdPihbeyBuYW1lOiBcIkRyb3Bib3hcIiwgcGF0aDogJycgfV0pO1xuXG4gIGNvbnN0IFtlcnJvck1lc3NhZ2VzLCBzZXRFcnJvck1lc3NhZ2VzXSA9IHVzZVN0YXRlPHsgZ2VuZXJhbD86IHN0cmluZzsgZmlsZXM/OiBzdHJpbmc7IHN0YXR1cz86IHN0cmluZyB9Pih7fSk7XG5cbiAgY29uc3QgZmV0Y2hDb25uZWN0aW9uU3RhdHVzID0gdXNlQ2FsbGJhY2soYXN5bmMgKCkgPT4ge1xuICAgIGlmICghdXNlcklkKSByZXR1cm47XG4gICAgc2V0SXNMb2FkaW5nU3RhdHVzKHRydWUpO1xuICAgIHNldEVycm9yTWVzc2FnZXMocHJldiA9PiAoeyAuLi5wcmV2LCBzdGF0dXM6IHVuZGVmaW5lZCB9KSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ2V0RHJvcGJveENvbm5lY3Rpb25TdGF0dXModXNlcklkKTtcbiAgICAgIGlmIChyZXNwb25zZS5vayAmJiByZXNwb25zZS5kYXRhKSB7XG4gICAgICAgIHNldENvbm5lY3Rpb25TdGF0dXMocmVzcG9uc2UuZGF0YSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzZXRDb25uZWN0aW9uU3RhdHVzKHsgaXNDb25uZWN0ZWQ6IGZhbHNlLCByZWFzb246IHJlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gZ2V0IHN0YXR1cycgfSk7XG4gICAgICAgIHNldEVycm9yTWVzc2FnZXMocHJldiA9PiAoeyAuLi5wcmV2LCBzdGF0dXM6IHJlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gZ2V0IHN0YXR1cycgfSkpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIHNldENvbm5lY3Rpb25TdGF0dXMoeyBpc0Nvbm5lY3RlZDogZmFsc2UsIHJlYXNvbjogJ0V4Y2VwdGlvbiB3aGlsZSBmZXRjaGluZyBzdGF0dXMnIH0pO1xuICAgICAgc2V0RXJyb3JNZXNzYWdlcyhwcmV2ID0+ICh7IC4uLnByZXYsIHN0YXR1czogZXJyb3IubWVzc2FnZSB8fCAnRXhjZXB0aW9uIHdoaWxlIGZldGNoaW5nIHN0YXR1cycgfSkpO1xuICAgIH0gZmluYWxseSB7XG4gICAgICBzZXRJc0xvYWRpbmdTdGF0dXMoZmFsc2UpO1xuICAgIH1cbiAgfSwgW3VzZXJJZF0pO1xuXG4gIGNvbnN0IGhhbmRsZUNvbm5lY3REcm9wYm94ID0gKCkgPT4ge1xuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBzZXRFcnJvck1lc3NhZ2VzKHByZXYgPT4gKHsgLi4ucHJldiwgZ2VuZXJhbDogXCJVc2VyIElEIGlzIG1pc3NpbmcuXCJ9KSk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIC8vIFJlZGlyZWN0IHRvIHRoZSBiYWNrZW5kIE9BdXRoIGluaXRpYXRpb24gVVJMIGZvciBEcm9wYm94XG4gICAgd2luZG93LmxvY2F0aW9uLmhyZWYgPSBgL2FwaS9hdXRoL2Ryb3Bib3gvaW5pdGlhdGU/dXNlcl9pZD0ke3VzZXJJZH1gO1xuICB9O1xuXG4gIGNvbnN0IGhhbmRsZURpc2Nvbm5lY3REcm9wYm94ID0gdXNlQ2FsbGJhY2soYXN5bmMgKCkgPT4ge1xuICAgIGlmICghdXNlcklkKSByZXR1cm47XG4gICAgc2V0RXJyb3JNZXNzYWdlcyhwcmV2ID0+ICh7IC4uLnByZXYsIGdlbmVyYWw6IHVuZGVmaW5lZCB9KSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZGlzY29ubmVjdERyb3Bib3godXNlcklkKTtcbiAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICBhd2FpdCBmZXRjaENvbm5lY3Rpb25TdGF0dXMoKTtcbiAgICAgICAgc2V0RmlsZXMoW10pO1xuICAgICAgICBzZXRDdXJyZW50UGF0aCgnJyk7XG4gICAgICAgIHNldFBhdGhIaXN0b3J5KFt7IG5hbWU6IFwiRHJvcGJveFwiLCBwYXRoOiAnJyB9XSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzZXRFcnJvck1lc3NhZ2VzKHByZXYgPT4gKHsgLi4ucHJldiwgZ2VuZXJhbDogcmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBkaXNjb25uZWN0JyB9KSk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgc2V0RXJyb3JNZXNzYWdlcyhwcmV2ID0+ICh7IC4uLnByZXYsIGdlbmVyYWw6IGVycm9yLm1lc3NhZ2UgfHwgJ0V4Y2VwdGlvbiBkdXJpbmcgZGlzY29ubmVjdCcgfSkpO1xuICAgIH1cbiAgfSwgW3VzZXJJZCwgZmV0Y2hDb25uZWN0aW9uU3RhdHVzXSk7XG5cbiAgY29uc3QgZmV0Y2hGaWxlcyA9IHVzZUNhbGxiYWNrKGFzeW5jIChwYXRoOiBzdHJpbmcpID0+IHtcbiAgICBpZiAoIXVzZXJJZCB8fCAhY29ubmVjdGlvblN0YXR1cz8uaXNDb25uZWN0ZWQpIHJldHVybjtcblxuICAgIHNldElzTG9hZGluZ0ZpbGVzKHRydWUpO1xuICAgIHNldEZpbGVzKFtdKTtcbiAgICBzZXRFcnJvck1lc3NhZ2VzKHByZXYgPT4gKHsgLi4ucHJldiwgZmlsZXM6IHVuZGVmaW5lZCB9KSk7XG5cbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBsaXN0RHJvcGJveEZpbGVzKHVzZXJJZCwgcGF0aCk7XG4gICAgICBpZiAocmVzcG9uc2Uub2sgJiYgcmVzcG9uc2UuZGF0YT8uZW50cmllcykge1xuICAgICAgICBzZXRGaWxlcyhyZXNwb25zZS5kYXRhLmVudHJpZXMpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgc2V0RXJyb3JNZXNzYWdlcyhwcmV2ID0+ICh7IC4uLnByZXYsIGZpbGVzOiByZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fCAnRmFpbGVkIHRvIGxvYWQgZmlsZXMnIH0pKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBzZXRFcnJvck1lc3NhZ2VzKHByZXYgPT4gKHsgLi4ucHJldiwgZmlsZXM6IGVycm9yLm1lc3NhZ2UgfHwgJ0V4Y2VwdGlvbiB3aGlsZSBsb2FkaW5nIGZpbGVzJyB9KSk7XG4gICAgfSBmaW5hbGx5IHtcbiAgICAgIHNldElzTG9hZGluZ0ZpbGVzKGZhbHNlKTtcbiAgICB9XG4gIH0sIFt1c2VySWQsIGNvbm5lY3Rpb25TdGF0dXM/LmlzQ29ubmVjdGVkXSk7XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAodXNlcklkKSBmZXRjaENvbm5lY3Rpb25TdGF0dXMoKTtcbiAgfSwgW3VzZXJJZCwgZmV0Y2hDb25uZWN0aW9uU3RhdHVzXSk7XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBpZiAoY29ubmVjdGlvblN0YXR1cz8uaXNDb25uZWN0ZWQgJiYgdXNlcklkKSB7XG4gICAgICBmZXRjaEZpbGVzKGN1cnJlbnRQYXRoKTtcbiAgICB9IGVsc2UgaWYgKCFjb25uZWN0aW9uU3RhdHVzPy5pc0Nvbm5lY3RlZCkge1xuICAgICAgc2V0RmlsZXMoW10pO1xuICAgICAgc2V0UGF0aEhpc3RvcnkoW3sgbmFtZTogXCJEcm9wYm94XCIsIHBhdGg6ICcnIH1dKTtcbiAgICB9XG4gIH0sIFtjb25uZWN0aW9uU3RhdHVzPy5pc0Nvbm5lY3RlZCwgY3VycmVudFBhdGgsIHVzZXJJZCwgZmV0Y2hGaWxlc10pO1xuXG4gIGNvbnN0IGhhbmRsZUZpbGVDbGljayA9IChmaWxlOiBGaWxlTGlzdEl0ZW0pID0+IHtcbiAgICBpZiAoZmlsZS50eXBlID09PSAnZm9sZGVyJykge1xuICAgICAgY29uc3QgbmV3UGF0aEl0ZW0gPSB7IG5hbWU6IGZpbGUubmFtZSwgcGF0aDogZmlsZS5wYXRoX2xvd2VyIHx8ICcnIH07XG4gICAgICBzZXRQYXRoSGlzdG9yeShwcmV2ID0+IFsuLi5wcmV2LCBuZXdQYXRoSXRlbV0pO1xuICAgICAgc2V0Q3VycmVudFBhdGgobmV3UGF0aEl0ZW0ucGF0aCk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUubG9nKFwiU2VsZWN0ZWQgZmlsZTpcIiwgZmlsZS5uYW1lKTtcbiAgICB9XG4gIH07XG5cbiAgY29uc3QgaGFuZGxlQnJlYWRjcnVtYkNsaWNrID0gKGluZGV4OiBudW1iZXIpID0+IHtcbiAgICBjb25zdCBuZXdQYXRoID0gcGF0aEhpc3Rvcnkuc2xpY2UoMCwgaW5kZXggKyAxKTtcbiAgICBzZXRQYXRoSGlzdG9yeShuZXdQYXRoKTtcbiAgICBzZXRDdXJyZW50UGF0aChwYXRoSGlzdG9yeVtpbmRleF0ucGF0aCk7XG4gIH07XG5cbiAgcmV0dXJuIChcbiAgICA8ZGl2IHN0eWxlPXt7IGZvbnRGYW1pbHk6ICdBcmlhbCwgc2Fucy1zZXJpZicsIHBhZGRpbmc6ICcyMHB4JywgbWF4V2lkdGg6ICc4MDBweCcsIG1hcmdpbjogJ2F1dG8nLCBib3JkZXI6ICcxcHggc29saWQgI2UwZTBlMCcsIGJvcmRlclJhZGl1czogJzhweCcsIGJveFNoYWRvdzogJzAgMnB4IDRweCByZ2JhKDAsMCwwLDAuMSknLCBtYXJnaW5Ub3A6ICcyMHB4JyB9fT5cbiAgICAgIDxoMiBzdHlsZT17eyBib3JkZXJCb3R0b206ICcxcHggc29saWQgI2VlZScsIHBhZGRpbmdCb3R0b206ICcxMHB4JywgbWFyZ2luQm90dG9tOiAnMjBweCcgfX0+RHJvcGJveCBNYW5hZ2VtZW50PC9oMj5cblxuICAgICAge2Vycm9yTWVzc2FnZXMuZ2VuZXJhbCAmJiA8cCBzdHlsZT17eyBjb2xvcjogJ3JlZCcgfX0+RXJyb3I6IHtlcnJvck1lc3NhZ2VzLmdlbmVyYWx9PC9wPn1cblxuICAgICAgPGRpdiBzdHlsZT17eyBtYXJnaW5Cb3R0b206ICcyMHB4JyB9fT5cbiAgICAgICAgPGgzPkNvbm5lY3Rpb24gU3RhdHVzPC9oMz5cbiAgICAgICAge2lzTG9hZGluZ1N0YXR1cyA/IDxwPkxvYWRpbmcgc3RhdHVzLi4uPC9wPiA6IGNvbm5lY3Rpb25TdGF0dXM/LmlzQ29ubmVjdGVkID8gKFxuICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICA8cCBzdHlsZT17eyBjb2xvcjogJ2dyZWVuJyB9fT5Db25uZWN0ZWQgYXM6IHtjb25uZWN0aW9uU3RhdHVzLmVtYWlsIHx8ICdOL0EnfTwvcD5cbiAgICAgICAgICAgIDxidXR0b24gb25DbGljaz17aGFuZGxlRGlzY29ubmVjdERyb3Bib3h9PkRpc2Nvbm5lY3QgRHJvcGJveDwvYnV0dG9uPlxuICAgICAgICAgIDwvZGl2PlxuICAgICAgICApIDogKFxuICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICA8cCBzdHlsZT17eyBjb2xvcjogJ29yYW5nZScgfX0+Tm90IENvbm5lY3RlZC48L3A+XG4gICAgICAgICAgICB7ZXJyb3JNZXNzYWdlcy5zdGF0dXMgJiYgPHAgc3R5bGU9e3sgY29sb3I6ICdyZWQnIH19PntlcnJvck1lc3NhZ2VzLnN0YXR1c308L3A+fVxuICAgICAgICAgICAgPGJ1dHRvbiBvbkNsaWNrPXtoYW5kbGVDb25uZWN0RHJvcGJveH0+Q29ubmVjdCBEcm9wYm94PC9idXR0b24+XG4gICAgICAgICAgPC9kaXY+XG4gICAgICAgICl9XG4gICAgICA8L2Rpdj5cblxuICAgICAge2Nvbm5lY3Rpb25TdGF0dXM/LmlzQ29ubmVjdGVkICYmIChcbiAgICAgICAgPGRpdj5cbiAgICAgICAgICA8aDM+RmlsZXMgYW5kIEZvbGRlcnM8L2gzPlxuICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICB7cGF0aEhpc3RvcnkubWFwKChwLCBpbmRleCkgPT4gKFxuICAgICAgICAgICAgICA8UmVhY3QuRnJhZ21lbnQga2V5PXtwLnBhdGh9PlxuICAgICAgICAgICAgICAgIDxidXR0b24gb25DbGljaz17KCkgPT4gaGFuZGxlQnJlYWRjcnVtYkNsaWNrKGluZGV4KX0gZGlzYWJsZWQ9e2luZGV4ID09PSBwYXRoSGlzdG9yeS5sZW5ndGggLSAxfT5cbiAgICAgICAgICAgICAgICAgIHtwLm5hbWV9XG4gICAgICAgICAgICAgICAgPC9idXR0b24+XG4gICAgICAgICAgICAgICAge2luZGV4IDwgcGF0aEhpc3RvcnkubGVuZ3RoIC0gMSAmJiA8c3Bhbj4gLyA8L3NwYW4+fVxuICAgICAgICAgICAgICA8L1JlYWN0LkZyYWdtZW50PlxuICAgICAgICAgICAgKSl9XG4gICAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgICB7ZXJyb3JNZXNzYWdlcy5maWxlcyAmJiA8cCBzdHlsZT17eyBjb2xvcjogJ3JlZCcgfX0+e2Vycm9yTWVzc2FnZXMuZmlsZXN9PC9wPn1cblxuICAgICAgICAgIHtpc0xvYWRpbmdGaWxlcyA/IDxwPkxvYWRpbmcgZmlsZXMuLi48L3A+IDogKFxuICAgICAgICAgICAgPHVsPlxuICAgICAgICAgICAgICB7ZmlsZXMubWFwKGZpbGUgPT4gKFxuICAgICAgICAgICAgICAgIDxsaSBrZXk9e2ZpbGUuaWR9IG9uQ2xpY2s9eygpID0+IGhhbmRsZUZpbGVDbGljayhmaWxlKX0gc3R5bGU9e3sgY3Vyc29yOiBmaWxlLnR5cGUgPT09ICdmb2xkZXInID8gJ3BvaW50ZXInIDogJ2RlZmF1bHQnIH19PlxuICAgICAgICAgICAgICAgICAgPHNwYW4+e2ZpbGUudHlwZSA9PT0gJ2ZvbGRlcicgPyAn8J+TgScgOiAn8J+ThCd9PC9zcGFuPiB7ZmlsZS5uYW1lfVxuICAgICAgICAgICAgICAgIDwvbGk+XG4gICAgICAgICAgICAgICkpfVxuICAgICAgICAgICAgPC91bD5cbiAgICAgICAgICApfVxuICAgICAgICA8L2Rpdj5cbiAgICAgICl9XG4gICAgPC9kaXY+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCBEcm9wYm94TWFuYWdlcjtcbiJdfQ==