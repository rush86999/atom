import { EventType } from "./EventType";

export type PreAndPostEventReturnType = {
  preEvent?: EventType;
  postEvent?: EventType;
  newEvent?: EventType;
  preEventId?: string;
  postEventId?: string;
};
