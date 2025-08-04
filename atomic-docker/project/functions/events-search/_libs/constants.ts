export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const authApiToken = process.env.API_TOKEN;

export const openSearchEndPoint = process.env.OPENSEARCH_ENDPOINT;
export const eventVectorName = 'event-vector';
export const eventVectorDimensions = 384;
export const eventSearchIndex = 'knn-events-index';

export const openAIPassKey = process.env.OPENAI_PASS_KEY;
export const defaultOpenAIAPIKey = process.env.OPENAI_API_KEY;

export const emailKnwIndex = 'knn-knw-index';
export const emailKnwVectorDimensions = 1536;
export const emailKnwVectorName = 'embeddings';

export const openAIChatGPTModel = 'gpt-3.5-turbo';

export const agentKnwIndex = 'knn-agent-index';
export const agentKnwVectorDimensions = 1536;
export const agentKnwVectorName = 'embeddings';

export const openTrainEventVectorName = 'embeddings';
export const openTrainEventVectorDimensions = 1536;
export const openTrainEventIndex = 'knn-open-train-event-index';

export const openAllEventIndex = 'knn-open-all-event-index';
export const openAllEventVectorDimensions = 1536;
export const openAllEventVectorName = 'embeddings';
