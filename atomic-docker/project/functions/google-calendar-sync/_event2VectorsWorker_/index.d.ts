import { Event2VectorBodyType } from '../_libs/types/event2Vectors/types';
export declare const event2VectorBody: (body: Event2VectorBodyType) => Promise<void>;
export declare const processQueueMessage: (body: Event2VectorBodyType) => Promise<void>;
declare const queueWorker: (event: any) => Promise<void>;
export default queueWorker;
