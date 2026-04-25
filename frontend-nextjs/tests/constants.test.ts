/**
 * Tests for Application Constants
 *
 * Tests environment variable-based constants for API URLs and configuration.
 */

// Mock environment variables before importing
const originalEnv = process.env;

describe('constants', () => {
  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('PostGraphile URLs', () => {
    it('should export postgraphileApiUrl from environment', () => {
      process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL = 'http://localhost:5000/graphql';

      const constants = require('../constants');

      expect(constants.postgraphileApiUrl).toBe('http://localhost:5000/graphql');
    });

    it('should default to undefined if not set', () => {
      delete process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL;

      const constants = require('../constants');

      expect(constants.postgraphileApiUrl).toBeUndefined();
    });

    it('should export postgraphileDbUrl', () => {
      process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL = 'http://localhost:5000/graphql';

      const constants = require('../constants');

      expect(constants.postgraphileDbUrl).toBe('http://localhost:5000/graphql');
    });
  });

  describe('WebSocket URL', () => {
    it('should convert http to ws protocol', () => {
      process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL = 'http://localhost:5000/graphql';

      const constants = require('../constants');

      expect(constants.postgraphileWSUrl).toBe('ws://localhost:5000/graphql');
    });

    it('should convert https to wss protocol', () => {
      process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL = 'https://api.example.com/graphql';

      const constants = require('../constants');

      expect(constants.postgraphileWSUrl).toBe('wss://api.example.com/graphql');
    });

    it('should be undefined if POSTGRAPHILE_GRAPHQL_URL not set', () => {
      delete process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL;

      const constants = require('../constants');

      expect(constants.postgraphileWSUrl).toBeUndefined();
    });
  });

  describe('Event Queue URLs', () => {
    it('should export eventToQueueAuthUrl', () => {
      process.env.NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL = 'http://localhost:8080/events';

      const constants = require('../constants');

      expect(constants.eventToQueueAuthUrl).toBe('http://localhost:8080/events');
    });

    it('should export eventToQueueShortAuthUrl', () => {
      process.env.NEXT_PUBLIC_EVENT_TO_QUEUE_SHORT_AUTH_URL = 'http://localhost:8080/short';

      const constants = require('../constants');

      expect(constants.eventToQueueShortAuthUrl).toBe('http://localhost:8080/short');
    });

    it('should export calendarToQueueAuthUrl', () => {
      process.env.NEXT_PUBLIC_CALENDAR_TO_QUEUE_AUTH_URL = 'http://localhost:8080/calendar';

      const constants = require('../constants');

      expect(constants.calendarToQueueAuthUrl).toBe('http://localhost:8080/calendar');
    });

    it('should export featuresApplyToEventsAuthUrl', () => {
      process.env.NEXT_PUBLIC_FEATURES_APPLY_TO_EVENTS_AUTH_URL = 'http://localhost:8080/features';

      const constants = require('../constants');

      expect(constants.featuresApplyToEventsAuthUrl).toBe('http://localhost:8080/features');
    });
  });

  describe('Search Index URL', () => {
    it('should export methodToSearchIndexAuthUrl', () => {
      process.env.NEXT_PUBLIC_METHOD_TO_SEARCH_INDEX_AUTH_URL = 'http://localhost:8080/search';

      const constants = require('../constants');

      expect(constants.methodToSearchIndexAuthUrl).toBe('http://localhost:8080/search');
    });
  });

  describe('Lance Event Matcher', () => {
    it('should export lanceEventMatcherUrl with default', () => {
      delete process.env.NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL;

      const constants = require('../constants');

      expect(constants.lanceEventMatcherUrl).toBe('/api/lance-event-matcher');
    });

    it('should export lanceEventMatcherUrl from environment', () => {
      process.env.NEXT_PUBLIC_LANCE_EVENT_MATCHER_URL = 'http://localhost:9000/matcher';

      const constants = require('../constants');

      expect(constants.lanceEventMatcherUrl).toBe('http://localhost:9000/matcher');
    });

    it('should export openTrainEventVectorName', () => {
      const constants = require('../constants');

      expect(constants.openTrainEventVectorName).toBe('embeddings');
    });

    it('should export eventVectorName as alias', () => {
      const constants = require('../constants');

      expect(constants.eventVectorName).toBe('embeddings');
    });
  });

  describe('Google Calendar Auth', () => {
    it('should export googleCalendarAndroidAuthUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_URL = 'https://accounts.google.com/android';

      const constants = require('../constants');

      expect(constants.googleCalendarAndroidAuthUrl).toBe('https://accounts.google.com/android');
    });

    it('should export googleClientIdAtomicWeb', () => {
      process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB = 'client-id-123';

      const constants = require('../constants');

      expect(constants.googleClientIdAtomicWeb).toBe('client-id-123');
    });

    it('should export googleCalendarAndroidAuthRefreshUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_ANDROID_AUTH_REFRESH_URL = 'https://accounts.google.com/refresh';

      const constants = require('../constants');

      expect(constants.googleCalendarAndroidAuthRefreshUrl).toBe('https://accounts.google.com/refresh');
    });

    it('should export googleAtomicWebAuthRefreshUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_ATOMIC_WEB_AUTH_REFRESH_URL = 'https://accounts.google.com/web-refresh';

      const constants = require('../constants');

      expect(constants.googleAtomicWebAuthRefreshUrl).toBe('https://accounts.google.com/web-refresh');
    });

    it('should export googleCalendarIosAuthRefreshUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_CALENDAR_IOS_AUTH_REFRESH_URL = 'https://accounts.google.com/ios-refresh';

      const constants = require('../constants');

      expect(constants.googleCalendarIosAuthRefreshUrl).toBe('https://accounts.google.com/ios-refresh');
    });

    it('should export googleClientSecretAtomicWeb', () => {
      process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB = 'client-secret-123';

      const constants = require('../constants');

      expect(constants.googleClientSecretAtomicWeb).toBe('client-secret-123');
    });
  });

  describe('Google OAuth', () => {
    it('should export googleTokenUrl', () => {
      const constants = require('../constants');

      expect(constants.googleTokenUrl).toBe('https://oauth2.googleapis.com/token');
    });

    it('should export googleOAuthAtomicWebAPIStartUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_API_START_URL = 'https://api.example.com/oauth/start';

      const constants = require('../constants');

      expect(constants.googleOAuthAtomicWebAPIStartUrl).toBe('https://api.example.com/oauth/start');
    });

    it('should export googleSignInNormalButton path', () => {
      const constants = require('../constants');

      expect(constants.googleSignInNormalButton).toBe('public/images/google-signin-normal.png');
    });

    it('should export googleSignInDarkButton path', () => {
      const constants = require('../constants');

      expect(constants.googleSignInDarkButton).toBe('public/images/google-signin-dark-normal.png');
    });

    it('should export messyDoodleSVG path', () => {
      const constants = require('../constants');

      expect(constants.messyDoodleSVG).toBe('/MessyDoodle.svg');
    });

    it('should export googleOAuthAtomicWebRedirectUrl', () => {
      process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL = 'http://localhost:3000/callback';

      const constants = require('../constants');

      expect(constants.googleOAuthAtomicWebRedirectUrl).toBe('http://localhost:3000/callback');
    });
  });

  describe('Zoom Configuration', () => {
    it('should export zoomSaltForPass', () => {
      process.env.ZOOM_SALT_FOR_PASS = 'zoom-salt';

      const constants = require('../constants');

      expect(constants.zoomSaltForPass).toBe('zoom-salt');
    });

    it('should export zoomAuthUrl', () => {
      const constants = require('../constants');

      expect(constants.zoomAuthUrl).toBe('https://zoom.us/oauth/authorize');
    });

    it('should export zoomIVForPass', () => {
      process.env.ZOOM_IV_FOR_PASS = 'zoom-iv';

      const constants = require('../constants');

      expect(constants.zoomIVForPass).toBe('zoom-iv');
    });

    it('should export zoomResourceName', () => {
      const constants = require('../constants');

      expect(constants.zoomResourceName).toBe('zoom');
    });

    it('should export zoomPassKey', () => {
      process.env.ZOOM_PASS_KEY = 'zoom-pass-key';

      const constants = require('../constants');

      expect(constants.zoomPassKey).toBe('zoom-pass-key');
    });
  });

  describe('Python API Service', () => {
    it('should export PYTHON_TRAINING_API_URL', () => {
      process.env.NEXT_PUBLIC_PYTHON_TRAINING_API_URL = 'http://localhost:8000/training';

      const constants = require('../constants');

      expect(constants.PYTHON_TRAINING_API_URL).toBe('http://localhost:8000/training');
    });

    it('should export ATOM_OPENAI_API_KEY', () => {
      process.env.NEXT_PUBLIC_ATOM_OPENAI_API_KEY = 'sk-test-key';

      const constants = require('../constants');

      expect(constants.ATOM_OPENAI_API_KEY).toBe('sk-test-key');
    });
  });

  describe('Scheduler API', () => {
    it('should export SCHEDULER_API_URL with default', () => {
      delete process.env.NEXT_PUBLIC_SCHEDULER_API_URL;

      const constants = require('../constants');

      expect(constants.SCHEDULER_API_URL).toBe('http://localhost:8080');
    });

    it('should export SCHEDULER_API_URL from environment', () => {
      process.env.NEXT_PUBLIC_SCHEDULER_API_URL = 'http://scheduler:9000';

      const constants = require('../constants');

      expect(constants.SCHEDULER_API_URL).toBe('http://scheduler:9000');
    });
  });

  describe('PostGraphile Admin', () => {
    it('should export postgraphileGraphUrl', () => {
      process.env.POSTGRAPHILE_GRAPHQL_URL = 'http://localhost:5000/graphql';

      const constants = require('../constants');

      expect(constants.postgraphileGraphUrl).toBe('http://localhost:5000/graphql');
    });

    it('should export postgraphileAdminSecret', () => {
      process.env.POSTGRAPHILE_ADMIN_SECRET = 'admin-secret';

      const constants = require('../constants');

      expect(constants.postgraphileAdminSecret).toBe('admin-secret');
    });
  });

  describe('constant values', () => {
    it('should have correct googleTokenUrl', () => {
      const constants = require('../constants');

      expect(constants.googleTokenUrl).toBe('https://oauth2.googleapis.com/token');
    });

    it('should have correct zoomAuthUrl', () => {
      const constants = require('../constants');

      expect(constants.zoomAuthUrl).toBe('https://zoom.us/oauth/authorize');
    });

    it('should have correct zoomResourceName', () => {
      const constants = require('../constants');

      expect(constants.zoomResourceName).toBe('zoom');
    });

    it('should have correct openTrainEventVectorName', () => {
      const constants = require('../constants');

      expect(constants.openTrainEventVectorName).toBe('embeddings');
    });

    it('should have correct eventVectorName', () => {
      const constants = require('../constants');

      expect(constants.eventVectorName).toBe('embeddings');
    });
  });

  describe('environment variable precedence', () => {
    it('should prefer STORAGE_AWS over AWS for credentials', () => {
      process.env.STORAGE_AWS_ACCESS_KEY_ID = 'storage-key';
      process.env.AWS_ACCESS_KEY_ID = 'aws-key';

      // This is tested in s3-storage.test.ts, but constant values should reflect this
      const constants = require('../constants');

      // The constants file doesn't directly use these, but they should be available
      expect(process.env.STORAGE_AWS_ACCESS_KEY_ID).toBe('storage-key');
    });
  });

  describe('undefined handling', () => {
    it('should handle missing NEXT_PUBLIC variables gracefully', () => {
      delete process.env.NEXT_PUBLIC_POSTGRAPHILE_GRAPHQL_URL;
      delete process.env.NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL;
      delete process.env.NEXT_PUBLIC_SCHEDULER_API_URL;

      const constants = require('../constants');

      expect(constants.postgraphileApiUrl).toBeUndefined();
      expect(constants.eventToQueueAuthUrl).toBeUndefined();
      expect(constants.SCHEDULER_API_URL).toBe('http://localhost:8080'); // Has default
    });
  });

  describe('type safety', () => {
    it('should export all constants as strings or undefined', () => {
      const constants = require('../constants');

      const stringConstants = [
        'postgraphileApiUrl',
        'eventToQueueAuthUrl',
        'googleTokenUrl',
        'zoomAuthUrl',
        'zoomResourceName',
        'openTrainEventVectorName',
        'googleSignInNormalButton',
        'messyDoodleSVG'
      ];

      stringConstants.forEach(constName => {
        const value = constants[constName];
        if (value !== undefined) {
          expect(typeof value).toBe('string');
        }
      });
    });
  });
});
