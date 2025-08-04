import { useState, useCallback } from 'react';

/**
 * Defines the shape of the state object managed by the useDataFetching hook.
 *
 * @template T The type of the data being fetched.
 */
interface DataFetchingState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

/**
 * A custom hook for the desktop app to abstract data fetching logic.
 * It simplifies state management for data, loading, and error states.
 * Instead of a URL, it accepts a data-producing function.
 *
 * @template T The expected type of the data to be fetched.
 * @returns An object containing the fetched data, loading and error states,
 *          and a function to trigger the data fetching.
 */
export const useDataFetching = <T>() => {
  const [state, setState] = useState<DataFetchingState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  /**
   * A memoized function that executes a given data fetching function.
   *
   * @param {() => Promise<T>} dataFetcher - An async function that, when called,
   * returns a promise resolving to the required data.
   */
  const fetchData = useCallback(async (dataFetcher: () => Promise<T>) => {
    setState((prevState) => ({ ...prevState, loading: true, error: null }));
    try {
      const data = await dataFetcher();
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState({
        data: null,
        loading: false,
        error:
          err instanceof Error
            ? err
            : new Error('An unknown error occurred during fetch.'),
      });
    }
  }, []);

  return { ...state, fetchData };
};
