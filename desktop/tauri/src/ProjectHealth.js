"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const tauri_1 = require("@tauri-apps/api/tauri");
function ProjectHealth() {
    const [healthScore, setHealthScore] = (0, react_1.useState)(null);
    const [isLoading, setIsLoading] = (0, react_1.useState)(false);
    const [error, setError] = (0, react_1.useState)('');
    const fetchHealthScore = async () => {
        setIsLoading(true);
        setError('');
        try {
            const score = await (0, tauri_1.invoke)('get_project_health_score');
            setHealthScore(score);
        }
        catch (err) {
            setError(err.toString());
        }
        finally {
            setIsLoading(false);
        }
    };
    (0, react_1.useEffect)(() => {
        fetchHealthScore();
    }, []);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "project-health-container", children: [(0, jsx_runtime_1.jsx)("h2", { children: "Project Health Score" }), isLoading && (0, jsx_runtime_1.jsx)("p", { children: "Loading..." }), error && (0, jsx_runtime_1.jsx)("p", { className: "error", children: error }), healthScore !== null && ((0, jsx_runtime_1.jsx)("div", { className: "health-score", children: (0, jsx_runtime_1.jsx)("p", { children: healthScore }) }))] }));
}
exports.default = ProjectHealth;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUHJvamVjdEhlYWx0aC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlByb2plY3RIZWFsdGgudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUE0QztBQUM1QyxpREFBK0M7QUFFL0MsU0FBUyxhQUFhO0lBQ3BCLE1BQU0sQ0FBQyxXQUFXLEVBQUUsY0FBYyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFnQixJQUFJLENBQUMsQ0FBQztJQUNwRSxNQUFNLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxLQUFLLENBQUMsQ0FBQztJQUNsRCxNQUFNLENBQUMsS0FBSyxFQUFFLFFBQVEsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxFQUFFLENBQUMsQ0FBQztJQUV2QyxNQUFNLGdCQUFnQixHQUFHLEtBQUssSUFBSSxFQUFFO1FBQ2xDLFlBQVksQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNuQixRQUFRLENBQUMsRUFBRSxDQUFDLENBQUM7UUFDYixJQUFJLENBQUM7WUFDSCxNQUFNLEtBQUssR0FBRyxNQUFNLElBQUEsY0FBTSxFQUFDLDBCQUEwQixDQUFDLENBQUM7WUFDdkQsY0FBYyxDQUFDLEtBQWUsQ0FBQyxDQUFDO1FBQ2xDLENBQUM7UUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1lBQ2xCLFFBQVEsQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLENBQUMsQ0FBQztRQUMzQixDQUFDO2dCQUFTLENBQUM7WUFDVCxZQUFZLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDdEIsQ0FBQztJQUNILENBQUMsQ0FBQztJQUVGLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixnQkFBZ0IsRUFBRSxDQUFDO0lBQ3JCLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztJQUVQLE9BQU8sQ0FDTCxpQ0FBSyxTQUFTLEVBQUMsMEJBQTBCLGFBQ3ZDLGtFQUE2QixFQUM1QixTQUFTLElBQUksdURBQWlCLEVBQzlCLEtBQUssSUFBSSw4QkFBRyxTQUFTLEVBQUMsT0FBTyxZQUFFLEtBQUssR0FBSyxFQUN6QyxXQUFXLEtBQUssSUFBSSxJQUFJLENBQ3ZCLGdDQUFLLFNBQVMsRUFBQyxjQUFjLFlBQzNCLHdDQUFJLFdBQVcsR0FBSyxHQUNoQixDQUNQLElBQ0csQ0FDUCxDQUFDO0FBQ0osQ0FBQztBQUVELGtCQUFlLGFBQWEsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVzZVN0YXRlLCB1c2VFZmZlY3QgfSBmcm9tICdyZWFjdCc7XG5pbXBvcnQgeyBpbnZva2UgfSBmcm9tICdAdGF1cmktYXBwcy9hcGkvdGF1cmknO1xuXG5mdW5jdGlvbiBQcm9qZWN0SGVhbHRoKCkge1xuICBjb25zdCBbaGVhbHRoU2NvcmUsIHNldEhlYWx0aFNjb3JlXSA9IHVzZVN0YXRlPG51bWJlciB8IG51bGw+KG51bGwpO1xuICBjb25zdCBbaXNMb2FkaW5nLCBzZXRJc0xvYWRpbmddID0gdXNlU3RhdGUoZmFsc2UpO1xuICBjb25zdCBbZXJyb3IsIHNldEVycm9yXSA9IHVzZVN0YXRlKCcnKTtcblxuICBjb25zdCBmZXRjaEhlYWx0aFNjb3JlID0gYXN5bmMgKCkgPT4ge1xuICAgIHNldElzTG9hZGluZyh0cnVlKTtcbiAgICBzZXRFcnJvcignJyk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHNjb3JlID0gYXdhaXQgaW52b2tlKCdnZXRfcHJvamVjdF9oZWFsdGhfc2NvcmUnKTtcbiAgICAgIHNldEhlYWx0aFNjb3JlKHNjb3JlIGFzIG51bWJlcik7XG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgIHNldEVycm9yKGVyci50b1N0cmluZygpKTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgc2V0SXNMb2FkaW5nKGZhbHNlKTtcbiAgICB9XG4gIH07XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBmZXRjaEhlYWx0aFNjb3JlKCk7XG4gIH0sIFtdKTtcblxuICByZXR1cm4gKFxuICAgIDxkaXYgY2xhc3NOYW1lPVwicHJvamVjdC1oZWFsdGgtY29udGFpbmVyXCI+XG4gICAgICA8aDI+UHJvamVjdCBIZWFsdGggU2NvcmU8L2gyPlxuICAgICAge2lzTG9hZGluZyAmJiA8cD5Mb2FkaW5nLi4uPC9wPn1cbiAgICAgIHtlcnJvciAmJiA8cCBjbGFzc05hbWU9XCJlcnJvclwiPntlcnJvcn08L3A+fVxuICAgICAge2hlYWx0aFNjb3JlICE9PSBudWxsICYmIChcbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJoZWFsdGgtc2NvcmVcIj5cbiAgICAgICAgICA8cD57aGVhbHRoU2NvcmV9PC9wPlxuICAgICAgICA8L2Rpdj5cbiAgICAgICl9XG4gICAgPC9kaXY+XG4gICk7XG59XG5cbmV4cG9ydCBkZWZhdWx0IFByb2plY3RIZWFsdGg7XG4iXX0=