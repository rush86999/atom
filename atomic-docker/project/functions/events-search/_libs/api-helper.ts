
import { Client } from '@opensearch-project/opensearch'
import { Config, ConfigurationOptions, AWSError } from 'aws-sdk'
import { APIVersions } from 'aws-sdk/lib/config'
import { ConfigurationServicePlaceholders } from 'aws-sdk/lib/config_service_placeholders'
import { openSearchEndPoint, eventSearchIndex, eventVectorDimensions, eventVectorName, hasuraGraphUrl, hasuraAdminSecret, openAIPassKey, emailKnwIndex, openAIChatGPTModel, emailKnwVectorName, agentKnwIndex, agentKnwVectorName, openTrainEventIndex, openTrainEventVectorName, openAllEventIndex, openAllEventVectorName, openTrainEventVectorDimensions, openAllEventVectorDimensions, defaultOpenAIAPIKey } from './constants'
import { OpenSearchResponseBodyType, EmailKnwSourceType, AgentKnwSourceType, OpenSearchGetResponseBodyType } from './types'

import got from 'got'

import crypto from 'crypto'
import OpenAI from "openai"
import { CreateChatCompletionRequestMessage } from 'openai/resources/chat'
import { ChatGPTRoleType } from '@/gpt-meeting/_libs/types/ChatGPTTypes'



const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});

export const getSearchClient = async () => {
    try {
        return new Client({
            node: process.env.OPENSEARCH_ENDPOINT,
            auth: {
                username: process.env.OPENSEARCH_USERNAME,
                password: process.env.OPENSEARCH_PASSWORD,
              }
        })
    } catch (e) {
        console.log(e, ' unable to get credentials from getSearchClient')
    }

}

export const putDataInAllEventIndexInOpenSearch = async (
    id: string,
    vector: number[],
    userId: string,
    start_date: string,
    end_date: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.index({
            id,
            index: openAllEventIndex,
            body: { [openAllEventVectorName]: vector, userId, start_date, end_date },
            refresh: true
        })
        console.log('Adding document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to put data into search')
    }
}

export const deleteDocInAllEventIndexInOpenSearch = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.delete({
            id,
            index: openAllEventIndex,
        })
        console.log('Deleting document in search:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to delete doc')
    }
}

export const getVectorInAllEventIndexInOpenSearch = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()

        const {body }: { body: OpenSearchGetResponseBodyType} = await client.get({
            index: openAllEventIndex,
            id,
            stored_fields: [openAllEventVectorName],
        })
        
        const vector = body._source[openAllEventVectorName]
        return vector
    } catch (e) {
        console.log(e, ' unable to get vector inside getVectorInAllEventIndexInOpenSearch')
    }
}

export const getVectorInTrainEventIndexInOpenSearch = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()

        const {body }: { body: OpenSearchGetResponseBodyType} = await client.get({
            index: openTrainEventIndex,
            id,
            stored_fields: [openTrainEventVectorName],
        })
        
        const vector = body._source[openTrainEventVectorName]
        return vector
    } catch (e) {
        console.log(e, ' unable to get vector inside getVectorInAllEventIndexInOpenSearch')
    }
}

export const putDataInTrainEventIndexInOpenSearch = async (
    id: string,
    vector: number[],
    userId: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.index({
            id,
            index: openTrainEventIndex,
            body: { [openTrainEventVectorName]: vector, userId },
            refresh: true
        })
        console.log('Adding document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to put data into search')
    }
}

export const deleteDocInTrainEventIndexInOpenSearch = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.delete({
            id,
            index: openTrainEventIndex,
        })
        console.log('Deleting document in search:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to delete doc')
    }
}

export const updateDocInTrainEventIndexInOpenSearch = async (
    id: string,
    vector: number[],
    userId: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.update({
            index: openTrainEventIndex,
            id,
            body: { [openTrainEventVectorName]: vector, userId },
            refresh: true
        })
        console.log('Updating document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to update docs')
    }
}

export const searchTrainEventIndexInOpenSearch = async (
    userId: string,
    searchVector: number[],
): Promise<OpenSearchResponseBodyType> => {
    try {
        const client = await getSearchClient()
        const response = await client.search({
            index: openTrainEventIndex,
            body: {
                "size": 1,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "term": {
                                        userId,
                                    }
                                }
                            }
                        },
                        "script": {
                            "lang": "knn",
                            "source": "knn_score",
                            "params": {
                                "field": openTrainEventVectorName,
                                "query_value": searchVector,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                },
                "min_score": 1.2
            }
        })
        console.log(response, ' search data in search engine')
        return response.body
    } catch (e) {
        console.log(e, ' unable to search data')
    }
}


export const searchData3 = async (
    userId: string,
    searchVector: number[],
): Promise<OpenSearchResponseBodyType> => {
    try {
        const client = await getSearchClient()
        const response = await client.search({
            index: eventSearchIndex,
            body: {
                "size": 1,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "term": {
                                        userId,
                                    }
                                }
                            }
                        },
                        "script": {
                            "lang": "knn",
                            "source": "knn_score",
                            "params": {
                                "field": eventVectorName,
                                "query_value": searchVector,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                },
                "min_score": 1.2
            }
        })
        console.log(response, ' search data in search engine')
        return response.body
    } catch (e) {
        console.log(e, ' unable to search data')
    }
}


export const putDataInSearch = async (
    id: string,
    vector: number[],
    userId: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.index({
            id,
            index: eventSearchIndex,
            body: { [eventVectorName]: vector, userId },
            refresh: true
        })
        console.log('Adding document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to put data into search')
    }
}

