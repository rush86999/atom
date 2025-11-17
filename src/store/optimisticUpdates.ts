import { AppState } from './index';
import { Task } from '../types';

type SetState = (partial: Partial<AppState>) => void;
type GetState = () => AppState;

export const withOptimisticUpdates = (
  set: SetState,
  get: GetState,
  sliceName: keyof AppState,
  apiUpdate: (item: any) => Promise<any>
) => async (item: any) => {
  const originalItems = get()[sliceName] as any[];
  const updatedItem = { ...item, _optimistic: true };

  const newItems = originalItems.map((i: any) =>
    i.id === item.id ? updatedItem : i
  );

  set({ [sliceName]: newItems } as Partial<AppState>);

  try {
    const serverItem = await apiUpdate(item);
    const currentItems = get()[sliceName] as any[];
    const finalItems = currentItems.map((i: any) =>
      i.id === item.id ? serverItem : i
    );
    set({ [sliceName]: finalItems } as Partial<AppState>);
  } catch (error) {
    const currentItems = get()[sliceName] as any[];
    const revertedItems = currentItems.map((i: any) =>
      i.id === item.id ? originalItems.find(o => o.id === i.id) : i
    );
    set({ [sliceName]: revertedItems } as Partial<AppState>);
    // Optionally, notify the user of the conflict
  }
};
