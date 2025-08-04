/**
 * A custom hook for the desktop app to abstract data fetching logic.
 * It simplifies state management for data, loading, and error states.
 * Instead of a URL, it accepts a data-producing function.
 *
 * @template T The expected type of the data to be fetched.
 * @returns An object containing the fetched data, loading and error states,
 *          and a function to trigger the data fetching.
 */
export declare const useDataFetching: <T>() => {
    fetchData: (dataFetcher: () => Promise<T>) => Promise<void>;
    data: T | null;
    loading: boolean;
    error: Error | null;
};
