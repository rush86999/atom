import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { streamToString } from '@post_process_calendar/_libs/api-helper';
import { bucketName, kafkaPostProcessCalGroupId, kafkaPostProcessCalTopic, } from '@post_process_calendar/_libs/constants';
import { S3Client, GetObjectCommand, DeleteObjectCommand, PutObjectCommand, } from '@aws-sdk/client-s3';
import { Kafka, logLevel } from 'kafkajs';
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
// Set the AWS Region.
const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
});
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
});
const processGetOpaPlanBody = async (body, // This is the initial S3 payload content
optaPlanSolution // This is the direct body from OptaPlanner's callback
) => {
    const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
    await producer.connect();
    const transaction = await producer.transaction();
    try {
        // Extract data from the initial S3 payload (body)
        const { singletonId, 
        // hostId: initialHostId, // hostId from initial payload might differ from OptaPlanner's solution hostId, prefer solution's
        allEvents, hostTimezone, newHostBufferTimes, newHostReminders, breaks, oldEvents, oldAttendeeEvents, isReplan, // New field
        originalGoogleEventId, // New field
        originalCalendarId, // New field
         } = body;
        // Extract data from OptaPlanner's solution
        const { timeslotList, userList, eventPartList, score, fileKey, // This is the key of the S3 object OptaPlanner read (initial payload key)
        hostId, // This is the hostId OptaPlanner used/returned in its solution
         } = optaPlanSolution;
        /**
         * TODO:
         * 1. get the opta plan
         * 2. if hard score != 0 recurse until 5 times (This is complex, for now, just check score once)
         * 3. still hard score != 0 send message to queue
         * 4. if hard score == 0, send message to queue
         */
        // Construct the S3 payload for the worker
        const workerPayload = {
            eventPartList,
            userList,
            timeslotList,
            score,
            fileKey, // Pass the original fileKey that OptaPlanner reported
            hostId, // Pass the hostId from OptaPlanner's solution
            singletonId, // From initial S3 payload
            allEvents,
            hostTimezone,
            newHostBufferTimes,
            newHostReminders,
            breaks,
            oldEvents,
            oldAttendeeEvents,
            isReplan,
            originalGoogleEventId,
            originalCalendarId,
        };
        const workerS3Key = `${hostId}/${singletonId}_processed.json`; // New S3 key for worker payload
        const params = {
            Body: JSON.stringify(workerPayload),
            Bucket: bucketName,
            Key: workerS3Key, // Use the new key
            ContentType: 'application/json',
        };
        const s3Command = new PutObjectCommand(params);
        const s3Response = await s3Client.send(s3Command);
        console.log(s3Response, ' s3Response for worker payload');
        const response = await transaction.send({
            topic: kafkaPostProcessCalTopic,
            messages: [{ value: JSON.stringify({ fileKey: workerS3Key }) }], // Point Kafka to the new S3 object
        });
        const admin = kafka.admin();
        await admin.connect();
        const partitions = await admin.fetchOffsets({
            groupId: kafkaPostProcessCalGroupId,
            topics: [kafkaPostProcessCalTopic],
        });
        console.log(partitions);
        await admin.disconnect();
        await transaction.sendOffsets({
            consumerGroupId: kafkaPostProcessCalGroupId,
            topics: [
                {
                    topic: kafkaPostProcessCalTopic,
                    partitions: partitions?.[0]?.partitions,
                },
            ],
        });
        await transaction.commit();
        console.log(response, ' response successfully added to queue inside publishToCalendarQueue');
    }
    catch (e) {
        console.log(e, ' processCalendarForOptaPlanner');
    }
};
const handler = async (req, res) => {
    try {
        console.log(req, ' event');
        // hasura trigger
        const bodyOptaPlan = req.body; // This is the direct payload from OptaPlanner
        console.log(bodyOptaPlan, ' bodyOptaPlan from OptaPlanner callback');
        const { score, fileKey, hostId: optaHostId } = bodyOptaPlan; // fileKey here is the key of the *initial* S3 payload
        // --- Score Check ---
        if (score) {
            const scoreParts = score.split('/');
            const hardScoreMatch = scoreParts[0].match(/(-?\d+)hard/);
            if (hardScoreMatch && hardScoreMatch[1]) {
                const hardScoreValue = parseInt(hardScoreMatch[1], 10);
                if (hardScoreValue < 0) {
                    // Must read singletonId from the initial S3 payload for logging.
                    // The fileKey from OptaPlanner callback IS the key to the initial S3 payload.
                    let initialSingletonId = 'UNKNOWN_SINGLETON_ID';
                    try {
                        const initialS3GetCommand = new GetObjectCommand({
                            Bucket: bucketName,
                            Key: fileKey,
                        });
                        const initialS3GetCommandOutput = await s3Client.send(initialS3GetCommand);
                        const initialBodyString = await streamToString(initialS3GetCommandOutput.Body);
                        const initialS3Body = JSON.parse(initialBodyString);
                        initialSingletonId =
                            initialS3Body.singletonId || initialSingletonId;
                    }
                    catch (s3Error) {
                        console.error(`Error reading initial S3 payload ${fileKey} for logging singletonId:`, s3Error);
                    }
                    console.error(`OptaPlanner solution for fileKey: ${fileKey}, singletonId: ${initialSingletonId} has a negative hard score (${hardScoreValue}). Aborting processing.`);
                    // It's important to delete the initial S3 file if it's no longer needed, even on failure, to prevent reprocessing or clutter.
                    // However, for debugging a hard score failure, one might want to keep it. For now, let's delete.
                    try {
                        const s3DeleteCmd = new DeleteObjectCommand({
                            Bucket: bucketName,
                            Key: fileKey,
                        });
                        await s3Client.send(s3DeleteCmd);
                        console.log(`Deleted initial S3 object ${fileKey} after negative hard score.`);
                    }
                    catch (deleteError) {
                        console.error(`Failed to delete initial S3 object ${fileKey} after negative hard score:`, deleteError);
                    }
                    return res
                        .status(200)
                        .json({
                        message: 'Acknowledged OptaPlanner callback. Negative hard score, solution not processed.',
                    });
                }
            }
            else {
                console.warn(`Could not parse hard score from score string: ${score}. Proceeding with processing.`);
            }
        }
        else {
            console.warn('OptaPlanner solution score is null or undefined. Proceeding with processing.');
        }
        // --- End Score Check ---
        if (!optaHostId) {
            // hostId from OptaPlanner's solution payload
            throw new Error('hostId from OptaPlanner solution is not provided');
        }
        if (!fileKey) {
            // fileKey of the initial S3 data object
            throw new Error('no fileKey found in OptaPlanner solution');
        }
        // The rest of the parameters from OptaPlanner's solution (timeslotList, eventPartList, userList)
        // are validated inside processGetOpaPlanBody or by its usage.
        console.log(`Initial S3 fileKey from OptaPlanner: ${fileKey}`);
        const s3GetCommand = new GetObjectCommand({
            Bucket: bucketName,
            Key: fileKey, // fileKey is the key to the *initial* S3 payload
        });
        const s3GetCommandOutput = await s3Client.send(s3GetCommand);
        const bodyString = await streamToString(s3GetCommandOutput.Body);
        const initialS3PayloadBody = JSON.parse(bodyString);
        console.log(initialS3PayloadBody, ' initialS3PayloadBody content from S3');
        // Now that we have processed the initial S3 payload, delete it.
        const s3DeleteCommand = new DeleteObjectCommand({
            Bucket: bucketName,
            Key: fileKey,
        });
        const s3DeleteCommandOutput = await s3Client.send(s3DeleteCommand);
        console.log(s3DeleteCommandOutput, ' s3DeleteCommandOutput for initial S3 payload');
        // Validate required fields from the initial S3 payload
        if (!initialS3PayloadBody?.hostId) {
            // This is hostId from the *original* data generation context
            throw new Error('hostId is required in the initial S3 payload');
        }
        else if (!initialS3PayloadBody?.singletonId) {
            throw new Error('singletonId is required in the initial S3 payload');
        }
        // eventParts and allEvents from initialS3PayloadBody are more for context if needed by worker,
        // the primary data for calendar update comes from bodyOptaPlan.eventPartList
        await processGetOpaPlanBody(initialS3PayloadBody, // Pass the content of the initial S3 payload
        bodyOptaPlan // Pass the direct solution from OptaPlanner
        );
        return res.status(202).json({
            message: 'success',
        });
    }
    catch (e) {
        console.log(e, ' postProcessCalendarOptaPlan');
        return res.status(400).json({
            message: e.message,
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoib24tb3B0YS1wbGFuLXBvc3QtcHJvY2Vzcy1jYWxlbmRhci1hZG1pbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm9uLW9wdGEtcGxhbi1wb3N0LXByb2Nlc3MtY2FsZW5kYXItYWRtaW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBRUEsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sT0FBTyxNQUFNLHNCQUFzQixDQUFDO0FBQzNDLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sU0FBUyxNQUFNLHdCQUF3QixDQUFDO0FBQy9DLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sR0FBRyxNQUFNLGtCQUFrQixDQUFDO0FBRW5DLE9BQU8sRUFBRSxjQUFjLEVBQUUsTUFBTSx5Q0FBeUMsQ0FBQztBQUN6RSxPQUFPLEVBQ0wsVUFBVSxFQUNWLDBCQUEwQixFQUMxQix3QkFBd0IsR0FDekIsTUFBTSx3Q0FBd0MsQ0FBQztBQUNoRCxPQUFPLEVBQ0wsUUFBUSxFQUNSLGdCQUFnQixFQUNoQixtQkFBbUIsRUFDbkIsZ0JBQWdCLEdBQ2pCLE1BQU0sb0JBQW9CLENBQUM7QUFXNUIsT0FBTyxFQUFFLEtBQUssRUFBRSxRQUFRLEVBQUUsTUFBTSxTQUFTLENBQUM7QUFHMUMsS0FBSyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQztBQUNsQixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDdEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLFNBQVMsQ0FBQyxDQUFDO0FBQ3hCLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFDdkIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQztBQUVsQixzQkFB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Q2hELENBQUM7UUFFRix1REFBdUQ7UUFDdkQsSUFBSSxDQUFDLG9CQUFvQixFQUFFLE1BQU0sRUFBRSxDQUFDO1lBQ2xDLDZEQUE2RDtZQUM3RCxNQUFNLElBQUksS0FBSyxDQUFDLDhDQUE4QyxDQUFDLENBQUM7UUFDbEUsQ0FBQzthQUFNLElBQUksQ0FBQyxvQkFBb0IsRUFBRSxXQUFXLEVBQUUsQ0FBQztZQUM5QyxNQUFNLElBQUksS0FBSyxDQUFDLG1EQUFtRCxDQUFDLENBQUM7UUFDdkUsQ0FBQztRQUNELCtGQUErRjtRQUMvRiw2RUFBNkU7UUFFN0UsTUFBTSxxQkFBcUIsQ0FDekIsb0JBQW9CLEVBQUUsNkNBQTZDO1FBQ25FLFlBQVksQ0FBQyw0Q0FBNEM7U0FDMUQsQ0FBQztRQUNGLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsT0FBTyxFQUFFLFNBQVM7U0FDbkIsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw4QkFBOEIsQ0FBQyxDQUFDO1FBQy9DLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsT0FBTyxFQUFFLENBQUMsQ0FBQyxPQUFPO1NBQ25CLENBQUMsQ0FBQztJQUNMLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFJlcXVlc3QsIFJlc3BvbnNlIH0gZnJvbSAnZXhwcmVzcyc7XG5cbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2Vlayc7XG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJztcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2Vlbic7XG5pbXBvcnQgdGltZXpvbmUgZnJvbSAnZGF5anMvcGx1Z2luL3RpbWV6b25lJztcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0Yyc7XG5cbmltcG9ydCB7IHN0cmVhbVRvU3RyaW5nIH0gZnJvbSAnQHBvc3RfcHJvY2Vzc19jYWxlbmRhci9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7XG4gIGJ1Y2tldE5hbWUsXG4gIGthZmthUG9zdFByb2Nlc3NDYWxHcm91cElkLFxuICBrYWZrYVBvc3RQcm9jZXNzQ2FsVG9waWMsXG59IGZyb20gJ0Bwb3N0X3Byb2Nlc3NfY2FsZW5kYXIvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIFMzQ2xpZW50LFxuICBHZXRPYmplY3RDb21tYW5kLFxuICBEZWxldGVPYmplY3RDb21tYW5kLFxuICBQdXRPYmplY3RDb21tYW5kLFxufSBmcm9tICdAYXdzLXNkay9jbGllbnQtczMnO1xuXG5pbXBvcnQgeyBSZWFkYWJsZSB9IGZyb20gJ3N0cmVhbSc7XG5pbXBvcnQgeyBHZXRPcHRhUGxhbkJvZHlGb3JDYWxlbmRhclR5cGUgfSBmcm9tICdAcG9zdF9wcm9jZXNzX2NhbGVuZGFyL19saWJzL3R5cGVzL29uUG9zdE9wdGFDYWwvdHlwZXMnO1xuaW1wb3J0IHtcbiAgRXZlbnRQbGFubmVyUmVzcG9uc2VCb2R5VHlwZSxcbiAgT25PcHRhUGxhbkJvZHlUeXBlLFxuICBUaW1lU2xvdFR5cGUsXG4gIFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBXb3JrZXJTM1BheWxvYWRUeXBlLFxufSBmcm9tICdAcG9zdF9wcm9jZXNzX2NhbGVuZGFyL19saWJzL3R5cGVzJzsgLy8gQWRkZWQgV29ya2VyUzNQYXlsb2FkVHlwZVxuaW1wb3J0IHsgS2Fma2EsIGxvZ0xldmVsIH0gZnJvbSAna2Fma2Fqcyc7XG5pbXBvcnQgaXAgZnJvbSAnaXAnO1xuXG5kYXlqcy5leHRlbmQodXRjKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQoaXNvV2Vlayk7XG5kYXlqcy5leHRlbmQoZHVyYXRpb24pO1xuZGF5anMuZXh0ZW5kKGlzQmV0d2Vlbik7XG5kYXlqcy5leHRlbmQodGltZXpvbmUpO1xuZGF5anMuZXh0ZW5kKHV0Yyk7XG5cbi8vIFNldCB0aGUgQVdTIFJlZ2lvbi5cbmNvbnN0IHMzQ2xpZW50ID0gbmV3IFMzQ2xpZW50KHtcbiAgY3JlZGVudGlhbHM6IHtcbiAgICBhY2Nlc3NLZXlJZDogcHJvY2Vzcy5lbnYuUzNfQUNDRVNTX0tFWSxcbiAgICBzZWNyZXRBY2Nlc3NLZXk6IHByb2Nlc3MuZW52LlMzX1NFQ1JFVF9LRVksXG4gIH0sXG4gIGVuZHBvaW50OiBwcm9jZXNzLmVudi5TM19FTkRQT0lOVCxcbiAgZm9yY2VQYXRoU3R5bGU6IHRydWUsXG59KTtcblxuY29uc3Qga2Fma2EgPSBuZXcgS2Fma2Eoe1xuICBsb2dMZXZlbDogbG9nTGV2ZWwuREVCVUcsXG4gIGJyb2tlcnM6IFtga2Fma2ExOjI5MDkyYF0sXG4gIGNsaWVudElkOiAnYXRvbWljJyxcbiAgLy8gc3NsOiB0cnVlLFxuICBzYXNsOiB7XG4gICAgbWVjaGFuaXNtOiAncGxhaW4nLCAvLyBzY3JhbS1zaGEtMjU2IG9yIHNjcmFtLXNoYS01MTJcbiAgICB1c2VybmFtZTogcHJvY2Vzcy5lbnYuS0FGS0FfVVNFUk5BTUUsXG4gICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52LktBRktBX1BBU1NXT1JELFxuICB9LFxufSk7XG5cbmNvbnN0IHByb2Nlc3NHZXRPcGFQbGFuQm9keSA9IGFzeW5jIChcbiAgYm9keTogR2V0T3B0YVBsYW5Cb2R5Rm9yQ2FsZW5kYXJUeXBlLCAvLyBUaGlzIGlzIHRoZSBpbml0aWFsIFMzIHBheWxvYWQgY29udGVudFxuICBvcHRhUGxhblNvbHV0aW9uOiBPbk9wdGFQbGFuQm9keVR5cGUgLy8gVGhpcyBpcyB0aGUgZGlyZWN0IGJvZHkgZnJvbSBPcHRhUGxhbm5lcidzIGNhbGxiYWNrXG4pID0+IHtcbiAgY29uc3QgcHJvZHVjZXIgPSBrYWZrYS5wcm9kdWNlcih7IG1heEluRmxpZ2h0UmVxdWVzdHM6IDEsIGlkZW1wb3RlbnQ6IHRydWUgfSk7XG4gIGF3YWl0IHByb2R1Y2VyLmNvbm5lY3QoKTtcblxuICBjb25zdCB0cmFuc2FjdGlvbiA9IGF3YWl0IHByb2R1Y2VyLnRyYW5zYWN0aW9uKCk7XG4gIHRyeSB7XG4gICAgLy8gRXh0cmFjdCBkYXRhIGZyb20gdGhlIGluaXRpYWwgUzMgcGF5bG9hZCAoYm9keSlcbiAgICBjb25zdCB7XG4gICAgICBzaW5nbGV0b25JZCxcbiAgICAgIC8vIGhvc3RJZDogaW5pdGlhbEhvc3RJZCwgLy8gaG9zdElkIGZyb20gaW5pdGlhbCBwYXlsb2FkIG1pZ2h0IGRpZmZlciBmcm9tIE9wdGFQbGFubmVyJ3Mgc29sdXRpb24gaG9zdElkLCBwcmVmZXIgc29sdXRpb24nc1xuICAgICAgYWxsRXZlbnRzLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzLFxuICAgICAgbmV3SG9zdFJlbWluZGVycyxcbiAgICAgIGJyZWFrcyxcbiAgICAgIG9sZEV2ZW50cyxcbiAgICAgIG9sZEF0dGVuZGVlRXZlbnRzLFxuICAgICAgaXNSZXBsYW4sIC8vIE5ldyBmaWVsZFxuICAgICAgb3JpZ2luYWxHb29nbGVFdmVudElkLCAvLyBOZXcgZmllbGRcbiAgICAgIG9yaWdpbmFsQ2FsZW5kYXJJZCwgLy8gTmV3IGZpZWxkXG4gICAgfSA9IGJvZHk7XG5cbiAgICAvLyBFeHRyYWN0IGRhdGEgZnJvbSBPcHRhUGxhbm5lcidzIHNvbHV0aW9uXG4gICAgY29uc3Qge1xuICAgICAgdGltZXNsb3RMaXN0LFxuICAgICAgdXNlckxpc3QsXG4gICAgICBldmVudFBhcnRMaXN0LFxuICAgICAgc2NvcmUsXG4gICAgICBmaWxlS2V5LCAvLyBUaGlzIGlzIHRoZSBrZXkgb2YgdGhlIFMzIG9iamVjdCBPcHRhUGxhbm5lciByZWFkIChpbml0aWFsIHBheWxvYWQga2V5KVxuICAgICAgaG9zdElkLCAvLyBUaGlzIGlzIHRoZSBob3N0SWQgT3B0YVBsYW5uZXIgdXNlZC9yZXR1cm5lZCBpbiBpdHMgc29sdXRpb25cbiAgICB9ID0gb3B0YVBsYW5Tb2x1dGlvbjtcblxuICAgIC8qKlxuICAgICAqIFRPRE86XG4gICAgICogMS4gZ2V0IHRoZSBvcHRhIHBsYW5cbiAgICAgKiAyLiBpZiBoYXJkIHNjb3JlICE9IDAgcmVjdXJzZSB1bnRpbCA1IHRpbWVzIChUaGlzIGlzIGNvbXBsZXgsIGZvciBub3csIGp1c3QgY2hlY2sgc2NvcmUgb25jZSlcbiAgICAgKiAzLiBzdGlsbCBoYXJkIHNjb3JlICE9IDAgc2VuZCBtZXNzYWdlIHRvIHF1ZXVlXG4gICAgICogNC4gaWYgaGFyZCBzY29yZSA9PSAwLCBzZW5kIG1lc3NhZ2UgdG8gcXVldWVcbiAgICAgKi9cblxuICAgIC8vIENvbnN0cnVjdCB0aGUgUzMgcGF5bG9hZCBmb3IgdGhlIHdvcmtlclxuICAgIGNvbnN0IHdvcmtlclBheWxvYWQ6IFdvcmtlclMzUGF5bG9hZFR5cGUgPSB7XG4gICAgICBldmVudFBhcnRMaXN0LFxuICAgICAgdXNlckxpc3QsXG4gICAgICB0aW1lc2xvdExpc3QsXG4gICAgICBzY29yZSxcbiAgICAgIGZpbGVLZXksIC8vIFBhc3MgdGhlIG9yaWdpbmFsIGZpbGVLZXkgdGhhdCBPcHRhUGxhbm5lciByZXBvcnRlZFxuICAgICAgaG9zdElkLCAvLyBQYXNzIHRoZSBob3N0SWQgZnJvbSBPcHRhUGxhbm5lcidzIHNvbHV0aW9uXG4gICAgICBzaW5nbGV0b25JZCwgLy8gRnJvbSBpbml0aWFsIFMzIHBheWxvYWRcbiAgICAgIGFsbEV2ZW50cyxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIG5ld0hvc3RCdWZmZXJUaW1lcyxcbiAgICAgIG5ld0hvc3RSZW1pbmRlcnMsXG4gICAgICBicmVha3MsXG4gICAgICBvbGRFdmVudHMsXG4gICAgICBvbGRBdHRlbmRlZUV2ZW50cyxcbiAgICAgIGlzUmVwbGFuLFxuICAgICAgb3JpZ2luYWxHb29nbGVFdmVudElkLFxuICAgICAgb3JpZ2luYWxDYWxlbmRhcklkLFxuICAgIH07XG5cbiAgICBjb25zdCB3b3JrZXJTM0tleSA9IGAke2hvc3RJZH0vJHtzaW5nbGV0b25JZH1fcHJvY2Vzc2VkLmpzb25gOyAvLyBOZXcgUzMga2V5IGZvciB3b3JrZXIgcGF5bG9hZFxuXG4gICAgY29uc3QgcGFyYW1zID0ge1xuICAgICAgQm9keTogSlNPTi5zdHJpbmdpZnkod29ya2VyUGF5bG9hZCksXG4gICAgICBCdWNrZXQ6IGJ1Y2tldE5hbWUsXG4gICAgICBLZXk6IHdvcmtlclMzS2V5LCAvLyBVc2UgdGhlIG5ldyBrZXlcbiAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHMzQ29tbWFuZCA9IG5ldyBQdXRPYmplY3RDb21tYW5kKHBhcmFtcyk7XG5cbiAgICBjb25zdCBzM1Jlc3BvbnNlID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0NvbW1hbmQpO1xuICAgIGNvbnNvbGUubG9nKHMzUmVzcG9uc2UsICcgczNSZXNwb25zZSBmb3Igd29ya2VyIHBheWxvYWQnKTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgdHJhbnNhY3Rpb24uc2VuZCh7XG4gICAgICB0b3BpYzoga2Fma2FQb3N0UHJvY2Vzc0NhbFRvcGljLFxuICAgICAgbWVzc2FnZXM6IFt7IHZhbHVlOiBKU09OLnN0cmluZ2lmeSh7IGZpbGVLZXk6IHdvcmtlclMzS2V5IH0pIH1dLCAvLyBQb2ludCBLYWZrYSB0byB0aGUgbmV3IFMzIG9iamVjdFxuICAgIH0pO1xuXG4gICAgY29uc3QgYWRtaW4gPSBrYWZrYS5hZG1pbigpO1xuXG4gICAgYXdhaXQgYWRtaW4uY29ubmVjdCgpO1xuICAgIGNvbnN0IHBhcnRpdGlvbnMgPSBhd2FpdCBhZG1pbi5mZXRjaE9mZnNldHMoe1xuICAgICAgZ3JvdXBJZDoga2Fma2FQb3N0UHJvY2Vzc0NhbEdyb3VwSWQsXG4gICAgICB0b3BpY3M6IFtrYWZrYVBvc3RQcm9jZXNzQ2FsVG9waWNdLFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKHBhcnRpdGlvbnMpO1xuICAgIGF3YWl0IGFkbWluLmRpc2Nvbm5lY3QoKTtcblxuICAgIGF3YWl0IHRyYW5zYWN0aW9uLnNlbmRPZmZzZXRzKHtcbiAgICAgIGNvbnN1bWVyR3JvdXBJZDoga2Fma2FQb3N0UHJvY2Vzc0NhbEdyb3VwSWQsXG4gICAgICB0b3BpY3M6IFtcbiAgICAgICAge1xuICAgICAgICAgIHRvcGljOiBrYWZrYVBvc3RQcm9jZXNzQ2FsVG9waWMsXG4gICAgICAgICAgcGFydGl0aW9uczogcGFydGl0aW9ucz8uWzBdPy5wYXJ0aXRpb25zLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICB9KTtcblxuICAgIGF3YWl0IHRyYW5zYWN0aW9uLmNvbW1pdCgpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXNwb25zZSxcbiAgICAgICcgcmVzcG9uc2Ugc3VjY2Vzc2Z1bGx5IGFkZGVkIHRvIHF1ZXVlIGluc2lkZSBwdWJsaXNoVG9DYWxlbmRhclF1ZXVlJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHByb2Nlc3NDYWxlbmRhckZvck9wdGFQbGFubmVyJyk7XG4gIH1cbn07XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAocmVxOiBSZXF1ZXN0LCByZXM6IFJlc3BvbnNlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2cocmVxLCAnIGV2ZW50Jyk7XG4gICAgLy8gaGFzdXJhIHRyaWdnZXJcbiAgICBjb25zdCBib2R5T3B0YVBsYW46IE9uT3B0YVBsYW5Cb2R5VHlwZSA9IHJlcS5ib2R5OyAvLyBUaGlzIGlzIHRoZSBkaXJlY3QgcGF5bG9hZCBmcm9tIE9wdGFQbGFubmVyXG4gICAgY29uc29sZS5sb2coYm9keU9wdGFQbGFuLCAnIGJvZHlPcHRhUGxhbiBmcm9tIE9wdGFQbGFubmVyIGNhbGxiYWNrJyk7XG5cbiAgICBjb25zdCB7IHNjb3JlLCBmaWxlS2V5LCBob3N0SWQ6IG9wdGFIb3N0SWQgfSA9IGJvZHlPcHRhUGxhbjsgLy8gZmlsZUtleSBoZXJlIGlzIHRoZSBrZXkgb2YgdGhlICppbml0aWFsKiBTMyBwYXlsb2FkXG5cbiAgICAvLyAtLS0gU2NvcmUgQ2hlY2sgLS0tXG4gICAgaWYgKHNjb3JlKSB7XG4gICAgICBjb25zdCBzY29yZVBhcnRzID0gc2NvcmUuc3BsaXQoJy8nKTtcbiAgICAgIGNvbnN0IGhhcmRTY29yZU1hdGNoID0gc2NvcmVQYXJ0c1swXS5tYXRjaCgvKC0/XFxkKyloYXJkLyk7XG4gICAgICBpZiAoaGFyZFNjb3JlTWF0Y2ggJiYgaGFyZFNjb3JlTWF0Y2hbMV0pIHtcbiAgICAgICAgY29uc3QgaGFyZFNjb3JlVmFsdWUgPSBwYXJzZUludChoYXJkU2NvcmVNYXRjaFsxXSwgMTApO1xuICAgICAgICBpZiAoaGFyZFNjb3JlVmFsdWUgPCAwKSB7XG4gICAgICAgICAgLy8gTXVzdCByZWFkIHNpbmdsZXRvbklkIGZyb20gdGhlIGluaXRpYWwgUzMgcGF5bG9hZCBmb3IgbG9nZ2luZy5cbiAgICAgICAgICAvLyBUaGUgZmlsZUtleSBmcm9tIE9wdGFQbGFubmVyIGNhbGxiYWNrIElTIHRoZSBrZXkgdG8gdGhlIGluaXRpYWwgUzMgcGF5bG9hZC5cbiAgICAgICAgICBsZXQgaW5pdGlhbFNpbmdsZXRvbklkID0gJ1VOS05PV05fU0lOR0xFVE9OX0lEJztcbiAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc3QgaW5pdGlhbFMzR2V0Q29tbWFuZCA9IG5ldyBHZXRPYmplY3RDb21tYW5kKHtcbiAgICAgICAgICAgICAgQnVja2V0OiBidWNrZXROYW1lLFxuICAgICAgICAgICAgICBLZXk6IGZpbGVLZXksXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIGNvbnN0IGluaXRpYWxTM0dldENvbW1hbmRPdXRwdXQgPVxuICAgICAgICAgICAgICBhd2FpdCBzM0NsaWVudC5zZW5kKGluaXRpYWxTM0dldENvbW1hbmQpO1xuICAgICAgICAgICAgY29uc3QgaW5pdGlhbEJvZHlTdHJpbmcgPSBhd2FpdCBzdHJlYW1Ub1N0cmluZyhcbiAgICAgICAgICAgICAgaW5pdGlhbFMzR2V0Q29tbWFuZE91dHB1dC5Cb2R5IGFzIFJlYWRhYmxlXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgY29uc3QgaW5pdGlhbFMzQm9keTogR2V0T3B0YVBsYW5Cb2R5Rm9yQ2FsZW5kYXJUeXBlID1cbiAgICAgICAgICAgICAgSlNPTi5wYXJzZShpbml0aWFsQm9keVN0cmluZyk7XG4gICAgICAgICAgICBpbml0aWFsU2luZ2xldG9uSWQgPVxuICAgICAgICAgICAgICBpbml0aWFsUzNCb2R5LnNpbmdsZXRvbklkIHx8IGluaXRpYWxTaW5nbGV0b25JZDtcbiAgICAgICAgICB9IGNhdGNoIChzM0Vycm9yKSB7XG4gICAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgICBgRXJyb3IgcmVhZGluZyBpbml0aWFsIFMzIHBheWxvYWQgJHtmaWxlS2V5fSBmb3IgbG9nZ2luZyBzaW5nbGV0b25JZDpgLFxuICAgICAgICAgICAgICBzM0Vycm9yXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgICBgT3B0YVBsYW5uZXIgc29sdXRpb24gZm9yIGZpbGVLZXk6ICR7ZmlsZUtleX0sIHNpbmdsZXRvbklkOiAke2luaXRpYWxTaW5nbGV0b25JZH0gaGFzIGEgbmVnYXRpdmUgaGFyZCBzY29yZSAoJHtoYXJkU2NvcmVWYWx1ZX0pLiBBYm9ydGluZyBwcm9jZXNzaW5nLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIEl0J3MgaW1wb3J0YW50IHRvIGRlbGV0ZSB0aGUgaW5pdGlhbCBTMyBmaWxlIGlmIGl0J3Mgbm8gbG9uZ2VyIG5lZWRlZCwgZXZlbiBvbiBmYWlsdXJlLCB0byBwcmV2ZW50IHJlcHJvY2Vzc2luZyBvciBjbHV0dGVyLlxuICAgICAgICAgIC8vIEhvd2V2ZXIsIGZvciBkZWJ1Z2dpbmcgYSBoYXJkIHNjb3JlIGZhaWx1cmUsIG9uZSBtaWdodCB3YW50IHRvIGtlZXAgaXQuIEZvciBub3csIGxldCdzIGRlbGV0ZS5cbiAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc3QgczNEZWxldGVDbWQgPSBuZXcgRGVsZXRlT2JqZWN0Q29tbWFuZCh7XG4gICAgICAgICAgICAgIEJ1Y2tldDogYnVja2V0TmFtZSxcbiAgICAgICAgICAgICAgS2V5OiBmaWxlS2V5LFxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBhd2FpdCBzM0NsaWVudC5zZW5kKHMzRGVsZXRlQ21kKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICBgRGVsZXRlZCBpbml0aWFsIFMzIG9iamVjdCAke2ZpbGVLZXl9IGFmdGVyIG5lZ2F0aXZlIGhhcmQgc2NvcmUuYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9IGNhdGNoIChkZWxldGVFcnJvcikge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgYEZhaWxlZCB0byBkZWxldGUgaW5pdGlhbCBTMyBvYmplY3QgJHtmaWxlS2V5fSBhZnRlciBuZWdhdGl2ZSBoYXJkIHNjb3JlOmAsXG4gICAgICAgICAgICAgIGRlbGV0ZUVycm9yXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgICAuc3RhdHVzKDIwMClcbiAgICAgICAgICAgIC5qc29uKHtcbiAgICAgICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICAgICAnQWNrbm93bGVkZ2VkIE9wdGFQbGFubmVyIGNhbGxiYWNrLiBOZWdhdGl2ZSBoYXJkIHNjb3JlLCBzb2x1dGlvbiBub3QgcHJvY2Vzc2VkLicsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBDb3VsZCBub3QgcGFyc2UgaGFyZCBzY29yZSBmcm9tIHNjb3JlIHN0cmluZzogJHtzY29yZX0uIFByb2NlZWRpbmcgd2l0aCBwcm9jZXNzaW5nLmBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAnT3B0YVBsYW5uZXIgc29sdXRpb24gc2NvcmUgaXMgbnVsbCBvciB1bmRlZmluZWQuIFByb2NlZWRpbmcgd2l0aCBwcm9jZXNzaW5nLidcbiAgICAgICk7XG4gICAgfVxuICAgIC8vIC0tLSBFbmQgU2NvcmUgQ2hlY2sgLS0tXG5cbiAgICBpZiAoIW9wdGFIb3N0SWQpIHtcbiAgICAgIC8vIGhvc3RJZCBmcm9tIE9wdGFQbGFubmVyJ3Mgc29sdXRpb24gcGF5bG9hZFxuICAgICAgdGhyb3cgbmV3IEVycm9yKCdob3N0SWQgZnJvbSBPcHRhUGxhbm5lciBzb2x1dGlvbiBpcyBub3QgcHJvdmlkZWQnKTtcbiAgICB9XG5cbiAgICBpZiAoIWZpbGVLZXkpIHtcbiAgICAgIC8vIGZpbGVLZXkgb2YgdGhlIGluaXRpYWwgUzMgZGF0YSBvYmplY3RcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZmlsZUtleSBmb3VuZCBpbiBPcHRhUGxhbm5lciBzb2x1dGlvbicpO1xuICAgIH1cblxuICAgIC8vIFRoZSByZXN0IG9mIHRoZSBwYXJhbWV0ZXJzIGZyb20gT3B0YVBsYW5uZXIncyBzb2x1dGlvbiAodGltZXNsb3RMaXN0LCBldmVudFBhcnRMaXN0LCB1c2VyTGlzdClcbiAgICAvLyBhcmUgdmFsaWRhdGVkIGluc2lkZSBwcm9jZXNzR2V0T3BhUGxhbkJvZHkgb3IgYnkgaXRzIHVzYWdlLlxuXG4gICAgY29uc29sZS5sb2coYEluaXRpYWwgUzMgZmlsZUtleSBmcm9tIE9wdGFQbGFubmVyOiAke2ZpbGVLZXl9YCk7XG4gICAgY29uc3QgczNHZXRDb21tYW5kID0gbmV3IEdldE9iamVjdENvbW1hbmQoe1xuICAgICAgQnVja2V0OiBidWNrZXROYW1lLFxuICAgICAgS2V5OiBmaWxlS2V5LCAvLyBmaWxlS2V5IGlzIHRoZSBrZXkgdG8gdGhlICppbml0aWFsKiBTMyBwYXlsb2FkXG4gICAgfSk7XG5cbiAgICBjb25zdCBzM0dldENvbW1hbmRPdXRwdXQgPSBhd2FpdCBzM0NsaWVudC5zZW5kKHMzR2V0Q29tbWFuZCk7XG4gICAgY29uc3QgYm9keVN0cmluZyA9IGF3YWl0IHN0cmVhbVRvU3RyaW5nKFxuICAgICAgczNHZXRDb21tYW5kT3V0cHV0LkJvZHkgYXMgUmVhZGFibGVcbiAgICApO1xuICAgIGNvbnN0IGluaXRpYWxTM1BheWxvYWRCb2R5OiBHZXRPcHRhUGxhbkJvZHlGb3JDYWxlbmRhclR5cGUgPVxuICAgICAgSlNPTi5wYXJzZShib2R5U3RyaW5nKTtcbiAgICBjb25zb2xlLmxvZyhpbml0aWFsUzNQYXlsb2FkQm9keSwgJyBpbml0aWFsUzNQYXlsb2FkQm9keSBjb250ZW50IGZyb20gUzMnKTtcblxuICAgIC8vIE5vdyB0aGF0IHdlIGhhdmUgcHJvY2Vzc2VkIHRoZSBpbml0aWFsIFMzIHBheWxvYWQsIGRlbGV0ZSBpdC5cbiAgICBjb25zdCBzM0RlbGV0ZUNvbW1hbmQgPSBuZXcgRGVsZXRlT2JqZWN0Q29tbWFuZCh7XG4gICAgICBCdWNrZXQ6IGJ1Y2tldE5hbWUsXG4gICAgICBLZXk6IGZpbGVLZXksXG4gICAgfSk7XG4gICAgY29uc3QgczNEZWxldGVDb21tYW5kT3V0cHV0ID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0RlbGV0ZUNvbW1hbmQpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgczNEZWxldGVDb21tYW5kT3V0cHV0LFxuICAgICAgJyBzM0RlbGV0ZUNvbW1hbmRPdXRwdXQgZm9yIGluaXRpYWwgUzMgcGF5bG9hZCdcbiAgICApO1xuXG4gICAgLy8gVmFsaWRhdGUgcmVxdWlyZWQgZmllbGRzIGZyb20gdGhlIGluaXRpYWwgUzMgcGF5bG9hZFxuICAgIGlmICghaW5pdGlhbFMzUGF5bG9hZEJvZHk/Lmhvc3RJZCkge1xuICAgICAgLy8gVGhpcyBpcyBob3N0SWQgZnJvbSB0aGUgKm9yaWdpbmFsKiBkYXRhIGdlbmVyYXRpb24gY29udGV4dFxuICAgICAgdGhyb3cgbmV3IEVycm9yKCdob3N0SWQgaXMgcmVxdWlyZWQgaW4gdGhlIGluaXRpYWwgUzMgcGF5bG9hZCcpO1xuICAgIH0gZWxzZSBpZiAoIWluaXRpYWxTM1BheWxvYWRCb2R5Py5zaW5nbGV0b25JZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdzaW5nbGV0b25JZCBpcyByZXF1aXJlZCBpbiB0aGUgaW5pdGlhbCBTMyBwYXlsb2FkJyk7XG4gICAgfVxuICAgIC8vIGV2ZW50UGFydHMgYW5kIGFsbEV2ZW50cyBmcm9tIGluaXRpYWxTM1BheWxvYWRCb2R5IGFyZSBtb3JlIGZvciBjb250ZXh0IGlmIG5lZWRlZCBieSB3b3JrZXIsXG4gICAgLy8gdGhlIHByaW1hcnkgZGF0YSBmb3IgY2FsZW5kYXIgdXBkYXRlIGNvbWVzIGZyb20gYm9keU9wdGFQbGFuLmV2ZW50UGFydExpc3RcblxuICAgIGF3YWl0IHByb2Nlc3NHZXRPcGFQbGFuQm9keShcbiAgICAgIGluaXRpYWxTM1BheWxvYWRCb2R5LCAvLyBQYXNzIHRoZSBjb250ZW50IG9mIHRoZSBpbml0aWFsIFMzIHBheWxvYWRcbiAgICAgIGJvZHlPcHRhUGxhbiAvLyBQYXNzIHRoZSBkaXJlY3Qgc29sdXRpb24gZnJvbSBPcHRhUGxhbm5lclxuICAgICk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAyKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6ICdzdWNjZXNzJyxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgcG9zdFByb2Nlc3NDYWxlbmRhck9wdGFQbGFuJyk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6IGUubWVzc2FnZSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==