export const updateDocInSearch3 = async (
    id: string,
    vector: number[],
    userId: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.update({
            index: eventSearchIndex,
            id,
            body: { [eventVectorName]: vector, userId },
            refresh: true
        })
        console.log('Updating document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to update docs')
    }
}

export const deleteDocInSearch3 = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.delete({
            id,
            index: eventSearchIndex,
        })
        console.log('Deleting document in search:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to delete doc')
    }
}

export const listRepositoriesInSearch = async () => {
    try {
        const client = await getSearchClient()
        const response = await client.snapshot.get_repository()
        console.log(response, ' listRepositoriesOfSearchData in search engine')
        return response.body
    } catch (e) {
        console.log(e, ' unable to get list of repositories')
    }
}


export const listSnapshotsOfRepositoryOfSearchData = async (
    repository: string,
) => {
    try {
        // validate
        if (!repository) {
            console.log('no repository present')
            return null
        }

        const response = await got(`${process.env.OPENSEARCH_ENDPOINT}/_snapshot/${repository}/_all`, {
            method: 'GET',
            headers: {
                'Authorization': 'Basic ' + Buffer.from(`${process.env.OPENSEARCH_USERNAME}:${process.env.OPENSEARCH_PASSWORD}`).toString('base64')
            }
        });

        console.log(response.body);

        return response.body
    } catch (e) {
        console.log(e, ' unable to get snapshots inside listSnapShotsOfRepositoryOfSearchData')
    }
}

export const restoreSnapshotInSearch = async (
    repository: string,
    snapshot: string,
) => {
    try {
        // validate
        if (!repository) {
            console.log('no repository present inside restoreSnapshotInSearch')
            return
        }

        if (!snapshot) {
            console.log('no snapshot present inside restoreSnapshotInSearch')
            return
        }

        const client = await getSearchClient()
        const response = await client.snapshot.restore({
            repository,
            snapshot,
            body: {
                indices: eventSearchIndex,
            }
        })

        console.log(response, ' successfully restored index from snapshot')

    } catch (e) {
        console.log(e, ' unable to restore snapshot')
    }
}


export const deleteIndexInSearch = async (
    index_name: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.indices.delete({
            index: index_name,
        })

        console.log(response.body, ' deleted index successfully')
    } catch (e) {
        console.log(e, ' unable to delete index of search')
    }
}

export const createIndexInSearch3 = async () => {
    try {
        const client = await getSearchClient()

        const response = await client.indices.create({
            index: eventSearchIndex,
            body: {
                "mappings": {
                    "properties": {
                        [eventVectorName]: {
                            "type": "knn_vector",
                            "dimension": eventVectorDimensions,
                        },
                        "userId": {
                            "type": "keyword"
                        }
                    }
                }
            },
        });

        console.log('Creating index:');
        console.log(response.body, ' created index')
    } catch (e) {
        console.log(e, ' unable to create index')
    }
}

export const createTrainEventIndexInOpenSearch = async () => {
    try {
        const client = await getSearchClient()

        const response = await client.indices.create({
            index: openTrainEventIndex,
            body: {
                "mappings": {
                    "properties": {
                        [openTrainEventVectorName]: {
                            "type": "knn_vector",
                            "dimension": openTrainEventVectorDimensions,
                        },
                        "userId": {
                            "type": "keyword"
                        }
                    }
                }
            },
        });

        console.log('Creating index:');
        console.log(response.body, ' created index')
    } catch (e) {
        console.log(e, ' unable to create index')
    }
}

export const convertEventTitleToOpenAIVector = async (
    title: string,
) => {
    try {
        const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
            model: 'text-embedding-3-small',
            input: title,
        }

        const res = await openai.embeddings.create(embeddingRequest)
        console.log(res, ' res inside convertEventTitleToOpenAIVectors')
        return res?.data?.[0]?.embedding
    } catch (e) {
        console.log(e, ' unable to convert event title to openaivectors')
    }
}

export const createAllEventIndexInOpenSearch = async () => {
    try {
        const client = await getSearchClient()

        const response = await client.indices.create({
            index: openAllEventIndex,
            body: {
                "mappings": {
                    "properties": {
                        [openAllEventVectorName]: {
                            "type": "knn_vector",
                            "dimension": openAllEventVectorDimensions,
                        },
                        "userId": {
                            "type": "keyword"
                        },
                        "start_date": {
                            "type": "date"
                        },
                        "end_date": {
                            "type": "date"
                        }
                    }
                }
            },
        });

        console.log('Creating index:');
        console.log(response.body, ' created index')
    } catch (e) {
        console.log(e, ' unable to create index')
    }
}


export const convertQuestionToOpenAIVectors = async (
    question: string,
    openai: OpenAI,
) => {
    try {
        const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
            model: 'text-embedding-3-small',
            input: question,
        }

        const res = await openai.embeddings.create(embeddingRequest)
        console.log(res, ' res inside convertQuestionToOpenAIVectors')
        return res?.data?.[0]?.embedding
    } catch (e) {
        console.log(e, ' unable to convert question to openaivectors')
    }
}


/**
 * response:
 * {
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "\n\nHello there, how may I assist you today?",
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}

 */
export const callOpenAIWithMessageHistory = async (
    openai: OpenAI,
    messageHistory: CreateChatCompletionRequestMessage[] = [],
    prompt: string,
    model: 'gpt-3.5-turbo' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: messageHistory.concat([
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ])
            ?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return { totalTokenCount: completion?.usage?.total_tokens, response: completion?.choices?.[0]?.message?.content}
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
    }
}
export const callOpenAI = async (
    openai: OpenAI,
    prompt: string,
    model: 'gpt-3.5-turbo' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: [
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ]?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return completion?.choices?.[0]?.message?.content
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
    }
}




