interface TimeslotDto {
    hostId?: string;
    dayOfWeek?: string;
    startTime?: string;
    endTime?: string;
    monthDay?: string;
}
interface UserDto {
    id?: string;
    hostId?: string;
}
interface EventDto {
    id?: string;
    userId?: string;
    hostId?: string;
    summary?: string;
    title?: string;
    description?: string;
    preferredTimeRanges?: any[] | null;
}
export interface EventPartDto {
    id?: string;
    groupId?: string;
    eventId?: string;
    event?: EventDto;
    user?: UserDto;
    timeslot?: TimeslotDto | null;
    scheduled?: boolean;
}
export interface TimeTableSolutionDto {
    timeslotList?: TimeslotDto[];
    userList?: UserDto[];
    eventPartList: EventPartDto[];
    score: string | null;
    fileKey: string | null;
    hostId: string | null;
}
interface Request {
    body: any;
    headers: Record<string, string | string[] | undefined>;
}
interface Response {
    status: (code: number) => Response;
    send: (body?: any) => Response;
    json: (body?: any) => Response;
    end: () => void;
}
export declare function handleSchedulerCallback(req: Request, res: Response): Promise<void>;
export {};
