/**
 * A custom hook to abstract the logic for fetching data from an API endpoint.
 * It simplifies state management for data, loading, and error states.
 *
 * @template T The expected type of the data to be fetched.
 * @returns An object containing the fetched data, loading and error states,
 *          and a function to trigger the data fetching.
 */
export declare const useDataFetching: <T>() => {
    fetchData: (url: string, options?: RequestInit) => Promise<void>;
    data: T | null;
    loading: boolean;
    error: Error | null;
};
