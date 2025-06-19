import dayjs from 'dayjs'
import isoWeek from 'dayjs/plugin/isoWeek'
import duration from 'dayjs/plugin/duration'
import isBetween from 'dayjs/plugin/isBetween'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'


import {
  streamToString, updateAllCalendarEventsPostPlanner,
} from '@post_process_calendar/_libs/api-helper'

import { MessageQueueType, PostProcessQueueBodyForCalendarType, } from '@post_process_calendar/_libs/types/postOptaCalWorker/types'
import { EventPlannerResponseBodyType } from '@post_process_calendar/_libs/types'
import { S3Client, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { bucketName, kafkaPostProcessCalGroupId, kafkaPostProcessCalTopic } from '@post_process_calendar/_libs/constants';
import { Readable } from 'stream'
import _ from 'lodash'
import { Kafka, logLevel } from 'kafkajs'
import ip from 'ip'

dayjs.extend(isoWeek)
dayjs.extend(duration)
dayjs.extend(isBetween)
dayjs.extend(timezone)
dayjs.extend(utc)


const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
})



const kafka = new Kafka({
    logLevel: logLevel.DEBUG,
    brokers: [`kafka1:29092`],
    clientId: 'atomic',
    // ssl: true,
    sasl: {
        mechanism: 'plain', // scram-sha-256 or scram-sha-512
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
      },
})

const processPostOptaPlanQueueBody = async (
  body: PostProcessQueueBodyForCalendarType,
) => {
  try {
    const allEvents = body.allEvents
    const newBufferTimes = body?.newHostBufferTimes
    const newReminders = body?.newHostReminders
    const breaks = body?.breaks
    const plannerBodyResponse = body?.plannerBodyResponse
    const oldEvents = body?.oldEvents
    const oldAttendeeExternalEvents = body?.oldAttendeeEvents
    const hostTimezone = body?.hostTimezone
    // Extract new replan fields
    const isReplan = body?.isReplan
    const originalGoogleEventId = body?.originalGoogleEventId
    const originalCalendarId = body?.originalCalendarId

    newReminders.forEach(r => console.log(r, ' newReminders before updateAllCalendarEventsPostPlanner'))
    const eventsToUpdate: EventPlannerResponseBodyType[][] = []
    if (plannerBodyResponse?.userList?.[0]?.id) {
      const eventPartParentFiltered = _.uniqBy(plannerBodyResponse.eventPartList, 'eventId')
      for (const eventPartParent of eventPartParentFiltered) {
        const eventPartList = []
        for (const eventPartChild of plannerBodyResponse.eventPartList) {
          if (eventPartParent.eventId === eventPartChild.eventId) {
            const oldEventPart = allEvents.find(e => (e.id === eventPartChild.eventId))
            eventPartList.push({ ...eventPartChild, recurringEventId: oldEventPart?.recurringEventId })
          }
        }
        eventsToUpdate.push(eventPartList)
      }
    }

    const eventsToValidate: EventPlannerResponseBodyType[][] = []
    if (plannerBodyResponse?.userList?.[0]?.id) {
      const eventPartParentFiltered = _.uniqBy(plannerBodyResponse.eventPartList, 'groupId')
      for (const eventPartParent of eventPartParentFiltered) {
        const eventPartList = []
        for (const eventPartChild of plannerBodyResponse.eventPartList) {
          if (eventPartParent.groupId === eventPartChild.groupId) {
            const oldEventPart = allEvents.find(e => (e.id === eventPartChild.eventId))
            eventPartList.push({ ...eventPartChild, recurringEventId: oldEventPart?.recurringEventId })
          }
        }
        eventsToValidate.push(eventPartList)
      }
    }

    eventsToUpdate?.map(e => console.log(e, ' eventsToUpdate'))
    console.log(eventsToUpdate.length, ' updateEvents length ')
    await updateAllCalendarEventsPostPlanner(
      eventsToUpdate,
      eventsToValidate,
      allEvents,
      // isoWeekOfStartDates,
      oldEvents,
      hostTimezone,
      newBufferTimes,
      newReminders,
      breaks,
      oldAttendeeExternalEvents,
      // Pass new replan fields
      isReplan,
      originalGoogleEventId,
      originalCalendarId,
    )
  } catch (e) {
    console.log(e, ' processCalendarForOptaPlanner')
  }
}

const processQueueMessage = async (body: PostProcessQueueBodyForCalendarType) => {
  // find old event in database using elastic search
  // validate bodyData
  console.log(body, ' body')
  if (!body?.eventParts?.[0]?.eventId) {
    throw new Error('eventParts is required')
  }

  if (!body?.allEvents?.[0]?.id) {
    throw new Error('allEvents is required')
  }

  if (!body?.plannerBodyResponse?.userList?.[0]?.id) {
    throw new Error('plannerBodyResponse is required')
  }

  if (!body?.hostTimezone) {
    throw new Error('hostTimezone not present')
  }

  return processPostOptaPlanQueueBody(body)

}


const queueWorker = async () => {
  try {

    const consumer = kafka.consumer({ groupId: kafkaPostProcessCalGroupId })
    await consumer.connect()

    await consumer.subscribe({ topic: kafkaPostProcessCalTopic })

    await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
            console.log({
                key: message?.key?.toString(),
                value: message?.value?.toString(),
                headers: message?.headers,
            })
            // '{"fileKey":"fc5df674-b4ee-43c7-ad9e-298ae0eb6208/aed7b93e-8da4-447c-83e7-f0f0f1420226.json"}'
            const bodyData = JSON.parse(message?.value?.toString())
            const fileKey = bodyData.fileKey
            console.log(bodyData, ' bodyData')
            const s3GetCommand = new GetObjectCommand({
              Bucket: bucketName,
              Key: fileKey,
            })
      
            const s3GetCommandOutput = await s3Client.send(s3GetCommand)
            const bodyString = await streamToString(s3GetCommandOutput.Body as Readable)
      
            const body: PostProcessQueueBodyForCalendarType = JSON.parse(bodyString)
            console.log(body, ' body')
      
            const s3DeleteCommand = new DeleteObjectCommand({
              Bucket: bucketName,
              Key: fileKey,
            })
            const s3DeleteCommandOutput = await s3Client.send(s3DeleteCommand)
            console.log(s3DeleteCommandOutput, ' s3DeleteCommandOutput')
            
            return processQueueMessage(body)
        },
    })
    

  } catch (e) {
    console.log(e, ' unable to process message')

    return e
  }
}

export default queueWorker;
