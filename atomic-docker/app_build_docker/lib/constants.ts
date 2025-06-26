// prod VERSION

export const hasuraApiUrl = process.env.NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_URL

export const eventToQueueAuthUrl = process.env.NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL
export const eventToQueueShortAuthUrl = process.env.NEXT_PUBLIC_EVENT_TO_QUEUE_SHORT_AUTH_URL
export const calendarToQueueAuthUrl = process.env.NEXT_PUBLIC_CALENDAR_TO_QUEUE_AUTH_URL
export const featuresApplyToEventsAuthUrl = process.env.NEXT_PUBLIC_FEATURES_APPLY_TO_EVENTS_AUTH_URL

export const methodToSearchIndexAuthUrl = process.env.NEXT_PUBLIC_METHOD_TO_SEARCH_INDEX_AUTH_URL

export const lanceEventMatcherUrl = process.env.NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL || '/api/lance-event-matcher';

export const openTrainEventVectorName = 'embeddings'
export const eventVectorName = openTrainEventVectorName
export const hasuraDbUrl = process.env.NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_URL
export const hasuraWSUrl = process.env.NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_WS_URL

export const googleCalendarAndroidAuthUrl = process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_URL
export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB
export const googleCalendarAndroidAuthRefreshUrl = process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_REFRESH_URL
export const googleAtomicWebAuthRefreshUrl = process.env.NEXT_PUBLIC_GOOGLE_ATOMIC_WEB_AUTH_REFRESH_URL
export const googleCalendarIosAuthRefreshUrl = process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_IOS_AUTH_REFRESH_URL
export const googleClientSecretAtomicWeb = process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB

export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET
export const googleTokenUrl = 'https://oauth2.googleapis.com/token'
export const googleOAuthAtomicWebAPIStartUrl = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_API_START_URL
export const googleSignInNormalButton = 'public/images/google-signin-normal.png'
export const googleSignInDarkButton = 'public/images/google-signin-dark-normal.png'
export const messyDoodleSVG = '/MessyDoodle.svg'
export const googleOAuthAtomicWebRedirectUrl = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL
export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS
export const zoomAuthUrl = 'https://zoom.us/oauth/authorize'
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS
export const zoomResourceName = 'zoom'
export const zoomPassKey = process.env.ZOOM_PASS_KEY

// Python API Service URLs (used by client-side calls if necessary)
export const PYTHON_TRAINING_API_URL = process.env.NEXT_PUBLIC_PYTHON_TRAINING_API_URL;
// Assuming OpenAI API key might be needed client-side for some reason, or passed through if helper is used server-side.
// For direct client-to-Python-service calls that require this key, it must be exposed.
export const ATOM_OPENAI_API_KEY = process.env.NEXT_PUBLIC_ATOM_OPENAI_API_KEY;

// Scheduler API URL
export const SCHEDULER_API_URL = process.env.NEXT_PUBLIC_SCHEDULER_API_URL || 'http://localhost:8080';
