import dayjs from 'dayjs';
declare const Dayjs: any;
import { getISODay, setISODay } from 'date-fns';
import 'dayjs/locale/en';
type DayjsType = typeof Dayjs;
export { dayjs, type DayjsType as Dayjs, getISODay, setISODay };
