"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseSearchQueryWithLLM = parseSearchQueryWithLLM;
const llmUtils_1 = require("../lib/llmUtils"); // Assuming this is the path
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
const llmService = new llmUtils_1.OpenAIGroqService_Stub(process.env.GROQ_API_KEY); // Or however API key is managed
/**
 * Takes a user's raw natural language search query and uses an LLM to parse it
 * into a clean search term and a structured filters object.
 *
 * @param rawQuery The user's original search query string.
 * @returns A promise that resolves to a ParsedSearchQuery object.
 *          In case of parsing failure, it gracefully falls back to returning
 *          the original query as the search term and an empty filters object.
 */
async function parseSearchQueryWithLLM(rawQuery) {
    const fallbackResponse = {
        search_term: rawQuery,
        filters: {},
    };
    const currentDate = new Date().toISOString().split('T')[0]; // Get YYYY-MM-DD
    const prompt = {
        task: 'parse_search_query',
        data: {
            rawQuery: rawQuery,
            currentDate: currentDate,
        },
    };
    try {
        const llmResponse = await llmService.generate(prompt, 'llama3-8b-8192'); // Use a fast model
        if (!llmResponse.success || !llmResponse.content) {
            logger_1.logger.error(`[parseSearchQueryWithLLM] LLM call failed or returned no content. Error: ${llmResponse.error}`);
            return fallbackResponse;
        }
        // The prompt asks for JSON only, so we attempt to parse it directly.
        const parsedJson = JSON.parse(llmResponse.content);
        // Basic validation of the parsed structure
        if (typeof parsedJson.search_term === 'string' &&
            typeof parsedJson.filters === 'object') {
            logger_1.logger.info(`[parseSearchQueryWithLLM] Successfully parsed query. Term: "${parsedJson.search_term}", Filters:`, parsedJson.filters);
            return {
                search_term: parsedJson.search_term,
                filters: parsedJson.filters,
            };
        }
        else {
            logger_1.logger.warn(`[parseSearchQueryWithLLM] Parsed JSON from LLM has incorrect structure.`, parsedJson);
            return fallbackResponse;
        }
    }
    catch (error) {
        logger_1.logger.error(`[parseSearchQueryWithLLM] An exception occurred during LLM parsing. Error: ${error.message}`, error);
        return fallbackResponse;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1U2VhcmNoRmlsdGVyU2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJubHVTZWFyY2hGaWx0ZXJTa2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQTJCQSwwREEwREM7QUFwRkQsOENBSXlCLENBQUMsNEJBQTRCO0FBQ3RELGdGQUE2RTtBQVU3RSxNQUFNLFVBQVUsR0FBRyxJQUFJLGlDQUFzQixDQUFDLE9BQU8sQ0FBQyxHQUFHLENBQUMsWUFBWSxDQUFDLENBQUMsQ0FBQyxnQ0FBZ0M7QUFFekc7Ozs7Ozs7O0dBUUc7QUFDSSxLQUFLLFVBQVUsdUJBQXVCLENBQzNDLFFBQWdCO0lBRWhCLE1BQU0sZ0JBQWdCLEdBQXNCO1FBQzFDLFdBQVcsRUFBRSxRQUFRO1FBQ3JCLE9BQU8sRUFBRSxFQUFFO0tBQ1osQ0FBQztJQUVGLE1BQU0sV0FBVyxHQUFHLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsaUJBQWlCO0lBRTdFLE1BQU0sTUFBTSxHQUF3QjtRQUNsQyxJQUFJLEVBQUUsb0JBQW9CO1FBQzFCLElBQUksRUFBRTtZQUNKLFFBQVEsRUFBRSxRQUFRO1lBQ2xCLFdBQVcsRUFBRSxXQUFXO1NBQ0M7S0FDNUIsQ0FBQztJQUVGLElBQUksQ0FBQztRQUNILE1BQU0sV0FBVyxHQUFHLE1BQU0sVUFBVSxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUUsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLG1CQUFtQjtRQUU1RixJQUFJLENBQUMsV0FBVyxDQUFDLE9BQU8sSUFBSSxDQUFDLFdBQVcsQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNqRCxlQUFNLENBQUMsS0FBSyxDQUNWLDRFQUE0RSxXQUFXLENBQUMsS0FBSyxFQUFFLENBQ2hHLENBQUM7WUFDRixPQUFPLGdCQUFnQixDQUFDO1FBQzFCLENBQUM7UUFFRCxxRUFBcUU7UUFDckUsTUFBTSxVQUFVLEdBQUcsSUFBSSxDQUFDLEtBQUssQ0FBQyxXQUFXLENBQUMsT0FBTyxDQUFDLENBQUM7UUFFbkQsMkNBQTJDO1FBQzNDLElBQ0UsT0FBTyxVQUFVLENBQUMsV0FBVyxLQUFLLFFBQVE7WUFDMUMsT0FBTyxVQUFVLENBQUMsT0FBTyxLQUFLLFFBQVEsRUFDdEMsQ0FBQztZQUNELGVBQU0sQ0FBQyxJQUFJLENBQ1QsK0RBQStELFVBQVUsQ0FBQyxXQUFXLGFBQWEsRUFDbEcsVUFBVSxDQUFDLE9BQU8sQ0FDbkIsQ0FBQztZQUNGLE9BQU87Z0JBQ0wsV0FBVyxFQUFFLFVBQVUsQ0FBQyxXQUFXO2dCQUNuQyxPQUFPLEVBQUUsVUFBVSxDQUFDLE9BQThCO2FBQ25ELENBQUM7UUFDSixDQUFDO2FBQU0sQ0FBQztZQUNOLGVBQU0sQ0FBQyxJQUFJLENBQ1QseUVBQXlFLEVBQ3pFLFVBQVUsQ0FDWCxDQUFDO1lBQ0YsT0FBTyxnQkFBZ0IsQ0FBQztRQUMxQixDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsZUFBTSxDQUFDLEtBQUssQ0FDViw4RUFBOEUsS0FBSyxDQUFDLE9BQU8sRUFBRSxFQUM3RixLQUFLLENBQ04sQ0FBQztRQUNGLE9BQU8sZ0JBQWdCLENBQUM7SUFDMUIsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBIeWJyaWRTZWFyY2hGaWx0ZXJzIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJztcbmltcG9ydCB7XG4gIE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWIsXG4gIFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gIFNlYXJjaFF1ZXJ5UGFyc2luZ0RhdGEsXG59IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7IC8vIEFzc3VtaW5nIHRoaXMgaXMgdGhlIHBhdGhcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbi8qKlxuICogUmVwcmVzZW50cyB0aGUgc3RydWN0dXJlZCBvdXRwdXQgZnJvbSBwYXJzaW5nIGEgdXNlcidzIHJhdyBzZWFyY2ggcXVlcnkgd2l0aCBhbiBMTE0uXG4gKi9cbmV4cG9ydCBpbnRlcmZhY2UgUGFyc2VkU2VhcmNoUXVlcnkge1xuICBzZWFyY2hfdGVybTogc3RyaW5nO1xuICBmaWx0ZXJzOiBIeWJyaWRTZWFyY2hGaWx0ZXJzO1xufVxuXG5jb25zdCBsbG1TZXJ2aWNlID0gbmV3IE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWIocHJvY2Vzcy5lbnYuR1JPUV9BUElfS0VZKTsgLy8gT3IgaG93ZXZlciBBUEkga2V5IGlzIG1hbmFnZWRcblxuLyoqXG4gKiBUYWtlcyBhIHVzZXIncyByYXcgbmF0dXJhbCBsYW5ndWFnZSBzZWFyY2ggcXVlcnkgYW5kIHVzZXMgYW4gTExNIHRvIHBhcnNlIGl0XG4gKiBpbnRvIGEgY2xlYW4gc2VhcmNoIHRlcm0gYW5kIGEgc3RydWN0dXJlZCBmaWx0ZXJzIG9iamVjdC5cbiAqXG4gKiBAcGFyYW0gcmF3UXVlcnkgVGhlIHVzZXIncyBvcmlnaW5hbCBzZWFyY2ggcXVlcnkgc3RyaW5nLlxuICogQHJldHVybnMgQSBwcm9taXNlIHRoYXQgcmVzb2x2ZXMgdG8gYSBQYXJzZWRTZWFyY2hRdWVyeSBvYmplY3QuXG4gKiAgICAgICAgICBJbiBjYXNlIG9mIHBhcnNpbmcgZmFpbHVyZSwgaXQgZ3JhY2VmdWxseSBmYWxscyBiYWNrIHRvIHJldHVybmluZ1xuICogICAgICAgICAgdGhlIG9yaWdpbmFsIHF1ZXJ5IGFzIHRoZSBzZWFyY2ggdGVybSBhbmQgYW4gZW1wdHkgZmlsdGVycyBvYmplY3QuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBwYXJzZVNlYXJjaFF1ZXJ5V2l0aExMTShcbiAgcmF3UXVlcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxQYXJzZWRTZWFyY2hRdWVyeT4ge1xuICBjb25zdCBmYWxsYmFja1Jlc3BvbnNlOiBQYXJzZWRTZWFyY2hRdWVyeSA9IHtcbiAgICBzZWFyY2hfdGVybTogcmF3UXVlcnksXG4gICAgZmlsdGVyczoge30sXG4gIH07XG5cbiAgY29uc3QgY3VycmVudERhdGUgPSBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXTsgLy8gR2V0IFlZWVktTU0tRERcblxuICBjb25zdCBwcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQgPSB7XG4gICAgdGFzazogJ3BhcnNlX3NlYXJjaF9xdWVyeScsXG4gICAgZGF0YToge1xuICAgICAgcmF3UXVlcnk6IHJhd1F1ZXJ5LFxuICAgICAgY3VycmVudERhdGU6IGN1cnJlbnREYXRlLFxuICAgIH0gYXMgU2VhcmNoUXVlcnlQYXJzaW5nRGF0YSxcbiAgfTtcblxuICB0cnkge1xuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgbGxtU2VydmljZS5nZW5lcmF0ZShwcm9tcHQsICdsbGFtYTMtOGItODE5MicpOyAvLyBVc2UgYSBmYXN0IG1vZGVsXG5cbiAgICBpZiAoIWxsbVJlc3BvbnNlLnN1Y2Nlc3MgfHwgIWxsbVJlc3BvbnNlLmNvbnRlbnQpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtwYXJzZVNlYXJjaFF1ZXJ5V2l0aExMTV0gTExNIGNhbGwgZmFpbGVkIG9yIHJldHVybmVkIG5vIGNvbnRlbnQuIEVycm9yOiAke2xsbVJlc3BvbnNlLmVycm9yfWBcbiAgICAgICk7XG4gICAgICByZXR1cm4gZmFsbGJhY2tSZXNwb25zZTtcbiAgICB9XG5cbiAgICAvLyBUaGUgcHJvbXB0IGFza3MgZm9yIEpTT04gb25seSwgc28gd2UgYXR0ZW1wdCB0byBwYXJzZSBpdCBkaXJlY3RseS5cbiAgICBjb25zdCBwYXJzZWRKc29uID0gSlNPTi5wYXJzZShsbG1SZXNwb25zZS5jb250ZW50KTtcblxuICAgIC8vIEJhc2ljIHZhbGlkYXRpb24gb2YgdGhlIHBhcnNlZCBzdHJ1Y3R1cmVcbiAgICBpZiAoXG4gICAgICB0eXBlb2YgcGFyc2VkSnNvbi5zZWFyY2hfdGVybSA9PT0gJ3N0cmluZycgJiZcbiAgICAgIHR5cGVvZiBwYXJzZWRKc29uLmZpbHRlcnMgPT09ICdvYmplY3QnXG4gICAgKSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtwYXJzZVNlYXJjaFF1ZXJ5V2l0aExMTV0gU3VjY2Vzc2Z1bGx5IHBhcnNlZCBxdWVyeS4gVGVybTogXCIke3BhcnNlZEpzb24uc2VhcmNoX3Rlcm19XCIsIEZpbHRlcnM6YCxcbiAgICAgICAgcGFyc2VkSnNvbi5maWx0ZXJzXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgc2VhcmNoX3Rlcm06IHBhcnNlZEpzb24uc2VhcmNoX3Rlcm0sXG4gICAgICAgIGZpbHRlcnM6IHBhcnNlZEpzb24uZmlsdGVycyBhcyBIeWJyaWRTZWFyY2hGaWx0ZXJzLFxuICAgICAgfTtcbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbcGFyc2VTZWFyY2hRdWVyeVdpdGhMTE1dIFBhcnNlZCBKU09OIGZyb20gTExNIGhhcyBpbmNvcnJlY3Qgc3RydWN0dXJlLmAsXG4gICAgICAgIHBhcnNlZEpzb25cbiAgICAgICk7XG4gICAgICByZXR1cm4gZmFsbGJhY2tSZXNwb25zZTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW3BhcnNlU2VhcmNoUXVlcnlXaXRoTExNXSBBbiBleGNlcHRpb24gb2NjdXJyZWQgZHVyaW5nIExMTSBwYXJzaW5nLiBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIGZhbGxiYWNrUmVzcG9uc2U7XG4gIH1cbn1cbiJdfQ==