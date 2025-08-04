"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const config_json_1 = __importDefault(require("@config/config.json"));
const Baseof_1 = __importDefault(require("@layouts/Baseof"));
const Dashboard_1 = __importDefault(require("@components/Dashboard"));
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../config/backendConfig");
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
const Home = () => {
    const { title } = config_json_1.default.site;
    return ((0, jsx_runtime_1.jsx)(Baseof_1.default, { title: title, meta_title: undefined, description: undefined, image: undefined, noindex: undefined, canonical: undefined, children: (0, jsx_runtime_1.jsx)(Dashboard_1.default, {}) }));
};
exports.default = Home;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFlQSxnREFxQ0M7O0FBbkRELHNFQUF5QztBQUN6Qyw2REFBbUM7QUFPbkMsc0VBQThDO0FBRTlDLHdFQUE4QztBQUM5QywyREFBdUQ7QUFDdkQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2xHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQzNDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2xDLE9BQU8sRUFBRSxDQUFBO1lBQ1gsQ0FBQztTQUNGLENBQUMsQ0FBQTtJQUNKLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2xCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2pELE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUN4RCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ25ELGtFQUFrRTtZQUNsRSxxRUFBcUU7WUFDckUsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQ3hELENBQUM7UUFDRCxNQUFNLEdBQUcsQ0FBQTtJQUNYLENBQUM7SUFFRCxJQUFJLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxFQUFFLENBQUM7UUFDMUIsT0FBTztZQUNMLFFBQVEsRUFBRTtnQkFDUixXQUFXLEVBQUUsdUJBQXVCO2dCQUNwQyxTQUFTLEVBQUUsS0FBSzthQUNqQjtTQUNGLENBQUE7SUFDSCxDQUFDO0lBRUQsT0FBTztRQUNMLEtBQUssRUFBRTtZQUNMLEdBQUcsRUFBRSxPQUFPLENBQUMsU0FBUyxFQUFFO1NBQ3pCO0tBQ0YsQ0FBQTtBQUNILENBQUM7QUFHRCxNQUFNLElBQUksR0FBRyxHQUFHLEVBQUU7SUFFaEIsTUFBTSxFQUFFLEtBQUssRUFBRSxHQUFHLHFCQUFNLENBQUMsSUFBSSxDQUFDO0lBRTlCLE9BQU8sQ0FDTCx1QkFBQyxnQkFBSSxJQUFDLEtBQUssRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLFNBQVMsRUFBRSxXQUFXLEVBQUUsU0FBUyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsT0FBTyxFQUFFLFNBQVMsRUFBRSxTQUFTLEVBQUUsU0FBUyxZQUMzSCx1QkFBQyxtQkFBUyxLQUFHLEdBQ1IsQ0FDUixDQUFBO0FBQ0gsQ0FBQyxDQUFBO0FBRUQsa0JBQWUsSUFBSSxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiXG5pbXBvcnQgY29uZmlnIGZyb20gXCJAY29uZmlnL2NvbmZpZy5qc29uXCI7XG5pbXBvcnQgQmFzZSBmcm9tIFwiQGxheW91dHMvQmFzZW9mXCI7XG5cbmltcG9ydCB7IFRhYiwgVGFiTGlzdCwgVGFiUGFuZWwsIFRhYlBhbmVscywgVGFicyB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnO1xuaW1wb3J0IFVzZXJWaWV3Q2FsZW5kYXIgZnJvbSAnQHBhZ2VzL0NhbGVuZGFyL1VzZXJWaWV3Q2FsZW5kYXJXZWInXG5pbXBvcnQgVXNlclRhc2sgZnJvbSAnQHBhZ2VzL1Byb2dyZXNzL1RvZG8vVXNlclRhc2snXG5pbXBvcnQgVXNlclZpZXdDaGF0IGZyb20gJ0BwYWdlcy9DYWxlbmRhci9DaGF0L1VzZXJWaWV3Q2hhdCdcbmltcG9ydCBTbWFydFNlYXJjaCBmcm9tICdAY29tcG9uZW50cy9TbWFydFNlYXJjaCc7XG5pbXBvcnQgRGFzaGJvYXJkIGZyb20gJ0Bjb21wb25lbnRzL0Rhc2hib2FyZCc7XG5pbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgc3VwZXJ0b2tlbnNOb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUnXG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gIC8vIE5vdGljZSBob3cgdGhlIHNlcnZlciB1c2VzIGBBUElgIGZyb20gYHdpdGhTU1JDb250ZXh0YCwgaW5zdGVhZCBvZiB0aGUgdG9wLWxldmVsIGBBUElgLlxuICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gIHN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSlcbiAgbGV0IHNlc3Npb25cbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gW11cbiAgICAgIH0sXG4gICAgfSlcbiAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH0gZWxzZSBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICAvLyB0aGlzIHdpbGwgZm9yY2UgdGhlIGZyb250ZW5kIHRvIHRyeSBhbmQgcmVmcmVzaCB3aGljaCB3aWxsIGZhaWxcbiAgICAgIC8vIGNsZWFyaW5nIGFsbCBjb29raWVzIGFuZCByZWRpcmVjdGluZyB0aGUgdXNlciB0byB0aGUgbG9naW4gc2NyZWVuLlxuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfVxuICAgIHRocm93IGVyclxuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgcHJvcHM6IHtcbiAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICB9XG4gIH1cbn1cblxuXG5jb25zdCBIb21lID0gKCkgPT4ge1xuXG4gIGNvbnN0IHsgdGl0bGUgfSA9IGNvbmZpZy5zaXRlO1xuICBcbiAgcmV0dXJuIChcbiAgICA8QmFzZSB0aXRsZT17dGl0bGV9IG1ldGFfdGl0bGU9e3VuZGVmaW5lZH0gZGVzY3JpcHRpb249e3VuZGVmaW5lZH0gaW1hZ2U9e3VuZGVmaW5lZH0gbm9pbmRleD17dW5kZWZpbmVkfSBjYW5vbmljYWw9e3VuZGVmaW5lZH0+XG4gICAgICA8RGFzaGJvYXJkIC8+XG4gICAgPC9CYXNlPlxuICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IEhvbWVcbiJdfQ==