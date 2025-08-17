import axios from "axios";
import { executeGraphQLQuery, executeGraphQLMutation, GraphQLError } from "./graphqlClient";

jest.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock environment variables
let originalEnv: NodeJS.ProcessEnv;

beforeEach(() => {
  originalEnv = process.env;
  process.env = {
    ...originalEnv,
    POSTGRAPHILE_URL: "http://localhost:5000/graphql",
    AUTH_BEARER_TOKEN: "test-bearer-token"
  };

  jest.clearAllMocks();
  mockedAxios.post.mockReset();
  jest.spyOn(console, "error").mockImplementation(() => {});
  jest.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  process.env = originalEnv;
  jest.restoreAllMocks();
});

describe("Postgraphile GraphQL Client", () => {
  const query = "query TestQuery($id: ID!) { test(id: $id) { id name } }";
  const variables = { id: "123" };
  const operationName = "TestQuery";

  const mockSuccessData = { test: { id: "123", name: "Test Item" } };
  const mockGraphQLErrors = [{ message: "Permission denied" }];

  describe("executeGraphQLQuery", () => {
    it("should execute query successfully on first attempt", async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { data: mockSuccessData }
      });

      const result = await executeGraphQLQuery(query, variables, operationName, "test-user");

      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        process.env.POSTGRAPHILE_URL,
        { query, variables, operationName },
        expect.objectContaining({
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer test-bearer-token"
          },
          timeout: 15000
        })
      );
    });

    it("should retry on HTTP 500 errors and succeed", async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 500, data: "Server Error" }
        })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(query, variables, operationName);

      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    it("should retry on HTTP 429 rate limit errors", async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 429, data: "Too Many Requests" }
        })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(query, variables, operationName);

      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    it("should handle non-retryable HTTP errors (400 series)", async () => {
      mockedAxios.post.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 400, data: "Bad Request" }
      });

      await expect(executeGraphQLQuery(query, variables, operationName))
        .rejects.toThrow();
    });

    it("should retry on network timeout (ECONNABORTED)", async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          code: "ECONNABORTED",
          message: "timeout exceeded"
        })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(query, variables, operationName);

      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    it("should handle GraphQL errors in response", async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { errors: mockGraphQLErrors }
      });

      await expect(executeGraphQLQuery(query, variables, operationName))
        .rejects.toThrow(GraphQLError);
    });

    it("should fail after all retries for persistent 500 errors", async () => {
      for (let i = 0; i < 3; i++) {
        mockedAxios.post.mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 500, data: `Server Error ${i + 1}` }
        });
      }

      await expect(executeGraphQLQuery(query, variables, operationName))
