import { dayjs } from '@lib/date-utils';
import utc from 'dayjs/plugin/utc';
import isTomorrow from 'dayjs/plugin/isTomorrow';
import axios from 'axios';

import { ApolloClient, NormalizedCacheObject } from '@apollo/client';

import { TaskStatus } from './constants';

// import { getRealmApp } from '@realm1/realm'

//
// const realm = getRealmApp()

// dayjs.extend(utc)
// dayjs.extend(isTomorrow)

export enum TableName {
  DAILY = 'Daily',
  WEEKLY = 'Weekly',
  MASTER = 'Master',
  GROCERY = 'Grocery',
}

enum AppName {
  NOTION = 'Notion',
}

type type = 'created_time' | 'last_edited_time' | 'title' | 'select';

type selectName = 'To Do' | 'Doing' | 'Done';

type select = {
  color: string;
  id: string;
  name: selectName;
};

type resultTitle = {
  annotations: {
    bold: boolean;
    code: boolean;
    color: string;
    italic: boolean;
    strikethrough: boolean;
    underline: boolean;
  };
  plain_text: string;
  text: { content: string | null; link: string | null };
  type: type;
};

type result = {
  id: string;
  properties: {
    'Date Created': {
      id: string;
      created_time: string;
      type: type;
    };
    'Date Edited': {
      id: string;
      last_edited_time: string;
      type: type;
    };
    Status: {
      id: string;
      select: select;
      type: type;
    };
    Name: {
      id: string;
      title: resultTitle[];
      type: type;
    };
  };
};

type resultData = {
  data: {
    results: result[];
  };
};

type objectResult = 'block' | 'page';

type blockText = {
  annotations: {
    bold: boolean;
    code: boolean;
    color: string;
    italic: boolean;
    strikethrough: boolean;
    underline: boolean;
  };
  plain_text: string;
  text: { content: string | null; link: string | null };
  type: type;
  href: string | null;
};

type resultBlock = {
  archived: boolean;
  created_time: string;
  has_children: boolean;
  id: string;
  last_edited_time: string;
  object: objectResult;
  to_do: {
    checked: boolean;
    text: blockText[];
  };
};

type blockData = {
  data: {
    results: resultBlock[];
  };
};

type todoResponse = {
  id: string;
  text: string;
  checked: boolean;
};

type responseData = {
  id: string;
  status: selectName;
  title: string;
  created_time: string;
  last_edited_time: string;
  list?: todoResponse[];
};

// blockData?.data?.results'

// data.results[2].properties

// type taskType = 'Daily'|'Weekly'|'Master'|'Grocery'

const CALENDARNAME = 'Atomic Calendar';

const statusKey = {
  'To Do': TaskStatus.TODO,
  Doing: TaskStatus.DOING,
  Done: TaskStatus.DONE,
};

export const deleteNotionBlock = async (tableName: string, syncId: string) => {
  try {
    // const integration = await getIntegrationInfo(AppName.NOTION, tableName)
    // const url = `https://api.notion.com/v1/blocks/${syncId}`
    // const config = {
    //   headers: {
    //     Authorization: `Bearer ${integration?.token}`,
    //     'Content-Type': 'application/json',
    //     'Notion-Version': '2021-08-16',
    //   },
    // }
    // await axios.delete(url, config)
  } catch (e: any) {
    console.log(e, ' unable to delete notion db');
    console.log(
      e.response.data,
      ' error.response.data unable to delete notion db'
    );
    console.log(
      e.response.status,
      ' error.response.status unable to delete notion db'
    );
    console.log(
      e.response.headers,
      ' error.response.headers unable to delete notion db'
    );
  }
};

export const createTaskInStore = async (
  userId: string,
  type: TableName,
  notes?: string,
  date?: string,
  nextDay?: boolean,
  event?: boolean,
  syncId?: string,
  syncName?: string,
  startDate?: string,
  endDate?: string,
  status?: TaskStatus,
  parentId?: string,
  order?: number
) => {
  try {
  } catch (e) {
    console.log(e, ' unable to create task in store');
  }
};

export const updateTaskInStore = async (
  type: TableName,
  id: string,
  notes?: string,
  date?: string,
  event?: boolean,
  completed?: boolean,
  startDate?: string,
  endDate?: string,
  completedDate?: string,
  scheduleId?: string,
  softDeadline?: string,
  hardDeadline?: string,
  important?: boolean,
  status?: TaskStatus,
  parentId?: string,
  order?: number,
  eventId?: string,
  duration?: number
) => {
  console.log(
    type,
    id,
    parentId,
    ' type, id, parentId inside updatetaskinstore'
  );
  try {
  } catch (e) {
    console.log(e, ' unable to update task in store');
  }
};

export const processTaskFromNotion = async (
  results: responseData[],
  type: TableName,
  sub: string,
  client: ApolloClient<NormalizedCacheObject>
) => {
  console.log(results, ' results');
  // temp

  try {
    if (!results?.[0]?.id) {
      return;
    }

    const promises = results.map(async (responseData) => {});

    await Promise.all(promises);
  } catch (e) {
    console.log(e, ' unable to process task ');
  }
};

