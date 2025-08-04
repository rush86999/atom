"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const date_utils_1 = require("@lib/date-utils");
const date_fns_1 = require("date-fns");
const react_native_star_rating_widget_1 = __importDefault(require("react-native-star-rating-widget"));
const getEventById_1 = __importDefault(require("@lib/apollo/gql/getEventById"));
const updateEventForPositiveRating_1 = __importDefault(require("@lib/apollo/gql/updateEventForPositiveRating"));
const updateEventForNegativeRating_1 = __importDefault(require("@lib/apollo/gql/updateEventForNegativeRating"));
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const UserTrainCalendarHelper_1 = require("@lib/Calendar/UserTrainCalendarHelper");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../config/backendConfig");
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
function UserRateEvent(props) {
    const [rating, setRating] = (0, react_1.useState)(0);
    // const [isModalVisible, setIsModalVisible] = useState(true)
    const client = props?.client;
    const { eventId } = props;
    const toast = (0, react_2.useToast)();
    (0, react_1.useEffect)(() => {
        const updateEvent = async () => {
            try {
                if (rating === 0) {
                    return;
                }
                if (!eventId) {
                    console.log('no eventId');
                    return;
                }
                const existingEvent = (await client.query({
                    query: getEventById_1.default,
                    variables: {
                        id: eventId,
                    },
                })).data?.Event_by_pk;
                if (!existingEvent) {
                    throw new Error('Event not found');
                }
                console.log(rating, ' rating');
                if (Math.round(rating - 3) > 0) {
                    const positiveImpactScore = Math.round(rating - 3);
                    const positiveImpactDayOfWeek = (0, date_fns_1.getISODay)((0, date_utils_1.dayjs)(existingEvent.startDate).toDate());
                    const positiveImpactTime = (0, date_utils_1.dayjs)(existingEvent.startDate).toDate().toTimeString().slice(0, 5);
                    console.log(positiveImpactScore, ' positiveScore');
                    await client.mutate({
                        mutation: updateEventForPositiveRating_1.default,
                        variables: {
                            id: existingEvent.id,
                            positiveImpactScore,
                            positiveImpactDayOfWeek,
                            positiveImpactTime,
                        },
                    });
                }
                else if (Math.round(rating - 3) < 0) {
                    const negativeImpactScore = Math.abs(Math.round(3 - rating));
                    const negativeImpactDayOfWeek = (0, date_fns_1.getISODay)((0, date_utils_1.dayjs)(existingEvent.startDate).toDate());
                    const negativeImpactTime = (0, date_utils_1.dayjs)(existingEvent.startDate).toDate().toTimeString().slice(0, 5);
                    console.log(negativeImpactScore, ' negativeScore');
                    await client.mutate({
                        mutation: updateEventForNegativeRating_1.default,
                        variables: {
                            id: existingEvent.id,
                            negativeImpactScore,
                            negativeImpactDayOfWeek,
                            negativeImpactTime,
                        },
                    });
                }
                await (0, UserTrainCalendarHelper_1.addToSearchIndex)(existingEvent);
                toast({
                    status: 'success',
                    title: 'Event rated successfully',
                    description: 'Event rated successfully',
                    duration: 9000,
                    isClosable: true,
                });
                // setIsModalVisible(false)
                props.hideRating();
            }
            catch (error) {
                toast({
                    status: 'error',
                    title: 'Failed to rate event',
                    description: 'Failed to rate event',
                    duration: 9000,
                    isClosable: true,
                });
                console.log(error, ' error inside userrateevent');
            }
        };
        if (rating > 0) {
            updateEvent();
        }
    }, [client, eventId, props, rating, toast]);
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { p: { phone: 's', tablet: 'm' }, variant: "rating", children: "rate your productivity level" }), (0, jsx_runtime_1.jsx)(react_native_star_rating_widget_1.default, { rating: rating, onChange: setRating, starSize: 56 })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)("button", { className: "btn btn-link no-underline hover:no-underline", onClick: props.hideRating, children: "Close" }) })] }));
}
exports.default = UserRateEvent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclJhdGVFdmVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXJSYXRlRXZlbnQudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBa0JBLGdEQXFDQzs7QUF2REQsaUNBQWtEO0FBQ2xELDRDQUEyQztBQUMzQyxnREFBdUM7QUFDdkMsdUNBQW9DO0FBRXBDLHNHQUF3RDtBQUV4RCxnRkFBdUQ7QUFDdkQsZ0hBQXVGO0FBQ3ZGLGdIQUF1RjtBQUN2RixpRUFBd0M7QUFDeEMsbUVBQTBDO0FBQzFDLG1GQUF3RTtBQUV4RSx3RUFBOEM7QUFDOUMsOERBQTBEO0FBQzFELDhFQUFxRDtBQUU5QyxLQUFLLFVBQVUsa0JBQWtCLENBQUMsRUFBRSxHQUFHLEVBQUUsR0FBRyxFQUFpRDtJQUNsRywwRkFBMEY7SUFDMUYsc0NBQXNDO0lBQ3RDLHlFQUF5RTtJQUN6RSwwQkFBZSxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFBO0lBQ3JDLElBQUksT0FBTyxDQUFBO0lBQ1gsSUFBSSxDQUFDO1FBQ0gsT0FBTyxHQUFHLE1BQU0saUJBQU8sQ0FBQyxVQUFVLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUMzQyw2QkFBNkIsRUFBRSxLQUFLO2dCQUNsQyxPQUFPLEVBQUUsQ0FBQTtZQUNYLENBQUM7U0FDRixDQUFDLENBQUE7SUFDSixDQUFDO0lBQUMsT0FBTyxHQUFRLEVBQUUsQ0FBQztRQUNsQixJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztZQUNqRCxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsZUFBZSxFQUFFLGVBQWUsRUFBRSxFQUFFLENBQUE7UUFDeEQsQ0FBQzthQUFNLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUNuRCxrRUFBa0U7WUFDbEUscUVBQXFFO1lBQ3JFLE9B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YXRlLCB1c2VFZmZlY3QgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7IHVzZVRvYXN0IH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCdcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJ1xuaW1wb3J0IHsgZ2V0SVNPRGF5IH0gZnJvbSAnZGF0ZS1mbnMnXG5pbXBvcnQgeyBFdmVudFR5cGUsIFRpbWUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9FdmVudFR5cGUnXG5pbXBvcnQgU3RhclJhdGluZyBmcm9tICdyZWFjdC1uYXRpdmUtc3Rhci1yYXRpbmctd2lkZ2V0J1xuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCdcbmltcG9ydCBnZXRFdmVudEJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldEV2ZW50QnlJZCdcbmltcG9ydCB1cGRhdGVFdmVudEZvclBvc2l0aXZlUmF0aW5nIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cGRhdGVFdmVudEZvclBvc2l0aXZlUmF0aW5nJ1xuaW1wb3J0IHVwZGF0ZUV2ZW50Rm9yTmVnYXRpdmVSYXRpbmcgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZUV2ZW50Rm9yTmVnYXRpdmVSYXRpbmcnXG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnXG5pbXBvcnQgVGV4dCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vVGV4dCdcbmltcG9ydCB7IGFkZFRvU2VhcmNoSW5kZXggfSBmcm9tICdAbGliL0NhbGVuZGFyL1VzZXJUcmFpbkNhbGVuZGFySGVscGVyJ1xuaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHN1cGVydG9rZW5zTm9kZSBmcm9tICdzdXBlcnRva2Vucy1ub2RlJ1xuaW1wb3J0IHsgYmFja2VuZENvbmZpZyB9IGZyb20gJy4uLy4uL2NvbmZpZy9iYWNrZW5kQ29uZmlnJ1xuaW1wb3J0IFNlc3Npb24gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbidcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFNlcnZlclNpZGVQcm9wcyh7IHJlcSwgcmVzIH06IHsgcmVxOiBOZXh0QXBpUmVxdWVzdCwgcmVzOiBOZXh0QXBpUmVzcG9uc2UgfSkge1xuICAvLyBOb3RpY2UgaG93IHRoZSBzZXJ2ZXIgdXNlcyBgQVBJYCBmcm9tIGB3aXRoU1NSQ29udGV4dGAsIGluc3RlYWQgb2YgdGhlIHRvcC1sZXZlbCBgQVBJYC5cbiAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgLy8gdGhpcyBydW5zIG9uIHRoZSBiYWNrZW5kLCBzbyB3ZSBtdXN0IGNhbGwgaW5pdCBvbiBzdXBlcnRva2Vucy1ub2RlIFNES1xuICBzdXBlcnRva2Vuc05vZGUuaW5pdChiYWNrZW5kQ29uZmlnKCkpXG4gIGxldCBzZXNzaW9uXG4gIHRyeSB7XG4gICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgcmV0dXJuIFtdXG4gICAgICB9LFxuICAgIH0pXG4gIH0gY2F0Y2ggKGVycjogYW55KSB7XG4gICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICB9IGVsc2UgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlVOQVVUSE9SSVNFRCkge1xuICAgICAgLy8gdGhpcyB3aWxsIGZvcmNlIHRoZSBmcm9udGVuZCB0byB0cnkgYW5kIHJlZnJlc2ggd2hpY2ggd2lsbCBmYWlsXG4gICAgICAvLyBjbGVhcmluZyBhbGwgY29va2llcyBhbmQgcmVkaXJlY3RpbmcgdGhlIHVzZXIgdG8gdGhlIGxvZ2luIHNjcmVlbi5cbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH1cbiAgICB0aHJvdyBlcnJcbiAgfVxuXG4gIGlmICghc2Vzc2lvbj8uZ2V0VXNlcklkKCkpIHtcbiAgICByZXR1cm4ge1xuICAgICAgcmVkaXJlY3Q6IHtcbiAgICAgICAgZGVzdGluYXRpb246ICcvVXNlci9Mb2dpbi9Vc2VyTG9naW4nLFxuICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgfSxcbiAgICB9XG4gIH1cblxuICByZXR1cm4ge1xuICAgIHByb3BzOiB7XG4gICAgICBzdWI6IHNlc3Npb24uZ2V0VXNlcklkKCksXG4gICAgfVxuICB9XG59XG5cblxudHlwZSBQcm9wcyA9IHtcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBldmVudElkOiBzdHJpbmcsXG4gICAgaGlkZVJhdGluZzogKCkgPT4gdm9pZCxcbiAgICBpc1JhdGVFdmVudDogYm9vbGVhbixcbiAgICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxufVxuXG5mdW5jdGlvbiBVc2VyUmF0ZUV2ZW50KHByb3BzOiBQcm9wcykge1xuICAgIGNvbnN0IFtyYXRpbmcsIHNldFJhdGluZ10gPSB1c2VTdGF0ZSgwKVxuICAgIC8vIGNvbnN0IFtpc01vZGFsVmlzaWJsZSwgc2V0SXNNb2RhbFZpc2libGVdID0gdXNlU3RhdGUodHJ1ZSlcblxuICAgIGNvbnN0IGNsaWVudCA9IHByb3BzPy5jbGllbnRcbiAgICBjb25zdCB7IGV2ZW50SWQgfSA9IHByb3BzXG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG5cbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IHVwZGF0ZUV2ZW50ID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgaWYgKHJhdGluZyA9PT0gMCkge1xuICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoIWV2ZW50SWQpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRJZCcpXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGNvbnN0IGV4aXN0aW5nRXZlbnQgPSAoYXdhaXQgY2xpZW50LnF1ZXJ5PHsgRXZlbnRfYnlfcGs6IEV2ZW50VHlwZSB9Pih7XG4gICAgICAgICAgICAgICAgcXVlcnk6IGdldEV2ZW50QnlJZCxcbiAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0pKS5kYXRhPy5FdmVudF9ieV9wa1xuICAgICAgICAgICAgaWYgKCFleGlzdGluZ0V2ZW50KSB7XG4gICAgICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdFdmVudCBub3QgZm91bmQnKVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zb2xlLmxvZyhyYXRpbmcsICcgcmF0aW5nJylcblxuICAgICAgICAgICAgaWYgKE1hdGgucm91bmQocmF0aW5nIC0gMykgPiAwKSB7XG4gICAgICAgICAgICAgICAgY29uc3QgcG9zaXRpdmVJbXBhY3RTY29yZSA9IE1hdGgucm91bmQocmF0aW5nIC0gMylcbiAgICAgICAgICAgICAgICBjb25zdCBwb3NpdGl2ZUltcGFjdERheU9mV2VlayA9IGdldElTT0RheShkYXlqcyhleGlzdGluZ0V2ZW50LnN0YXJ0RGF0ZSkudG9EYXRlKCkpXG4gICAgICAgICAgICAgICAgY29uc3QgcG9zaXRpdmVJbXBhY3RUaW1lOiBUaW1lID0gZGF5anMoZXhpc3RpbmdFdmVudC5zdGFydERhdGUpLnRvRGF0ZSgpLnRvVGltZVN0cmluZygpLnNsaWNlKDAsIDUpIGFzIFRpbWVcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhwb3NpdGl2ZUltcGFjdFNjb3JlLCAnIHBvc2l0aXZlU2NvcmUnKVxuICAgICAgICAgICAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGUoe1xuICAgICAgICAgICAgICAgICAgICBtdXRhdGlvbjogdXBkYXRlRXZlbnRGb3JQb3NpdGl2ZVJhdGluZyxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZDogZXhpc3RpbmdFdmVudC5pZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZSxcblxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICB9IGVsc2UgaWYgKE1hdGgucm91bmQocmF0aW5nIC0gMykgPCAwKSB7XG4gICAgICAgICAgICAgICAgY29uc3QgbmVnYXRpdmVJbXBhY3RTY29yZSA9IE1hdGguYWJzKE1hdGgucm91bmQoMyAtIHJhdGluZykpXG4gICAgICAgICAgICAgICAgY29uc3QgbmVnYXRpdmVJbXBhY3REYXlPZldlZWsgPSBnZXRJU09EYXkoZGF5anMoZXhpc3RpbmdFdmVudC5zdGFydERhdGUpLnRvRGF0ZSgpKVxuICAgICAgICAgICAgICAgIGNvbnN0IG5lZ2F0aXZlSW1wYWN0VGltZTogVGltZSA9IGRheWpzKGV4aXN0aW5nRXZlbnQuc3RhcnREYXRlKS50b0RhdGUoKS50b1RpbWVTdHJpbmcoKS5zbGljZSgwLCA1KSBhcyBUaW1lXG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2cobmVnYXRpdmVJbXBhY3RTY29yZSwgJyBuZWdhdGl2ZVNjb3JlJylcbiAgICAgICAgICAgICAgICBhd2FpdCBjbGllbnQubXV0YXRlKHtcbiAgICAgICAgICAgICAgICAgICAgbXV0YXRpb246IHVwZGF0ZUV2ZW50Rm9yTmVnYXRpdmVSYXRpbmcsXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWQ6IGV4aXN0aW5nRXZlbnQuaWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgYXdhaXQgYWRkVG9TZWFyY2hJbmRleChleGlzdGluZ0V2ZW50KVxuICAgICAgICAgICAgXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnc3VjY2VzcycsXG4gICAgICAgICAgICAgICAgdGl0bGU6ICdFdmVudCByYXRlZCBzdWNjZXNzZnVsbHknLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnRXZlbnQgcmF0ZWQgc3VjY2Vzc2Z1bGx5JyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIC8vIHNldElzTW9kYWxWaXNpYmxlKGZhbHNlKVxuICAgICAgICAgICAgcHJvcHMuaGlkZVJhdGluZygpXG4gICAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnRmFpbGVkIHRvIHJhdGUgZXZlbnQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnRmFpbGVkIHRvIHJhdGUgZXZlbnQnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICB9KVxuXG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlcnJvciwgJyBlcnJvciBpbnNpZGUgdXNlcnJhdGVldmVudCcpXG4gICAgICAgIH1cbiAgICB9XG4gICAgICAgIGlmIChyYXRpbmcgPiAwKSB7XG4gICAgICAgICAgICB1cGRhdGVFdmVudCgpXG4gICAgICAgIH1cbiAgICB9LCBbY2xpZW50LCBldmVudElkLCBwcm9wcywgcmF0aW5nLCB0b2FzdF0pXG5cbiAgICByZXR1cm4gKFxuICAgICAgICA8Qm94IGZsZXg9ezF9IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICA8VGV4dCBwPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IHZhcmlhbnQ9XCJyYXRpbmdcIj5cbiAgICAgICAgICAgICAgICAgICAgcmF0ZSB5b3VyIHByb2R1Y3Rpdml0eSBsZXZlbFxuICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICA8U3RhclJhdGluZ1xuICAgICAgICAgICAgICAgICAgICByYXRpbmc9e3JhdGluZ31cbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e3NldFJhdGluZ31cbiAgICAgICAgICAgICAgICAgICAgc3RhclNpemU9ezU2fVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxCb3ggcD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICA8YnV0dG9uIGNsYXNzTmFtZT1cImJ0biBidG4tbGluayBuby11bmRlcmxpbmUgaG92ZXI6bm8tdW5kZXJsaW5lXCIgb25DbGljaz17cHJvcHMuaGlkZVJhdGluZ30+XG4gICAgICAgICAgICAgICAgICAgIENsb3NlXG4gICAgICAgICAgICAgICAgPC9idXR0b24+XG4gICAgICAgICAgIFxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgIDwvQm94PlxuICAgIClcbn1cblxuZXhwb3J0IGRlZmF1bHQgVXNlclJhdGVFdmVudFxuXG4iXX0=