"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useDataFetching = void 0;
const react_1 = require("react");
/**
 * A custom hook for the desktop app to abstract data fetching logic.
 * It simplifies state management for data, loading, and error states.
 * Instead of a URL, it accepts a data-producing function.
 *
 * @template T The expected type of the data to be fetched.
 * @returns An object containing the fetched data, loading and error states,
 *          and a function to trigger the data fetching.
 */
const useDataFetching = () => {
    const [state, setState] = (0, react_1.useState)({
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
    const fetchData = (0, react_1.useCallback)(async (dataFetcher) => {
        setState((prevState) => ({ ...prevState, loading: true, error: null }));
        try {
            const data = await dataFetcher();
            setState({ data, loading: false, error: null });
        }
        catch (err) {
            setState({
                data: null,
                loading: false,
                error: err instanceof Error
                    ? err
                    : new Error('An unknown error occurred during fetch.'),
            });
        }
    }, []);
    return { ...state, fetchData };
};
exports.useDataFetching = useDataFetching;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlRGF0YUZldGNoaW5nLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXNlRGF0YUZldGNoaW5nLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUE4QztBQWE5Qzs7Ozs7Ozs7R0FRRztBQUNJLE1BQU0sZUFBZSxHQUFHLEdBQU0sRUFBRTtJQUNyQyxNQUFNLENBQUMsS0FBSyxFQUFFLFFBQVEsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBdUI7UUFDdkQsSUFBSSxFQUFFLElBQUk7UUFDVixPQUFPLEVBQUUsS0FBSztRQUNkLEtBQUssRUFBRSxJQUFJO0tBQ1osQ0FBQyxDQUFDO0lBRUg7Ozs7O09BS0c7SUFDSCxNQUFNLFNBQVMsR0FBRyxJQUFBLG1CQUFXLEVBQUMsS0FBSyxFQUFFLFdBQTZCLEVBQUUsRUFBRTtRQUNwRSxRQUFRLENBQUMsQ0FBQyxTQUFTLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxHQUFHLFNBQVMsRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDeEUsSUFBSSxDQUFDO1lBQ0gsTUFBTSxJQUFJLEdBQUcsTUFBTSxXQUFXLEVBQUUsQ0FBQztZQUNqQyxRQUFRLENBQUMsRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQztRQUNsRCxDQUFDO1FBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztZQUNiLFFBQVEsQ0FBQztnQkFDUCxJQUFJLEVBQUUsSUFBSTtnQkFDVixPQUFPLEVBQUUsS0FBSztnQkFDZCxLQUFLLEVBQ0gsR0FBRyxZQUFZLEtBQUs7b0JBQ2xCLENBQUMsQ0FBQyxHQUFHO29CQUNMLENBQUMsQ0FBQyxJQUFJLEtBQUssQ0FBQyx5Q0FBeUMsQ0FBQzthQUMzRCxDQUFDLENBQUM7UUFDTCxDQUFDO0lBQ0gsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBRVAsT0FBTyxFQUFFLEdBQUcsS0FBSyxFQUFFLFNBQVMsRUFBRSxDQUFDO0FBQ2pDLENBQUMsQ0FBQztBQS9CVyxRQUFBLGVBQWUsbUJBK0IxQiIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVzZVN0YXRlLCB1c2VDYWxsYmFjayB9IGZyb20gJ3JlYWN0JztcblxuLyoqXG4gKiBEZWZpbmVzIHRoZSBzaGFwZSBvZiB0aGUgc3RhdGUgb2JqZWN0IG1hbmFnZWQgYnkgdGhlIHVzZURhdGFGZXRjaGluZyBob29rLlxuICpcbiAqIEB0ZW1wbGF0ZSBUIFRoZSB0eXBlIG9mIHRoZSBkYXRhIGJlaW5nIGZldGNoZWQuXG4gKi9cbmludGVyZmFjZSBEYXRhRmV0Y2hpbmdTdGF0ZTxUPiB7XG4gIGRhdGE6IFQgfCBudWxsO1xuICBsb2FkaW5nOiBib29sZWFuO1xuICBlcnJvcjogRXJyb3IgfCBudWxsO1xufVxuXG4vKipcbiAqIEEgY3VzdG9tIGhvb2sgZm9yIHRoZSBkZXNrdG9wIGFwcCB0byBhYnN0cmFjdCBkYXRhIGZldGNoaW5nIGxvZ2ljLlxuICogSXQgc2ltcGxpZmllcyBzdGF0ZSBtYW5hZ2VtZW50IGZvciBkYXRhLCBsb2FkaW5nLCBhbmQgZXJyb3Igc3RhdGVzLlxuICogSW5zdGVhZCBvZiBhIFVSTCwgaXQgYWNjZXB0cyBhIGRhdGEtcHJvZHVjaW5nIGZ1bmN0aW9uLlxuICpcbiAqIEB0ZW1wbGF0ZSBUIFRoZSBleHBlY3RlZCB0eXBlIG9mIHRoZSBkYXRhIHRvIGJlIGZldGNoZWQuXG4gKiBAcmV0dXJucyBBbiBvYmplY3QgY29udGFpbmluZyB0aGUgZmV0Y2hlZCBkYXRhLCBsb2FkaW5nIGFuZCBlcnJvciBzdGF0ZXMsXG4gKiAgICAgICAgICBhbmQgYSBmdW5jdGlvbiB0byB0cmlnZ2VyIHRoZSBkYXRhIGZldGNoaW5nLlxuICovXG5leHBvcnQgY29uc3QgdXNlRGF0YUZldGNoaW5nID0gPFQ+KCkgPT4ge1xuICBjb25zdCBbc3RhdGUsIHNldFN0YXRlXSA9IHVzZVN0YXRlPERhdGFGZXRjaGluZ1N0YXRlPFQ+Pih7XG4gICAgZGF0YTogbnVsbCxcbiAgICBsb2FkaW5nOiBmYWxzZSxcbiAgICBlcnJvcjogbnVsbCxcbiAgfSk7XG5cbiAgLyoqXG4gICAqIEEgbWVtb2l6ZWQgZnVuY3Rpb24gdGhhdCBleGVjdXRlcyBhIGdpdmVuIGRhdGEgZmV0Y2hpbmcgZnVuY3Rpb24uXG4gICAqXG4gICAqIEBwYXJhbSB7KCkgPT4gUHJvbWlzZTxUPn0gZGF0YUZldGNoZXIgLSBBbiBhc3luYyBmdW5jdGlvbiB0aGF0LCB3aGVuIGNhbGxlZCxcbiAgICogcmV0dXJucyBhIHByb21pc2UgcmVzb2x2aW5nIHRvIHRoZSByZXF1aXJlZCBkYXRhLlxuICAgKi9cbiAgY29uc3QgZmV0Y2hEYXRhID0gdXNlQ2FsbGJhY2soYXN5bmMgKGRhdGFGZXRjaGVyOiAoKSA9PiBQcm9taXNlPFQ+KSA9PiB7XG4gICAgc2V0U3RhdGUoKHByZXZTdGF0ZSkgPT4gKHsgLi4ucHJldlN0YXRlLCBsb2FkaW5nOiB0cnVlLCBlcnJvcjogbnVsbCB9KSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCBkYXRhRmV0Y2hlcigpO1xuICAgICAgc2V0U3RhdGUoeyBkYXRhLCBsb2FkaW5nOiBmYWxzZSwgZXJyb3I6IG51bGwgfSk7XG4gICAgfSBjYXRjaCAoZXJyKSB7XG4gICAgICBzZXRTdGF0ZSh7XG4gICAgICAgIGRhdGE6IG51bGwsXG4gICAgICAgIGxvYWRpbmc6IGZhbHNlLFxuICAgICAgICBlcnJvcjpcbiAgICAgICAgICBlcnIgaW5zdGFuY2VvZiBFcnJvclxuICAgICAgICAgICAgPyBlcnJcbiAgICAgICAgICAgIDogbmV3IEVycm9yKCdBbiB1bmtub3duIGVycm9yIG9jY3VycmVkIGR1cmluZyBmZXRjaC4nKSxcbiAgICAgIH0pO1xuICAgIH1cbiAgfSwgW10pO1xuXG4gIHJldHVybiB7IC4uLnN0YXRlLCBmZXRjaERhdGEgfTtcbn07XG4iXX0=