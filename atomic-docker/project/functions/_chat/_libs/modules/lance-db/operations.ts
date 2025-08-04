// LanceDB Operations Module
import {
  searchEvents,
  upsertEvents as lancedbUpsertEvents,
  deleteEventsByIds,
  searchTrainingEvents,
  upsertTrainingEvents,
  deleteTrainingEventsByIds,
  getEventById as getEventFromLanceDbById
} from '../../../_utils/lancedb_service';
import { EventSchema as LanceDbEventSchema, TrainingEventSchema as LanceDbTrainingEventSchema } from '../../../_utils/lancedb_service';

// Search operations
export const searchSingleEventByVectorLanceDb = async (
  userId: string,
  searchVector: number[],
): Promise<LanceDbEventSchema | null> => {
  try {
    const results = await searchEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
    return results && results.length > 0 ? results[0] : null;
  } catch (error) {
    console.error('Error in searchSingleEventByVectorLanceDb:', error);
    return null;
  }
};

export const searchSingleEventByVectorWithDatesLanceDb = async (
  userId: string,
  qVector: number[],
  startDate: string,
  endDate: string,
): Promise<LanceDbEventSchema | null> => {
  try {
    if (typeof qVector[0] !== 'number') {
      throw new Error('qVector is not a number array or is empty');
    }
    const filterCondition = `userId = '${userId.replace(/'/g, "''")}' AND start_date >= '${startDate}' AND end_date <= '${endDate}'`;
    const results = await searchEvents(qVector, 1, filterCondition);
    return results && results.length > 0 ? results[0] : null;
  } catch (error) {
    console.error('Error in searchSingleEventByVectorWithDatesLanceDb:', error);
    return null;
  }
};

export const searchMultipleEventsByVectorWithDatesLanceDb = async (
  userId: string,
  qVector: number[],
  startDate: string,
  endDate: string,
  limit: number = 10,
): Promise<LanceDbEventSchema[]> => {
  try {
    if (typeof qVector[0] !== 'number') {
      throw new Error('qVector is not a number array or is empty');
    }
    const filterCondition = `userId = '${userId.replace(/'/g, "''")}' AND start_date >= '${startDate}' AND end_date <= '${endDate}'`;
    return await searchEvents(qVector, limit, filterCondition);
  } catch (error) {
    console.error('Error in searchMultipleEventsByVectorWithDatesLanceDb:', error);
    return [];
  }
};

// Training data operations
export const getEventVectorFromLanceDb = async (id: string): Promise<number[] | null> => {
  try {
    const event = await getEventFromLanceDbById(id);
    return event?.vector || null;
  } catch (error) {
    console.error(`Error fetching event vector for ID ${id} from LanceDB:`, error);
    return null;
  }
};

export const upsertEventToLanceDb = async (
  id: string,
  vector: number[],
  userId: string,
  start_date: string,
  end_date: string,
  title: string,
): Promise<void> => {
  try {
    await lancedbUpsertEvents([{
      id,
      userId,
      vector,
      start_date,
      end_date,
      title,
    }]);
  } catch (error) {
    console.error('Error upserting event to LanceDB:', error);
  }
};

export const deleteEventFromLanceDb = async (id: string): Promise<void> => {
  try {
    await deleteEventsByIds([id]);
  } catch (error) {
    console.error('Error deleting event from LanceDB:', error);
  }
};

// Training data management
export const deleteTrainingDataFromLanceDb = async (id: string): Promise<void> => {
  try {
    await deleteTrainingEventsByIds([id]);
  } catch (error) {
    console.error('Error deleting training data from LanceDB:', error);
  }
};

export const updateTrainingDataInLanceDb = async (
  id: string,
  vector: number[],
  userId: string,
  source_event_text: string,
): Promise<void> => {
  try {
    await upsertTrainingEvents([{
      id,
      userId,
      vector,
      source_event_text,
    }]);
  } catch (error) {
    console.error('Error updating training data in LanceDB:', error);
  }
};

export const searchTrainingDataFromLanceDb = async (
  userId: string,
  qVector: number[],
  limit: number = 10,
): Promise<LanceDbTrainingEventSchema[]> => {
  try {
    return await searchTrainingEvents(qVector, limit, `userId = '${userId.replace(/'/g, "''")}'`);
  } catch (error) {
    console.error('Error searching training data from LanceDB:', error);
    return [];
  }
};