export const updateTaskNote = async (
  type: TableName,
  id: string,
  notes?: string,
  oldDate?: string,
  noteDate?: string,
  status?: selectName,
  oldEvent?: boolean,
  oldCompleted?: boolean,
  oldStartDate?: string,
  oldEndDate?: string,
  oldCompletedDate?: string,
  eventId?: string,
  duration?: number
) => {
  // don't update if oldDate is after noteDate
  if (dayjs(oldDate).isAfter(dayjs(noteDate))) {
    return;
  }

  try {
    if (!notes) {
      console.log(notes, ' no notes present updateTaskNotes');
      return;
    }

    // console.log('previous startDate and extractedRruleString does not exist inside updateTaskNotes')
    const newDate = dayjs().format();

    return updateTaskInStore(
      type,
      id,
      notes,
      newDate,
      oldEvent,
      oldCompleted,
      oldStartDate,
      oldEndDate,
      oldCompletedDate,
      undefined,
      undefined,
      undefined,
      undefined,
      statusKey[status],
      undefined,
      undefined,
      eventId,
      duration
    );
  } catch (e) {
    console.log(e, ' unable to update task note inside integration helper');
  }
};

export const createTaskNote = async (
  type: TableName,
  notes: string,
  syncId: string,
  syncName: string,
  userId: string,
  status: selectName,
  parentId?: string
) => {
  try {
    if (!notes) {
      return;
    }

    const newDate = dayjs().format();

    const taskId = await createTaskInStore(
      userId,
      type,
      notes,
      newDate,
      false,
      false,
      syncId,
      syncName,
      '',
      '',
      statusKey[status],
      parentId
    );
    return taskId;
  } catch (e) {
    console.log(e, ' unable to create task note in integration helper');
  }
};

export const queryNotionDB = async (integration: any) => {
  try {
    console.log(integration, ' integration inside queryNotionDB');
    if (!integration?.id) {
      return;
    }
    const url = `https://api.notion.com/v1/databases/${integration?.resourceId}/query`;
    const config = {
      headers: {
        Authorization: `Bearer ${integration?.token}`,
        'Content-Type': 'application/json',
        'Notion-Version': '2021-08-16',
      },
    };
    const data = {
      sorts: [
        {
          property: 'Last Edited',
          direction: 'descending',
        },
      ],
    };

    const resultData: resultData = await axios.post(url, data, config);

    const responseData: responseData[] = [];

    if (resultData?.data?.results[0]?.id) {
      const { data } = resultData;
      console.log(data, ' data from query NotionDB');
      console.log(data.results, ' results from query NotionDB');
      console.log(
        data.results?.[2]?.properties,
        ' results?.[2]?.properties from query NotionDB'
      );
      console.log(
        data.results?.[2]?.properties?.Name?.title[0]?.text,
        ' results?.[2].properties?.Name?.title[0]?.text from query NotionDB'
      );

      const { results } = data;
      for (let i = 0; i < results.length; i++) {
        const { properties, id: resultId } = results[i];

        const status = properties?.Status?.select?.name;
        const title = properties?.Name?.title?.[0]?.plain_text;
        const created_time = properties?.['Date Created']?.created_time;
        const last_edited_time = properties?.['Date Edited']?.last_edited_time;

        const blockUrl = `https://api.notion.com/v1/blocks/${resultId}/children?page_size=100`;

        const blockData: blockData = await axios.get(blockUrl, config);
        console.log(blockData, ' blockData');
        if (blockData?.data?.results?.[0]?.id) {
          console.log(blockData?.data?.results, ' blockData?.data?.results');
          const blockResults = blockData.data.results;
          const filteredToDos = blockResults.filter(
            (i: any) => i.type === 'to_do'
          );

          console.log(filteredToDos, ' filteredToDos');
          console.log(
            filteredToDos[0]?.to_do?.text,
            ' filteredToDos[0][to_do].text'
          );
          console.log(
            filteredToDos[0]?.to_do?.text[0]?.plain_text,
            ' filteredToDos[0][to_do].text[0].plain_text'
          );
          if (filteredToDos.length > 0) {
            const list: todoResponse[] = filteredToDos.map((i) => {
              const { to_do, id } = i;
              const { checked, text } = to_do;
              return {
                checked,
                text: text?.[0]?.plain_text,
                id,
              };
            });

            responseData.push({
              id: resultId,
              status,
              title,
              list,
              created_time,
              last_edited_time,
            });
          } else {
            responseData.push({
              id: resultId,
              status,
              title,
              created_time,
              last_edited_time,
            });
          }
        }
      }
      console.log(responseData, ' responseData created');
      return responseData;
    }
    return;
  } catch (e: any) {
    console.log(e, ' unable to query notion db');

    console.log(
      e.response.data,
      ' error.response.data unable to query notion db'
    );
    console.log(
      e.response.status,
      ' error.response.status unable to query notion db'
    );
    console.log(
      e.response.headers,
      ' error.response.headers unable to query notion db'
    );
  }
};
