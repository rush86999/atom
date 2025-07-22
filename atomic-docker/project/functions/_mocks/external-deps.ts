// Mock external dependencies for local testing without real API calls

// Mock OpenAI
export class MockOpenAI {
  constructor(config: any) {}

  chat = {
    completions: {
      create: async (params: any) => ({
        id: 'mock-completion-id',
        object: 'chat.completion',
        created: Date.now(),
        model: params.model || 'mock-model',
        choices: [{
          index: 0,
          message: {
            role: 'assistant',
            content: `Mock response for: ${params.messages[params.messages.length - 1].content}`
          },
          finish_reason: 'stop'
        }],
        usage: {
          prompt_tokens: 10,
          completion_tokens: 10,
          total_tokens: 20
        }
      })
    }
  };

  embeddings = {
    create: async (params: any) => ({
      object: 'list',
      data: [{
        object: 'embedding',
        embedding: new Array(1536).fill(0.01), // Mock embedding vector
        index: 0
      }],
      model: params.model || 'text-embedding-3-small',
      usage: {
        prompt_tokens: 10,
        total_tokens: 10
      }
    })
  };
}

// Mock date-fns
export const mockDateFns = {
  startOfWeek: (date: Date, options?: any) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  },
  endOfWeek: (date: Date, options?: any) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? 0 : 7);
    return new Date(d.setDate(diff));
  },
  startOfMonth: (date: Date) => {
    return new Date(date.getFullYear(), date.getMonth(), 1);
  },
  endOfMonth: (date: Date) => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0);
  },
  add: (date: Date, duration: any) => {
    const d = new Date(date);
    if (duration.days) d.setDate(d.getDate() + duration.days);
    if (duration.months) d.setMonth(d.getMonth() + duration.months);
    if (duration.years) d.setFullYear(d.getFullYear() + duration.years);
    if (duration.hours) d.setHours(d.getHours() + duration.hours);
    if (duration.minutes) d.setMinutes(d.getMinutes() + duration.minutes);
    return d;
  },
  sub: (date: Date, duration: any) => {
    const d = new Date(date);
    if (duration.days) d.setDate(d.getDate() - duration.days);
    if (duration.months) d.setMonth(d.getMonth() - duration.months);
    if (duration.years) d.setFullYear(d.getFullYear() - duration.years);
    if (duration.hours) d.setHours(d.getHours() - duration.hours);
    if (duration.minutes) d.setMinutes(d.getMinutes() - duration.minutes);
    return d;
  },
  format: (date: Date, formatStr: string) => {
    // Simple format implementation
    const d = new Date(date);
    return formatStr
      .replace('yyyy', d.getFullYear().toString())
      .replace('MM', (d.getMonth() + 1).toString().padStart(2, '0'))
      .replace('dd', d.getDate().toString().padStart(2, '0'))
      .replace('HH', d.getHours().toString().padStart(2, '0'))
      .replace('mm', d.getMinutes().toString().padStart(2, '0'))
      .replace('ss', d.getSeconds().toString().padStart(2, '0'));
  },
  getISODay: (date: Date) => {
    const day = date.getDay();
    return day === 0 ? 7 : day;
  }
};

// Mock googleapis
export const mockGoogleApis = {
  google: {
    auth: {
      OAuth2: class MockOAuth2 {
        credentials: any = {};

        constructor(clientId?: string, clientSecret?: string, redirectUri?: string) {}

        setCredentials(tokens: any) {
          this.credentials = tokens;
        }

        getAccessToken() {
          return Promise.resolve({
            token: 'mock-access-token',
            res: null
          });
        }

        refreshAccessToken() {
          return Promise.resolve({
            credentials: {
              access_token: 'mock-refreshed-token',
              refresh_token: 'mock-refresh-token',
              expiry_date: Date.now() + 3600000
            }
          });
        }
      }
    },
    calendar: (options: any) => ({
      events: {
        list: async (params: any) => ({
          data: {
            items: [],
            nextPageToken: null,
            summary: 'Mock Calendar',
            updated: new Date().toISOString()
          }
        }),
        get: async (params: any) => ({
          data: {
            id: params.eventId || 'mock-event-id',
            summary: 'Mock Event',
            start: { dateTime: new Date().toISOString() },
            end: { dateTime: new Date(Date.now() + 3600000).toISOString() }
          }
        }),
        insert: async (params: any) => ({
          data: {
            id: 'mock-new-event-id',
            ...params.requestBody,
            created: new Date().toISOString(),
            updated: new Date().toISOString()
          }
        }),
        update: async (params: any) => ({
          data: {
            id: params.eventId,
            ...params.requestBody,
            updated: new Date().toISOString()
          }
        }),
        delete: async (params: any) => ({})
      },
      calendarList: {
        list: async () => ({
          data: {
            items: [{
              id: 'primary',
              summary: 'Primary Calendar',
              primary: true,
              accessRole: 'owner'
            }]
          }
        })
      }
    })
  }
};

