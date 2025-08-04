"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Switch_1 = __importDefault(require("@components/Switch"));
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("@config/backendConfig");
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
async function getServerSideProps({ req, res }) {
    // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
    // const SSR = withSSRContext({ req })
    // this runs on the backend, so we must call init on supertokens-node SDK
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
    let session;
    try {
        session = await session_1.default.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return [];
            },
        });
    }
    catch (err) {
        if (err.type === session_1.default.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        else if (err.type === session_1.default.Error.UNAUTHORISED) {
            // this will force the frontend to try and refresh which will fail
            // clearing all cookies and redirecting the user to the login screen.
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        throw err;
    }
    if (!session?.getUserId()) {
        return {
            redirect: {
                destination: '/User/Login/UserLogin',
                permanent: false,
            },
        };
    }
    return {
        props: {
            sub: session.getUserId(),
        }
    };
}
function EditCategoryStep1b(props) {
    const [copyModifiable, setCopyModifiable] = (0, react_1.useState)(props?.copyModifiable ?? false);
    const [isMessage1, setIsMessage1] = (0, react_1.useState)(false);
    const setParentCopyModifiable = props?.setParentCopyModifiable;
    const changeCopyModifiable = (value) => {
        setCopyModifiable(value);
        setParentCopyModifiable(value);
    };
    return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "flex-start", style: { width: '90%' }, pt: { phone: 'm', tablet: 's' }, minHeight: "70vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { flexDirection: "row", justifyContent: "flex-start", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", children: "Copy over time modifiable / time not modifiable value (make static) to any new events whose details are similar in context to this event for scheduling assists? " }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { flexDirection: "row", justifyContent: "flex-end", pt: { phone: 'm', tablet: 's' }, style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(Switch_1.default, { checked: copyModifiable, onValueChange: changeCopyModifiable, style: { marginBottom: 20 } }) })] }) }));
}
exports.default = EditCategoryStep1b;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiRWRpdENhdGVnb3J5U3RlcDFiLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiRWRpdENhdGVnb3J5U3RlcDFiLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWlCQSxnREFxQ0M7O0FBdERELGlDQUljO0FBRWQsZ0VBQXdDO0FBR3hDLGlFQUF3QztBQUN4QyxtRUFBMEM7QUFHMUMsd0VBQThDO0FBQzlDLHlEQUFxRDtBQUNyRCw4RUFBcUQ7QUFFOUMsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDaEcsMEZBQTBGO0lBQzFGLHNDQUFzQztJQUN0Qyx5RUFBeUU7SUFDekUsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQTtJQUNyQyxJQUFJLE9BQU8sQ0FBQTtJQUNYLElBQUksQ0FBQztRQUNELE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDekMsNkJBQTZCLEVBQUUsS0FBSztnQkFDaEMsT0FBTyxFQUFFLENBQUE7WUFDYixDQUFDO1NBQ0osQ0FBQyxDQUFBO0lBQ04sQ0FBQztJQUFDLE9BQU8sR0FBUSxFQUFFLENBQUM7UUFDaEIsSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLGlCQUFpQixFQUFFLENBQUM7WUFDL0MsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQzFELENBQUM7YUFBTSxJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDakQsa0VBQWtFO1lBQ2xFLHFFQUFxRTtZQUNyRSxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsZUFBZSxFQUFFLGVBQWUsRUFBRSxFQUFFLENBQUE7UUFDMUQsQ0FBQztRQUNELE1BQU0sR0FBRyxDQUFBO0lBQ2IsQ0FBQztJQUVELElBQUksQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLEVBQUUsQ0FBQztRQUN4QixPQUFPO1lBQ0gsUUFBUSxFQUFFO2dCQUNOLFdBQVcsRUFBRSx1QkFBdUI7Z0JBQ3BDLFNBQVMsRUFBRSxLQUFLO2FBQ25CO1NBQ0osQ0FBQTtJQUNMLENBQUM7SUFFRCxPQUFPO1FBQ0gsS0FBSyxFQUFFO1lBQ1AsR0FBRyxFQUFFLE9BQU8sQ0FBQyxTQUFTLEVBQUU7U0FDdkI7S0FDSixDQUFBO0FBQ0wsQ0FBQztBQU9ELFNBQVMsa0JBQWtCLENBQUMsS0FBWTtJQUNwQyxNQUFNLENBQUMsY0FBYyxFQUFFLGlCQUFpQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssRUFBRSxjQUFjLElBQUksS0FBSyxDQUFDLENBQUE7SUFDN0YsTUFBTSxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFFNUQsTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQUUsdUJBQXVCLENBQUE7SUFFOUQsTUFBTSxvQkFBb0IsR0FBRyxDQUFDLEtBQWMsRUFBRSxFQUFFO1FBQzVDLGlCQUFpQixDQUFDLEtBQUssQ0FBQyxDQUFBO1FBQ3hCLHVCQUF1QixDQUFDLEtBQUssQ0FBQyxDQUFBO0lBQ2xDLENBQUMsQ0FBQTtJQUVELE9BQU8sQ0FDSCx1QkFBQyxhQUFHLElBQUMsSUFBSSxFQUFFLENBQUMsRUFBRSxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxZQUM5RSx3QkFBQyxhQUFHLElBQUMsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsWUFBWSxFQUFDLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsRUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxTQUFTLEVBQUMsTUFBTSxhQUMzSCx1QkFBQyxhQUFHLElBQUMsYUFBYSxFQUFDLEtBQUssRUFBQyxjQUFjLEVBQUMsWUFBWSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxZQUM3Rix1QkFBQyxjQUFJLElBQUMsT0FBTyxFQUFDLGNBQWMsa0xBQXlLLEdBQ25NLEVBQ04sdUJBQUMsYUFBRyxJQUFDLGFBQWEsRUFBQyxLQUFLLEVBQUMsY0FBYyxFQUFDLFVBQVUsRUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLFlBQ3hHLHVCQUFDLGdCQUFPLElBQ0osT0FBTyxFQUFFLGNBQWMsRUFDdkIsYUFBYSxFQUFFLG9CQUFvQixFQUNuQyxLQUFLLEVBQUUsRUFBRSxZQUFZLEVBQUUsRUFBRSxFQUFFLEdBQzdCLEdBQ0EsSUFDSixHQUNKLENBQ1QsQ0FBQTtBQUVMLENBQUM7QUFFRCxrQkFBZSxrQkFBa0IsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwge1xuICB1c2VTdGF0ZSxcbiAgRGlzcGF0Y2gsXG4gIFNldFN0YXRlQWN0aW9uLFxufSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IFN3aXRjaDEgZnJvbSAnQGNvbXBvbmVudHMvU3dpdGNoJ1xuaW1wb3J0IHsgUHJlc3NhYmxlIH0gZnJvbSAncmVhY3QtbmF0aXZlJ1xuaW1wb3J0IFRleHRGaWVsZCBmcm9tICdAY29tcG9uZW50cy9UZXh0RmllbGQnXG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnXG5pbXBvcnQgVGV4dCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vVGV4dCdcbmltcG9ydCB7IERlZmF1bHRUaW1lQmxvY2tpbmdUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2F0ZWdvcnlUeXBlJ1xuaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHN1cGVydG9rZW5zTm9kZSBmcm9tICdzdXBlcnRva2Vucy1ub2RlJ1xuaW1wb3J0IHsgYmFja2VuZENvbmZpZyB9IGZyb20gJ0Bjb25maWcvYmFja2VuZENvbmZpZydcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRTZXJ2ZXJTaWRlUHJvcHMoeyByZXEsIHJlcyB9OiB7IHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlIH0pIHtcbiAgICAvLyBOb3RpY2UgaG93IHRoZSBzZXJ2ZXIgdXNlcyBgQVBJYCBmcm9tIGB3aXRoU1NSQ29udGV4dGAsIGluc3RlYWQgb2YgdGhlIHRvcC1sZXZlbCBgQVBJYC5cbiAgICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAgIC8vIHRoaXMgcnVucyBvbiB0aGUgYmFja2VuZCwgc28gd2UgbXVzdCBjYWxsIGluaXQgb24gc3VwZXJ0b2tlbnMtbm9kZSBTREtcbiAgICBzdXBlcnRva2Vuc05vZGUuaW5pdChiYWNrZW5kQ29uZmlnKCkpXG4gICAgbGV0IHNlc3Npb25cbiAgICB0cnkge1xuICAgICAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICAgICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICAgICAgICAgIHJldHVybiBbXVxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgICAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9IGVsc2UgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlVOQVVUSE9SSVNFRCkge1xuICAgICAgICAgICAgLy8gdGhpcyB3aWxsIGZvcmNlIHRoZSBmcm9udGVuZCB0byB0cnkgYW5kIHJlZnJlc2ggd2hpY2ggd2lsbCBmYWlsXG4gICAgICAgICAgICAvLyBjbGVhcmluZyBhbGwgY29va2llcyBhbmQgcmVkaXJlY3RpbmcgdGhlIHVzZXIgdG8gdGhlIGxvZ2luIHNjcmVlbi5cbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9XG4gICAgICAgIHRocm93IGVyclxuICAgIH1cblxuICAgIGlmICghc2Vzc2lvbj8uZ2V0VXNlcklkKCkpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgICAgICAgICAgZGVzdGluYXRpb246ICcvVXNlci9Mb2dpbi9Vc2VyTG9naW4nLFxuICAgICAgICAgICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgICAgcHJvcHM6IHtcbiAgICAgICAgc3ViOiBzZXNzaW9uLmdldFVzZXJJZCgpLFxuICAgICAgICB9XG4gICAgfVxufVxuXG50eXBlIFByb3BzID0ge1xuICAgIGNvcHlNb2RpZmlhYmxlOiBib29sZWFuLFxuICAgIHNldFBhcmVudENvcHlNb2RpZmlhYmxlOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxib29sZWFuPj4sXG59XG5cbmZ1bmN0aW9uIEVkaXRDYXRlZ29yeVN0ZXAxYihwcm9wczogUHJvcHMpIHtcbiAgICBjb25zdCBbY29weU1vZGlmaWFibGUsIHNldENvcHlNb2RpZmlhYmxlXSA9IHVzZVN0YXRlPGJvb2xlYW4+KHByb3BzPy5jb3B5TW9kaWZpYWJsZSA/PyBmYWxzZSlcbiAgICBjb25zdCBbaXNNZXNzYWdlMSwgc2V0SXNNZXNzYWdlMV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcblxuICAgIGNvbnN0IHNldFBhcmVudENvcHlNb2RpZmlhYmxlID0gcHJvcHM/LnNldFBhcmVudENvcHlNb2RpZmlhYmxlXG5cbiAgICBjb25zdCBjaGFuZ2VDb3B5TW9kaWZpYWJsZSA9ICh2YWx1ZTogYm9vbGVhbikgPT4ge1xuICAgICAgICBzZXRDb3B5TW9kaWZpYWJsZSh2YWx1ZSlcbiAgICAgICAgc2V0UGFyZW50Q29weU1vZGlmaWFibGUodmFsdWUpXG4gICAgfVxuXG4gICAgcmV0dXJuIChcbiAgICAgICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19PlxuICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJmbGV4LXN0YXJ0XCIgc3R5bGU9e3sgd2lkdGg6ICc5MCUnIH19IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ3MnIH19IG1pbkhlaWdodD1cIjcwdmhcIj5cbiAgICAgICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cImZsZXgtc3RhcnRcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fT5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiPkNvcHkgb3ZlciB0aW1lIG1vZGlmaWFibGUgLyB0aW1lIG5vdCBtb2RpZmlhYmxlIHZhbHVlIChtYWtlIHN0YXRpYykgdG8gYW55IG5ldyBldmVudHMgd2hvc2UgZGV0YWlscyBhcmUgc2ltaWxhciBpbiBjb250ZXh0IHRvIHRoaXMgZXZlbnQgZm9yIHNjaGVkdWxpbmcgYXNzaXN0cz8gPC9UZXh0PlxuICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwiZmxleC1lbmRcIiBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fSBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19PlxuICAgICAgICAgICAgICAgICAgICA8U3dpdGNoMVxuICAgICAgICAgICAgICAgICAgICAgICAgY2hlY2tlZD17Y29weU1vZGlmaWFibGV9XG4gICAgICAgICAgICAgICAgICAgICAgICBvblZhbHVlQ2hhbmdlPXtjaGFuZ2VDb3B5TW9kaWZpYWJsZX1cbiAgICAgICAgICAgICAgICAgICAgICAgIHN0eWxlPXt7IG1hcmdpbkJvdHRvbTogMjAgfX1cbiAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICA8L0JveD5cbiAgICApXG4gICAgXG59XG5cbmV4cG9ydCBkZWZhdWx0IEVkaXRDYXRlZ29yeVN0ZXAxYlxuIl19