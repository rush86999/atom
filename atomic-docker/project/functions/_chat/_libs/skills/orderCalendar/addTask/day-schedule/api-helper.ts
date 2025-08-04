import {
  callOpenAIWithMessageHistoryOnly,
  listEventsForUserGivenDates,
} from '@chat/_libs/api-helper';
import {
  dailyScheduleExampleInput,
  dailyScheduleExampleOutput,
  dailySchedulePrompt,
  dailyScheduleTemplate,
} from './prompts';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  defaultOpenAIAPIKey,
  openAIChatGPT35Model,
} from '@chat/_libs/constants';
import OpenAI from 'openai';
import { DailyScheduleObjectType } from './types';
import { BufferTimeType } from '@chat/_libs/types/EventType';
import { ChatGPTMessageHistoryType } from '@chat/_libs/types/ChatGPTTypes';
import {
  generateWorkTimesForUser,
  getUserPreferences,
} from '@chat/_libs/skills/askCalendar/api-helper';
import { TemplateEngine } from '@chat/_libs/template-engine';
import { ChatGPTRoleType } from '@/gpt-meeting/_libs/types/ChatGPTTypes';

const openai = new OpenAI({
  apiKey: defaultOpenAIAPIKey,
});

export const createDayScheduleForTasks = async (
  userId: string,
  tasks: string[], // make sure to add previous events inside tasks when submitting
  timezone: string,
  dayWindowStartDate: string,
  dayWindowEndDate: string,
  userCurrentTime: string,
  bufferTime?: BufferTimeType,
  startDate?: string // dayjs().format()
) => {
  try {
    // get previous events
    const previousEvents = await listEventsForUserGivenDates(
      userId,
      dayWindowStartDate,
      dayWindowEndDate
    );

    // create prompt
    // h:mm a

    const queryDateSysMessage = {
      role: 'system' as ChatGPTRoleType,
      content: dailySchedulePrompt,
    };
    const queryDateMessageHistory: ChatGPTMessageHistoryType = [];

    const queryDateUserMessage1 = {
      role: 'user' as ChatGPTRoleType,
      content: dailyScheduleExampleInput,
    };
    const queryDateAssistantMessage1 = {
      role: 'assistant' as ChatGPTRoleType,
      content: dailyScheduleExampleOutput,
    };

    // user work times
    const userPreferences = await getUserPreferences(userId);

    const workTimesObject = generateWorkTimesForUser(userPreferences, timezone);
    let userWorkTimes = '';
    for (const workTimeObject of workTimesObject) {
      userWorkTimes += `${workTimeObject?.dayOfWeek}: ${workTimeObject?.startTime} - ${workTimeObject?.endTime} \n`;
    }
    console.log(userWorkTimes, ' userWorkTimes');

    let startDateTime = startDate;

    if (startDate) {
      const startHour = dayjs(startDate).tz(timezone).hour();
      const startMinute = dayjs(startDate).tz(timezone).minute();
      if (startHour === 0 && startMinute === 0) {
        startDateTime = null;
      }
    }

    const userInput = `
            ${bufferTime?.afterEvent || bufferTime?.beforeEvent ? `Add buffer time if any time available to each task with before: ${bufferTime?.beforeEvent || '0'} min and after: ${bufferTime?.afterEvent || '0'} min with title: Buffer time` : ''}
            ${startDateTime ? `start time for tasks: ${dayjs(startDateTime).tz(timezone).format('h:mm a')}` : ''}
            tasks:
            ${tasks?.reduce((prev, curr) => `${prev}, ${curr}`, '')},
            ${previousEvents
              ?.map(
                (e) =>
                  `From ${dayjs(e?.startDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')} to ${dayjs(e?.endDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')}: ${e?.summary} ${e?.notes}`
              )
              ?.reduce((prev, curr) => `${prev}, ${curr}`, '')}
        `;
    console.log(userInput, ' userInput');
    const queryDateEngine = new TemplateEngine(dailyScheduleTemplate);
    const queryDateRendered = queryDateEngine.render({
      userCurrentTime,
      userWorkTimes: userWorkTimes,
      userInput,
    });

    const queryDateUserMessageInput = {
      role: 'user' as ChatGPTRoleType,
      content: queryDateRendered,
    };
    queryDateMessageHistory.push(
      queryDateSysMessage,
      queryDateUserMessage1,
      queryDateAssistantMessage1,
      queryDateUserMessageInput
    );
    // get res from openai
    const openAIRes = await callOpenAIWithMessageHistoryOnly(
      openai,
      queryDateMessageHistory,
      openAIChatGPT35Model
    );

    // validate openai res
    if (!openAIRes) {
      throw new Error('no openAIRes present inside createAgenda');
    }

    console.log(openAIRes, ' openAIRes');

    // create event

    // format response for all day
    /*
            format is JSON array [{"start_time": "", "end_time": "", "task": ""}]
        */

    const startIndex = openAIRes?.indexOf('[');
    const endIndex = openAIRes?.lastIndexOf(']');

    const finalString = openAIRes.slice(startIndex, endIndex + 1);

    console.log('finalString: ', finalString);

    const parsedText: DailyScheduleObjectType[] = JSON.parse(finalString);

    console.log('parsedText: ', parsedText);

    return parsedText;
  } catch (e) {
    console.log(e, ' unable to create daily schedule');
  }
};
