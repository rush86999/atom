import { MessageQueueType } from '@schedule_event/_libs/types/scheduleEventShortWorker/types';
declare const scheduleEventWorker: (event: {
    Records: MessageQueueType[];
}) => Promise<void>;
export default scheduleEventWorker;
