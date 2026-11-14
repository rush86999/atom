import {
  BACKEND_CONFIG_ERROR_SOURCE,
  DEFAULT_BACKEND_HTTP_URL,
  DEFAULT_BACKEND_WEBSOCKET_URL,
  deriveWebSocketUrl,
  isLoopbackServerUrl,
  loadBackendConfig,
  normalizeServerUrl,
  readStoredServerUrl,
  validateServerUrl,
  validateWebSocketUrl,
  writeStoredServerUrl,
} from "../config";

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
}

function nativeConfig(
  httpBaseUrl: string,
  source = "environment",
  websocketUrl = deriveWebSocketUrl(httpBaseUrl)
) {
  return {
    http_base_url: httpBaseUrl,
    websocket_url: websocketUrl,
    http_base_url_source: source,
  };
}

describe("menu bar backend configuration", () => {
  test("defaults are unchanged", () => {
    expect(DEFAULT_BACKEND_HTTP_URL).toBe("http://localhost:8000");
    expect(normalizeServerUrl(undefined)).toBe("http://localhost:8000");
    expect(normalizeServerUrl("")).toBe("http://localhost:8000");
    expect(deriveWebSocketUrl(DEFAULT_BACKEND_HTTP_URL)).toBe(
      "ws://localhost:8000/ws/menubar"
    );
    expect(DEFAULT_BACKEND_WEBSOCKET_URL).toBe("ws://localhost:8000/ws/menubar");
  });

  test("isolated loopback backend on a separate port is supported", () => {
    expect(validateServerUrl("http://127.0.0.1:8123/")).toEqual({
      ok: true,
      url: "http://127.0.0.1:8123",
    });
    expect(deriveWebSocketUrl("http://127.0.0.1:8123")).toBe(
      "ws://127.0.0.1:8123/ws/menubar"
    );
    expect(isLoopbackServerUrl("http://127.0.0.1:8123")).toBe(true);
    expect(isLoopbackServerUrl("http://localhost:8123")).toBe(true);
    expect(isLoopbackServerUrl("https://atom.example")).toBe(false);
  });

  test("https bases derive wss", () => {
    expect(deriveWebSocketUrl("https://menubar.example")).toBe(
      "wss://menubar.example/ws/menubar"
    );
  });

  test("accepts a bare host and preserves a path prefix", () => {
    expect(validateServerUrl("127.0.0.1:8123")).toEqual({
      ok: true,
      url: "http://127.0.0.1:8123",
    });
    expect(validateServerUrl("http://127.0.0.1:8123/prefix/")).toEqual({
      ok: true,
      url: "http://127.0.0.1:8123/prefix",
    });
  });

  test("rejects unsupported schemes, credentials, queries, and fragments", () => {
    const unsupported = validateServerUrl("ws://127.0.0.1:8123");
    expect(unsupported.ok).toBe(false);
    if (!unsupported.ok) {
      expect(unsupported.error).toContain("http:// or https://");
      expect(unsupported.error).not.toContain("127.0.0.1");
    }

    const credentials = validateServerUrl(
      "http://user:secret@127.0.0.1:8123"
    );
    expect(credentials.ok).toBe(false);
    if (!credentials.ok) {
      expect(credentials.error).toContain("credentials");
      expect(credentials.error).not.toContain("secret");
      expect(credentials.error).not.toContain("127.0.0.1");
    }

    const query = validateServerUrl("http://127.0.0.1:8123?token=secret");
    expect(query.ok).toBe(false);
    if (!query.ok) {
      expect(query.error).toContain("query");
      expect(query.error).not.toContain("secret");
    }

    const fragment = validateServerUrl("http://127.0.0.1:8123#fragment");
    expect(fragment.ok).toBe(false);
    if (!fragment.ok) {
      expect(fragment.error).toContain("fragment");
    }

    expect(validateServerUrl("not a url").ok).toBe(false);
    expect(validateServerUrl("http://").ok).toBe(false);
  });

  test("normalizer keeps the default for invalid values but never coerces schemes", () => {
    expect(normalizeServerUrl("ws://127.0.0.1:8123")).toBe(
      DEFAULT_BACKEND_HTTP_URL
    );
    expect(normalizeServerUrl("not a url")).toBe(DEFAULT_BACKEND_HTTP_URL);
    expect(
      normalizeServerUrl("http://user:secret@127.0.0.1:8123")
    ).toBe(DEFAULT_BACKEND_HTTP_URL);
  });

  test("websocket validation requires ws or wss and no credentials", () => {
    expect(validateWebSocketUrl("ws://127.0.0.1:8123/ws/menubar")).toEqual({
      ok: true,
      url: "ws://127.0.0.1:8123/ws/menubar",
    });
    expect(validateWebSocketUrl("http://127.0.0.1:8123").ok).toBe(false);
    const credentials = validateWebSocketUrl(
      "ws://user:secret@127.0.0.1:8123"
    );
    expect(credentials.ok).toBe(false);
    if (!credentials.ok) {
      expect(credentials.error).not.toContain("secret");
    }
    expect(validateWebSocketUrl("ws://127.0.0.1:8123#fragment").ok).toBe(false);
  });

  test("stored settings round-trip and remain the fallback", () => {
    const storage = memoryStorage();
    expect(readStoredServerUrl(storage)).toBeNull();
    expect(writeStoredServerUrl("http://127.0.0.1:8124/", storage)).toEqual({
      ok: true,
      url: "http://127.0.0.1:8124",
    });
    expect(readStoredServerUrl(storage)).toBe("http://127.0.0.1:8124");
  });

  test("invalid stored settings are ignored and never overwrite a valid value", () => {
    const storage = memoryStorage({
      atom_server_url: "http://user:secret@127.0.0.1:8123",
    });
    expect(readStoredServerUrl(storage)).toBeNull();

    const invalid = writeStoredServerUrl(
      "http://user:secret@127.0.0.1:8124",
      storage
    );
    expect(invalid.ok).toBe(false);
    if (!invalid.ok) {
      expect(invalid.error).not.toContain("secret");
    }
    expect(storage.getItem("atom_server_url")).toBe(
      "http://user:secret@127.0.0.1:8123"
    );
  });

  test("native environment override wins over a stale stored value", async () => {
    const storage = memoryStorage({ atom_server_url: "http://localhost:8000" });
    const config = await loadBackendConfig(
      storage,
      async <T>(): Promise<T> => nativeConfig("http://127.0.0.1:8123") as T,
      true
    );

    expect(config.error).toBeUndefined();
    expect(config.http_base_url).toBe("http://127.0.0.1:8123");
    expect(config.websocket_url).toBe("ws://127.0.0.1:8123/ws/menubar");
    expect(config.http_base_url_source).toBe("environment");
  });

  test("browser-only launches keep the stored/default fallback", async () => {
    const storage = memoryStorage({ atom_server_url: "http://127.0.0.1:8124" });
    const invokeFn = jest.fn(async () => {
      throw new Error("native IPC must not be used without a bridge");
    });
    const config = await loadBackendConfig(storage, invokeFn, false);

    expect(invokeFn).not.toHaveBeenCalled();
    expect(config.http_base_url).toBe("http://127.0.0.1:8124");
    expect(config.websocket_url).toBe("ws://127.0.0.1:8124/ws/menubar");
    expect(config.http_base_url_source).toBe("settings");
  });

  test("falls back to the default without storage or native config", async () => {
    const config = await loadBackendConfig(memoryStorage(), async () => {
      throw new Error("no Tauri IPC in this test");
    }, false);

    expect(config.http_base_url).toBe(DEFAULT_BACKEND_HTTP_URL);
    expect(config.websocket_url).toBe(DEFAULT_BACKEND_WEBSOCKET_URL);
    expect(config.http_base_url_source).toBe("default");
  });

  test("native rejection is surfaced and never falls back to localhost", async () => {
    const storage = memoryStorage({ atom_server_url: "http://127.0.0.1:8124" });
    const config = await loadBackendConfig(
      storage,
      async () => {
        throw new Error(
          'backend URL "http://user:secret@127.0.0.1:8123" must not contain credentials'
        );
      },
      true
    );

    expect(config.http_base_url_source).toBe(BACKEND_CONFIG_ERROR_SOURCE);
    expect(config.http_base_url).toBe("");
    expect(config.websocket_url).toBe("");
    expect(config.error).toBeTruthy();
    expect(config.error).not.toContain("secret");
    expect(config.error).not.toContain("127.0.0.1");
    expect(config.error).toContain("<redacted-url>");
  });

  test("malformed or invalid native success payloads are rejected", async () => {
    const malformed = await loadBackendConfig(
      memoryStorage(),
      async <T>(): Promise<T> => ({ http_base_url: "http://127.0.0.1:8123" } as T),
      true
    );
    expect(malformed.error).toBeTruthy();
    expect(malformed.http_base_url_source).toBe(BACKEND_CONFIG_ERROR_SOURCE);

    const invalidHttp = await loadBackendConfig(
      memoryStorage(),
      async <T>(): Promise<T> =>
        nativeConfig("http://user:secret@127.0.0.1:8123") as T,
      true
    );
    expect(invalidHttp.error).toBeTruthy();
    expect(invalidHttp.error).not.toContain("secret");
    expect(invalidHttp.http_base_url).toBe("");

    const invalidWebSocket = await loadBackendConfig(
      memoryStorage(),
      async <T>(): Promise<T> =>
        nativeConfig(
          "http://127.0.0.1:8123",
          "environment",
          "http://127.0.0.1:8123/ws/menubar"
        ) as T,
      true
    );
    expect(invalidWebSocket.error).toContain("WebSocket URL");
    expect(invalidWebSocket.http_base_url).toBe("");
  });

  test("native default source still yields to a valid stored setting", async () => {
    const storage = memoryStorage({ atom_server_url: "http://127.0.0.1:8124" });
    const config = await loadBackendConfig(
      storage,
      async <T>(): Promise<T> => nativeConfig(DEFAULT_BACKEND_HTTP_URL, "default") as T,
      true
    );

    expect(config.http_base_url).toBe("http://127.0.0.1:8124");
    expect(config.websocket_url).toBe("ws://127.0.0.1:8124/ws/menubar");
    expect(config.http_base_url_source).toBe("settings");
  });

  test("credential-bearing values are not treated as loopback", () => {
    expect(isLoopbackServerUrl("http://user:secret@127.0.0.1:8123")).toBe(false);
  });
});
