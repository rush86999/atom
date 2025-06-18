import { defaultOpenAIAPIKey, openAllEventIndex, openSearchEndPoint, openAllEventVectorName } from "@google_calendar_sync/_libs/constants";
import OpenAI from "openai"

import { Client } from '@opensearch-project/opensearch';
import { Config, ConfigurationOptions, AWSError } from "aws-sdk";
import { APIVersions } from "aws-sdk/lib/config";
import { ConfigurationServicePlaceholders } from "aws-sdk/lib/config_service_placeholders";
import { BulkImportBodyType, OpenSearchResponseBodyType } from "../types/event2Vectors/types";



const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
})

export const convertEventTitleToOpenAIVector = async (
    title: string,
) => {
    try {
        const embeddingRequest:  OpenAI.Embeddings.EmbeddingCreateParams = {
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

export const listAllEventWithEventOpenSearch = async (
    userId: string,
    qVector: number[],
    startDate: string,
    endDate: string,
): Promise<OpenSearchResponseBodyType> => {
    try {
        const client = await getSearchClient()
        console.log(qVector, ' qVector')
        if (typeof qVector[0] !== 'number') {
            throw new Error('qVector is not a number')
        }

        const filter_conditions = {
            "bool": {
                "must": [
                    { "term": { "userId": userId } },
                    { "range": { "start_date": { "gte": startDate, "lte": endDate } } },
                    { "range": { "end_date": { "gte": startDate, "lte": endDate } } }
                ]
            }
        }

        const response = await client.search({
            index: openAllEventIndex,
            body: {
                "size": 10,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": filter_conditions
                            }
                        },
                        "script": {
                            "lang": "knn",
                            "source": "knn_score",
                            "params": {
                                "field": openAllEventVectorName,
                                "query_value": qVector,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                },
                sort: [
                    {
                        start_date: {
                            order: "asc"
                        }
                    }
                ],
                "min_score": 1.2
            }
        })
        console.log(response, ' search data in search engine')
        return response.body
    } catch (e) {
        console.log(e, ' unable to search data')
    }
}



