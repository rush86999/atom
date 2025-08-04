import { MessageQueueType } from '@schedule_assist/_libs/types/scheduleMeetingWorker/types';
declare const scheduleMeetingWorker: (event: {
    Records: MessageQueueType[];
}) => Promise<void>;
export default scheduleMeetingWorker;
