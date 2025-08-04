import { EventType } from './EventType';
export type PreAndPostEventReturnType = {
    afterEvent?: EventType;
    newEvent: EventType;
    beforeEvent?: EventType;
};
