"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useDataFetching = void 0;
const react_1 = require("react");
/**
 * A custom hook to abstract the logic for fetching data from an API endpoint.
 * It simplifies state management for data, loading, and error states.
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
     * A memoized function to fetch data from a given API endpoint.
     *
     * @param {string} url - The URL of the API endpoint to fetch data from.
     * @param {RequestInit} [options] - Optional request options for the fetch call.
     */
    const fetchData = (0, react_1.useCallback)(async (url, options) => {
        setState((prevState) => ({ ...prevState, loading: true, error: null }));
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`API call failed: ${response.statusText}`);
            }
            const data = await response.json();
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
    }, []); // The function is memoized and doesn't depend on any external state.
    return { ...state, fetchData };
};
exports.useDataFetching = useDataFetching;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlRGF0YUZldGNoaW5nLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXNlRGF0YUZldGNoaW5nLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUE4QztBQWE5Qzs7Ozs7OztHQU9HO0FBQ0ksTUFBTSxlQUFlLEdBQUcsR0FBTSxFQUFFO0lBQ3JDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsUUFBUSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUF1QjtRQUN2RCxJQUFJLEVBQUUsSUFBSTtRQUNWLE9BQU8sRUFBRSxLQUFLO1FBQ2QsS0FBSyxFQUFFLElBQUk7S0FDWixDQUFDLENBQUM7SUFFSDs7Ozs7T0FLRztJQUNILE1BQU0sU0FBUyxHQUFHLElBQUEsbUJBQVcsRUFBQyxLQUFLLEVBQUUsR0FBVyxFQUFFLE9BQXFCLEVBQUUsRUFBRTtRQUN6RSxRQUFRLENBQUMsQ0FBQyxTQUFTLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxHQUFHLFNBQVMsRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDeEUsSUFBSSxDQUFDO1lBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsR0FBRyxFQUFFLE9BQU8sQ0FBQyxDQUFDO1lBQzNDLElBQUksQ0FBQyxRQUFRLENBQUMsRUFBRSxFQUFFLENBQUM7Z0JBQ2pCLE1BQU0sSUFBSSxLQUFLLENBQUMsb0JBQW9CLFFBQVEsQ0FBQyxVQUFVLEVBQUUsQ0FBQyxDQUFDO1lBQzdELENBQUM7WUFDRCxNQUFNLElBQUksR0FBTSxNQUFNLFFBQVEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztZQUN0QyxRQUFRLENBQUMsRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQztRQUNsRCxDQUFDO1FBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztZQUNiLFFBQVEsQ0FBQztnQkFDUCxJQUFJLEVBQUUsSUFBSTtnQkFDVixPQUFPLEVBQUUsS0FBSztnQkFDZCxLQUFLLEVBQ0gsR0FBRyxZQUFZLEtBQUs7b0JBQ2xCLENBQUMsQ0FBQyxHQUFHO29CQUNMLENBQUMsQ0FBQyxJQUFJLEtBQUssQ0FBQyx5Q0FBeUMsQ0FBQzthQUMzRCxDQUFDLENBQUM7UUFDTCxDQUFDO0lBQ0gsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMscUVBQXFFO0lBRTdFLE9BQU8sRUFBRSxHQUFHLEtBQUssRUFBRSxTQUFTLEVBQUUsQ0FBQztBQUNqQyxDQUFDLENBQUM7QUFuQ1csUUFBQSxlQUFlLG1CQW1DMUIiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB1c2VTdGF0ZSwgdXNlQ2FsbGJhY2sgfSBmcm9tICdyZWFjdCc7XG5cbi8qKlxuICogRGVmaW5lcyB0aGUgc2hhcGUgb2YgdGhlIHN0YXRlIG9iamVjdCBtYW5hZ2VkIGJ5IHRoZSB1c2VEYXRhRmV0Y2hpbmcgaG9vay5cbiAqXG4gKiBAdGVtcGxhdGUgVCBUaGUgdHlwZSBvZiB0aGUgZGF0YSBiZWluZyBmZXRjaGVkLlxuICovXG5pbnRlcmZhY2UgRGF0YUZldGNoaW5nU3RhdGU8VD4ge1xuICBkYXRhOiBUIHwgbnVsbDtcbiAgbG9hZGluZzogYm9vbGVhbjtcbiAgZXJyb3I6IEVycm9yIHwgbnVsbDtcbn1cblxuLyoqXG4gKiBBIGN1c3RvbSBob29rIHRvIGFic3RyYWN0IHRoZSBsb2dpYyBmb3IgZmV0Y2hpbmcgZGF0YSBmcm9tIGFuIEFQSSBlbmRwb2ludC5cbiAqIEl0IHNpbXBsaWZpZXMgc3RhdGUgbWFuYWdlbWVudCBmb3IgZGF0YSwgbG9hZGluZywgYW5kIGVycm9yIHN0YXRlcy5cbiAqXG4gKiBAdGVtcGxhdGUgVCBUaGUgZXhwZWN0ZWQgdHlwZSBvZiB0aGUgZGF0YSB0byBiZSBmZXRjaGVkLlxuICogQHJldHVybnMgQW4gb2JqZWN0IGNvbnRhaW5pbmcgdGhlIGZldGNoZWQgZGF0YSwgbG9hZGluZyBhbmQgZXJyb3Igc3RhdGVzLFxuICogICAgICAgICAgYW5kIGEgZnVuY3Rpb24gdG8gdHJpZ2dlciB0aGUgZGF0YSBmZXRjaGluZy5cbiAqL1xuZXhwb3J0IGNvbnN0IHVzZURhdGFGZXRjaGluZyA9IDxUPigpID0+IHtcbiAgY29uc3QgW3N0YXRlLCBzZXRTdGF0ZV0gPSB1c2VTdGF0ZTxEYXRhRmV0Y2hpbmdTdGF0ZTxUPj4oe1xuICAgIGRhdGE6IG51bGwsXG4gICAgbG9hZGluZzogZmFsc2UsXG4gICAgZXJyb3I6IG51bGwsXG4gIH0pO1xuXG4gIC8qKlxuICAgKiBBIG1lbW9pemVkIGZ1bmN0aW9uIHRvIGZldGNoIGRhdGEgZnJvbSBhIGdpdmVuIEFQSSBlbmRwb2ludC5cbiAgICpcbiAgICogQHBhcmFtIHtzdHJpbmd9IHVybCAtIFRoZSBVUkwgb2YgdGhlIEFQSSBlbmRwb2ludCB0byBmZXRjaCBkYXRhIGZyb20uXG4gICAqIEBwYXJhbSB7UmVxdWVzdEluaXR9IFtvcHRpb25zXSAtIE9wdGlvbmFsIHJlcXVlc3Qgb3B0aW9ucyBmb3IgdGhlIGZldGNoIGNhbGwuXG4gICAqL1xuICBjb25zdCBmZXRjaERhdGEgPSB1c2VDYWxsYmFjayhhc3luYyAodXJsOiBzdHJpbmcsIG9wdGlvbnM/OiBSZXF1ZXN0SW5pdCkgPT4ge1xuICAgIHNldFN0YXRlKChwcmV2U3RhdGUpID0+ICh7IC4uLnByZXZTdGF0ZSwgbG9hZGluZzogdHJ1ZSwgZXJyb3I6IG51bGwgfSkpO1xuICAgIHRyeSB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKHVybCwgb3B0aW9ucyk7XG4gICAgICBpZiAoIXJlc3BvbnNlLm9rKSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihgQVBJIGNhbGwgZmFpbGVkOiAke3Jlc3BvbnNlLnN0YXR1c1RleHR9YCk7XG4gICAgICB9XG4gICAgICBjb25zdCBkYXRhOiBUID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgICAgc2V0U3RhdGUoeyBkYXRhLCBsb2FkaW5nOiBmYWxzZSwgZXJyb3I6IG51bGwgfSk7XG4gICAgfSBjYXRjaCAoZXJyKSB7XG4gICAgICBzZXRTdGF0ZSh7XG4gICAgICAgIGRhdGE6IG51bGwsXG4gICAgICAgIGxvYWRpbmc6IGZhbHNlLFxuICAgICAgICBlcnJvcjpcbiAgICAgICAgICBlcnIgaW5zdGFuY2VvZiBFcnJvclxuICAgICAgICAgICAgPyBlcnJcbiAgICAgICAgICAgIDogbmV3IEVycm9yKCdBbiB1bmtub3duIGVycm9yIG9jY3VycmVkIGR1cmluZyBmZXRjaC4nKSxcbiAgICAgIH0pO1xuICAgIH1cbiAgfSwgW10pOyAvLyBUaGUgZnVuY3Rpb24gaXMgbWVtb2l6ZWQgYW5kIGRvZXNuJ3QgZGVwZW5kIG9uIGFueSBleHRlcm5hbCBzdGF0ZS5cblxuICByZXR1cm4geyAuLi5zdGF0ZSwgZmV0Y2hEYXRhIH07XG59O1xuIl19