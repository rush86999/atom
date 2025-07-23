import { useState, useCallback } from "react";

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
 * A custom hook to abstract the logic for fetching data from an API endpoint.
 * It simplifies state management for data, loading, and error states.
 *
 * @template T The expected type of the data to be fetched.
 * @returns An object containing the fetched data, loading and error states,
 *          and a function to trigger the data fetching.
 */
export const useDataFetching = <T,>() => {
  const [state, setState] = useState<DataFetchingState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  /**
   * A memoized function to fetch data from a given API endpoint.
   *
   * @param {string} url - The URL of the API endpoint to fetch data from.
   * @param {RequestInit} [options] - Optional request options for the fetch call.
   */
  const fetchData = useCallback(async (url: string, options?: RequestInit) => {
    setState((prevState) => ({ ...prevState, loading: true, error: null }));
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`API call failed: ${response.statusText}`);
      }
      const data: T = await response.json();
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState({
        data: null,
        loading: false,
        error: err instanceof Error ? err : new Error("An unknown error occurred during fetch."),
      });
    }
  }, []); // The function is memoized and doesn't depend on any external state.

  return { ...state, fetchData };
};