// Mock OpenSearch
export class MockOpenSearchClient {
  constructor(config: any) {}

  async search(params: any) {
    return {
      body: {
        took: 1,
        timed_out: false,
        hits: {
          total: { value: 0, relation: 'eq' },
          hits: []
        }
      }
    };
  }

  async index(params: any) {
    return {
      body: {
        _index: params.index,
        _id: params.id || 'mock-doc-id',
        _version: 1,
        result: 'created'
      }
    };
  }

  async bulk(params: any) {
    return {
      body: {
        took: 1,
        errors: false,
        items: []
      }
    };
  }

  async delete(params: any) {
    return {
      body: {
        _index: params.index,
        _id: params.id,
        result: 'deleted'
      }
    };
  }
}

// Mock AWS S3
export class MockS3Client {
  constructor(config: any) {}

  async send(command: any) {
    if (command instanceof MockPutObjectCommand) {
      return {
        ETag: '"mock-etag"',
        VersionId: 'mock-version-id'
      };
    }
    return {};
  }
}

export class MockPutObjectCommand {
  constructor(public params: any) {}
}

// Mock Kafka
export class MockKafka {
  constructor(config: any) {}

  producer() {
    return {
      connect: async () => {},
      send: async (params: any) => {
        console.log('Mock Kafka send:', params);
        return [{ topicName: params.topic, partition: 0, errorCode: 0 }];
      },
      disconnect: async () => {}
    };
  }

  consumer(config: any) {
    return {
      connect: async () => {},
      subscribe: async (params: any) => {},
      run: async (params: any) => {},
      disconnect: async () => {}
    };
  }
}

// Mock ip module
export const mockIp = {
  address: () => '127.0.0.1',
  isPrivate: (addr: string) => addr.startsWith('192.168.') || addr.startsWith('10.') || addr === '127.0.0.1',
  isLoopback: (addr: string) => addr === '127.0.0.1' || addr === '::1',
  loopback: (family?: string) => family === 'ipv6' ? '::1' : '127.0.0.1'
};

// Mock got (HTTP client)
export const mockGot = {
  get: async (url: string, options?: any) => ({
    body: {},
    statusCode: 200,
    headers: {}
  }),
  post: async (url: string, options?: any) => ({
    body: {},
    statusCode: 200,
    headers: {}
  }),
  put: async (url: string, options?: any) => ({
    body: {},
    statusCode: 200,
    headers: {}
  }),
  delete: async (url: string, options?: any) => ({
    body: {},
    statusCode: 200,
    headers: {}
  })
};

// Mock axios
export const mockAxios = {
  get: async (url: string, config?: any) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config: config || {}
  }),
  post: async (url: string, data?: any, config?: any) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config: config || {}
  }),
  put: async (url: string, data?: any, config?: any) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config: config || {}
  }),
  delete: async (url: string, config?: any) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config: config || {}
  })
};

// Export all mocks
export default {
  OpenAI: MockOpenAI,
  dateFns: mockDateFns,
  googleapis: mockGoogleApis,
  OpenSearchClient: MockOpenSearchClient,
  S3Client: MockS3Client,
  PutObjectCommand: MockPutObjectCommand,
  Kafka: MockKafka,
  ip: mockIp,
  got: mockGot,
  axios: mockAxios
};
