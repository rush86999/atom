import { AppState } from './index';
import { Task } from '../types';

type SetState = (partial: Partial<AppState> | ((state: AppState) => Partial<AppState>)) => void;
type GetState = () => AppState;

export const withOptimisticUpdates = (
  set: SetState,
  get: GetState,
  sliceName: 'tasks' | 'notes' | 'workflows',
  apiUpdate: (item: any) => Promise<any>
) => {
  return async (id: string, updates: any) => {
    const items = get()[sliceName] as any[];
    const originalItem = items.find((i) => i.id === id);
    
    if (!originalItem) {
      console.warn(`Item with id ${id} not found in ${sliceName}`);
      return;
    }

    const updatedItem = { ...originalItem, ...updates, _optimistic: true };
    const newItems = items.map((i) => (i.id === id ? updatedItem : i));

    set({ [sliceName]: newItems } as any);

    try {
      const serverItem = await apiUpdate({ ...originalItem, ...updates });
      const currentItems = get()[sliceName] as any[];
      const finalItems = currentItems.map((i) =>
        i.id === id ? { ...serverItem, _optimistic: false } : i
      );
      set({ [sliceName]: finalItems } as any);
    } catch (error) {
      const currentItems = get()[sliceName] as any[];
      const revertedItems = currentItems.map((i) =>
        i.id === id ? originalItem : i
      );
      set({ [sliceName]: revertedItems } as any);
      console.error(`Failed to update ${sliceName}:`, error);
    }
  };
};
