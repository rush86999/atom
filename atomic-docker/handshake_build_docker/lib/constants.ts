

export const IS_PRODUCTION = process.env.NODE_ENV === "production"
export const postgraphileGraphUrl = process.env.POSTGRAPHILE_GRAPHQL_URL as string

export const postgraphileAdminSecret = process.env.POSTGRAPHILE_ADMIN_SECRET as string
export const authApiToken = process.env.API_TOKEN as string
export const googleTokenUrl = 'https://oauth2.googleapis.com/token'
export const googleCalendarSyncStartUrl = 'https://oauth.atomiclife.app/api/google-calendar-handshake/start-handshake'
export const googleSignInNormalButton = '/images/google-signin-normal.png'
export const googleSignInDarkButton = '/images/google-signin-dark-normal.png'
export const messyDoodleSVG = '/MessyDoodle.svg'
export const meetingAssistAdminUrl = process.env.MEETING_ASSIST_ADMIN_URL as string

type dayOfWeekIntToStringType = {
    [key: number]: string,
}

export const dayOfWeekIntToString: dayOfWeekIntToStringType = {
    1: 'MONDAY',
    2: 'TUESDAY',
    3: 'WEDNESDAY',
    4: 'THURSDAY',
    5: 'FRIDAY',
    6: 'SATURDAY',
    7: 'SUNDAY'
}

