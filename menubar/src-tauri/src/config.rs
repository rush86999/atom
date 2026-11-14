//! Backend endpoint configuration for the macOS menu bar companion.
//!
//! Defaults are unchanged: `http://localhost:8000` for HTTP and
//! `ws://localhost:8000/ws/menubar` for WebSocket. An isolated loopback
//! verification backend on a different port can be selected with
//! `ATOM_MENUBAR_BACKEND_URL` (preferred) or the repository-wide
//! `ATOM_BACKEND_URL` convention. `ATOM_MENUBAR_WS_URL` optionally overrides
//! the WebSocket endpoint; otherwise it is derived from the HTTP base.
//!
//! The environment is read on every resolution instead of being cached, so a
//! short-lived verification process cannot retain a stale endpoint. An explicit
//! override that is invalid (unsupported scheme, credentials, query/fragment,
//! or an unparsable URL) is reported as an error to the caller. It is never
//! silently replaced with the localhost default: doing that would send
//! requests to a backend the operator did not configure. Diagnostics never
//! echo the raw configured value so credentials cannot leak into logs.

use url::Url;

/// Default HTTP backend used by every native menu bar command.
pub const DEFAULT_HTTP_BASE_URL: &str = "http://localhost:8000";

/// Default WebSocket endpoint used by the menu bar client.
pub const DEFAULT_WEBSOCKET_URL: &str = "ws://localhost:8000/ws/menubar";

/// Path on the Atom backend that serves the menu bar WebSocket.
pub const WEBSOCKET_PATH: &str = "/ws/menubar";

/// Menu-bar-specific HTTP override.
pub const MENUBAR_BACKEND_URL_ENV: &str = "ATOM_MENUBAR_BACKEND_URL";

/// Repository-wide backend override (used when the menu-bar-specific one is absent).
pub const BACKEND_URL_ENV: &str = "ATOM_BACKEND_URL";

/// Menu-bar-specific WebSocket override.
pub const WEBSOCKET_URL_ENV: &str = "ATOM_MENUBAR_WS_URL";

/// Where the resolved HTTP base came from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EndpointSource {
    Default,
    Environment,
}

impl EndpointSource {
    pub fn as_str(self) -> &'static str {
        match self {
            EndpointSource::Default => "default",
            EndpointSource::Environment => "environment",
        }
    }
}

/// The endpoints used by native commands and the frontend in one resolution.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedEndpoints {
    pub http_base_url: String,
    pub websocket_url: String,
    pub source: EndpointSource,
}

fn read_env(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

/// The raw configured HTTP base, if an environment override is present.
pub fn configured_http_base_url() -> Option<String> {
    read_env(MENUBAR_BACKEND_URL_ENV).or_else(|| read_env(BACKEND_URL_ENV))
}

/// Validate and normalize an HTTP base URL.
///
/// `None`, an empty value, or whitespace preserves the historical default.
/// An explicit non-empty value is validated; unsupported schemes, credentials,
/// queries, and fragments are rejected instead of falling back. The returned
/// value has no trailing slash and is safe to join with an absolute API path.
pub fn resolve_http_base_url(raw: Option<&str>) -> Result<String, String> {
    let Some(value) = raw.map(str::trim).filter(|value| !value.is_empty()) else {
        return Ok(DEFAULT_HTTP_BASE_URL.to_string());
    };

    let parsed = Url::parse(value)
        .map_err(|_| "backend URL must be a valid absolute URL".to_string())?;

    if !matches!(parsed.scheme(), "http" | "https") {
        return Err("backend URL must use http:// or https://".to_string());
    }
    if parsed.host_str().is_none() {
        return Err("backend URL must include a host".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("backend URL must not contain credentials".to_string());
    }
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("backend URL must not include a query or fragment".to_string());
    }

    Ok(parsed.as_str().trim_end_matches('/').to_string())
}

/// Derive the menu bar WebSocket URL from an HTTP base.
pub fn derive_websocket_url(http_base_url: &str) -> Result<String, String> {
    let mut parsed = Url::parse(http_base_url)
        .map_err(|_| "backend URL must be a valid absolute URL".to_string())?;

    let scheme = match parsed.scheme() {
        "http" => "ws",
        "https" => "wss",
        _ => return Err("backend URL must use http:// or https://".to_string()),
    };
    parsed
        .set_scheme(scheme)
        .map_err(|_| "cannot derive a WebSocket URL from the backend URL".to_string())?;

    let prefix = parsed.path().trim_end_matches('/');
    let path = if prefix.is_empty() {
        WEBSOCKET_PATH.to_string()
    } else {
        format!("{prefix}{WEBSOCKET_PATH}")
    };
    parsed.set_path(&path);
    parsed.set_query(None);
    parsed.set_fragment(None);

    Ok(parsed.as_str().to_string())
}

/// Validate an explicit WebSocket override, or derive one from the HTTP base.
pub fn resolve_websocket_url(
    raw: Option<&str>,
    http_base_url: &str,
) -> Result<String, String> {
    let Some(value) = raw.map(str::trim).filter(|value| !value.is_empty()) else {
        return derive_websocket_url(http_base_url);
    };

    let parsed = Url::parse(value)
        .map_err(|_| "WebSocket URL must be a valid absolute URL".to_string())?;

    if !matches!(parsed.scheme(), "ws" | "wss") {
        return Err("WebSocket URL must use ws:// or wss://".to_string());
    }
    if parsed.host_str().is_none() {
        return Err("WebSocket URL must include a host".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("WebSocket URL must not contain credentials".to_string());
    }
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("WebSocket URL must not include a query or fragment".to_string());
    }

    Ok(parsed.as_str().trim_end_matches('/').to_string())
}

/// Canonical origin (`scheme://host[:port]`) for a backend base URL.
///
/// A persisted session is bound to this value. It deliberately excludes the
/// path prefix: a token is only meaningful for the origin that issued it, while
/// a deployment can move its API prefix without becoming a different trust
/// boundary. The host is normalized by `url`, so case, default ports and IPv6
/// spelling cannot produce a false match. An invalid base is an error; it must
/// never be treated as "the same origin".
pub fn http_origin(raw: &str) -> Result<String, String> {
    if raw.trim().is_empty() {
        return Err("backend URL must be a non-empty http(s) URL".to_string());
    }
    let normalized = resolve_http_base_url(Some(raw))?;
    let parsed = Url::parse(&normalized)
        .map_err(|_| "backend URL must be a valid absolute URL".to_string())?;
    let origin = parsed.origin();
    if !origin.is_tuple() {
        return Err("backend URL must have an http(s) origin".to_string());
    }
    Ok(origin.ascii_serialization())
}

/// Join an absolute API path onto a backend base.
pub fn join_api_url(base: &str, path: &str) -> String {
    let base = base.trim_end_matches('/');
    let path = if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    };
    format!("{base}{path}")
}

/// Resolve the HTTP base and report whether an environment override applied.
///
/// An explicit but invalid override is an error; it never falls back to the
/// localhost default.
pub fn http_base_url_with_source() -> Result<(String, EndpointSource), String> {
    match configured_http_base_url() {
        Some(raw) => {
            resolve_http_base_url(Some(&raw)).map(|url| (url, EndpointSource::Environment))
        }
        None => Ok((DEFAULT_HTTP_BASE_URL.to_string(), EndpointSource::Default)),
    }
}

/// Resolve the HTTP base, reading environment overrides at call time.
pub fn http_base_url() -> Result<String, String> {
    http_base_url_with_source().map(|(url, _)| url)
}

/// Build an absolute API URL for a native command.
///
/// Propagates an invalid explicit override so a request is never silently sent
/// to the localhost default.
pub fn api_url(path: &str) -> Result<String, String> {
    http_base_url().map(|base| join_api_url(&base, path))
}

/// Resolve the WebSocket URL against the supplied HTTP base.
pub fn websocket_url_for(http_base_url: &str) -> Result<String, String> {
    resolve_websocket_url(read_env(WEBSOCKET_URL_ENV).as_deref(), http_base_url)
}

/// Resolve the WebSocket URL, reading environment overrides at call time.
pub fn websocket_url() -> Result<String, String> {
    let http_base_url = http_base_url()?;
    websocket_url_for(&http_base_url)
}

/// Resolve both endpoints and the HTTP source in one call.
pub fn resolve_endpoints() -> Result<ResolvedEndpoints, String> {
    let (http_base_url, source) = http_base_url_with_source()?;
    let websocket_url = websocket_url_for(&http_base_url)?;
    Ok(ResolvedEndpoints {
        http_base_url,
        websocket_url,
        source,
    })
}

/// Whether a URL points at the local loopback interface.
pub fn is_loopback_url(value: &str) -> bool {
    let Ok(parsed) = Url::parse(value) else {
        return false;
    };
    let Some(host) = parsed.host_str() else {
        return false;
    };
    let host = host.to_ascii_lowercase();
    matches!(host.as_str(), "localhost" | "127.0.0.1" | "::1" | "[::1]")
        || host.ends_with(".localhost")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    /// Restores an environment variable when the test scope ends, even if an
    /// assertion panics.
    struct EnvVarGuard {
        key: &'static str,
        previous: Option<String>,
    }

    impl EnvVarGuard {
        fn set(key: &'static str, value: &str) -> Self {
            let previous = std::env::var(key).ok();
            std::env::set_var(key, value);
            Self { key, previous }
        }

        fn clear(key: &'static str) -> Self {
            let previous = std::env::var(key).ok();
            std::env::remove_var(key);
            Self { key, previous }
        }
    }

    impl Drop for EnvVarGuard {
        fn drop(&mut self) {
            match &self.previous {
                Some(value) => std::env::set_var(self.key, value),
                None => std::env::remove_var(self.key),
            }
        }
    }

    #[test]
    fn defaults_are_unchanged() {
        assert_eq!(resolve_http_base_url(None).unwrap(), DEFAULT_HTTP_BASE_URL);
        assert_eq!(
            resolve_websocket_url(None, DEFAULT_HTTP_BASE_URL).unwrap(),
            DEFAULT_WEBSOCKET_URL
        );
        assert_eq!(resolve_http_base_url(Some("   ")).unwrap(), DEFAULT_HTTP_BASE_URL);
    }

    #[test]
    fn accepts_isolated_loopback_port_and_strips_trailing_slash() {
        assert_eq!(
            resolve_http_base_url(Some("http://127.0.0.1:8123/")).unwrap(),
            "http://127.0.0.1:8123"
        );
        assert_eq!(
            resolve_http_base_url(Some("  http://localhost:8124  ")).unwrap(),
            "http://localhost:8124"
        );
        assert_eq!(
            resolve_http_base_url(Some("http://127.0.0.1:8123/prefix")).unwrap(),
            "http://127.0.0.1:8123/prefix"
        );
    }

    #[test]
    fn derives_websocket_from_http_base() {
        assert_eq!(
            resolve_websocket_url(None, "http://127.0.0.1:8123").unwrap(),
            "ws://127.0.0.1:8123/ws/menubar"
        );
        assert_eq!(
            derive_websocket_url("https://atom.example").unwrap(),
            "wss://atom.example/ws/menubar"
        );
        assert_eq!(
            derive_websocket_url("http://127.0.0.1:8123/prefix").unwrap(),
            "ws://127.0.0.1:8123/prefix/ws/menubar"
        );
    }

    #[test]
    fn explicit_websocket_override_is_used_verbatim() {
        assert_eq!(
            resolve_websocket_url(
                Some("ws://127.0.0.1:8123/custom/menubar"),
                "http://localhost:8000"
            )
            .unwrap(),
            "ws://127.0.0.1:8123/custom/menubar"
        );
    }

    #[test]
    fn rejects_invalid_http_overrides_without_echoing_them() {
        for raw in [
            "ws://127.0.0.1:8123",
            "ftp://127.0.0.1:8123",
            "not a url",
        ] {
            let error = resolve_http_base_url(Some(raw)).unwrap_err();
            assert!(error.contains("http:// or https://") || error.contains("valid absolute"));
            assert!(!error.contains(raw));
        }

        let error =
            resolve_http_base_url(Some("http://user:secret@127.0.0.1:8123")).unwrap_err();
        assert!(error.contains("credentials"));
        assert!(!error.contains("secret"));
        assert!(!error.contains("127.0.0.1"));

        let error = resolve_http_base_url(Some("http://127.0.0.1:8123?token=x")).unwrap_err();
        assert!(error.contains("query or fragment"));
        assert!(!error.contains("token"));

        let error = resolve_http_base_url(Some("http://127.0.0.1:8123#fragment")).unwrap_err();
        assert!(error.contains("query or fragment"));
        assert!(!error.contains("#fragment"));
        assert!(!error.contains("127.0.0.1"));
    }

    #[test]
    fn rejects_invalid_websocket_overrides_without_echoing_them() {
        let error = resolve_websocket_url(
            Some("http://127.0.0.1:8123"),
            "http://localhost:8000",
        )
        .unwrap_err();
        assert!(error.contains("ws:// or wss://"));
        assert!(!error.contains("127.0.0.1"));

        let error = resolve_websocket_url(
            Some("ws://user:secret@127.0.0.1:8123"),
            "http://localhost:8000",
        )
        .unwrap_err();
        assert!(error.contains("credentials"));
        assert!(!error.contains("secret"));

        let error = resolve_websocket_url(
            Some("ws://127.0.0.1:8123#fragment"),
            "http://localhost:8000",
        )
        .unwrap_err();
        assert!(error.contains("query or fragment"));
        assert!(!error.contains("#fragment"));
        assert!(!error.contains("127.0.0.1"));
    }

    #[test]
    fn invalid_environment_overrides_never_fall_back_to_localhost() {
        let _lock = ENV_LOCK.lock().unwrap();

        {
            let _menubar = EnvVarGuard::set(
                MENUBAR_BACKEND_URL_ENV,
                "http://user:secret@127.0.0.1:8123",
            );
            let _backend = EnvVarGuard::clear(BACKEND_URL_ENV);
            let _websocket = EnvVarGuard::clear(WEBSOCKET_URL_ENV);

            let error = http_base_url_with_source().unwrap_err();
            assert!(error.contains("credentials"));
            assert!(!error.contains("secret"));
            assert!(!error.contains("127.0.0.1"));

            assert!(http_base_url().is_err());
            assert!(api_url("/api/menubar/status").is_err());
            assert!(websocket_url().is_err());
            assert!(resolve_endpoints().is_err());
        }

        {
            let _menubar = EnvVarGuard::clear(MENUBAR_BACKEND_URL_ENV);
            let _backend = EnvVarGuard::clear(BACKEND_URL_ENV);
            let _websocket = EnvVarGuard::set(
                WEBSOCKET_URL_ENV,
                "http://127.0.0.1:8123/ws/menubar",
            );

            let error = resolve_endpoints().unwrap_err();
            assert!(error.contains("WebSocket URL"));
            assert!(!error.contains("127.0.0.1"));
            assert!(websocket_url_for(DEFAULT_HTTP_BASE_URL).is_err());
        }
    }

    #[test]
    fn valid_environment_override_is_reported_as_environment() {
        let _lock = ENV_LOCK.lock().unwrap();
        let _menubar = EnvVarGuard::set(MENUBAR_BACKEND_URL_ENV, "http://127.0.0.1:8123");
        let _backend = EnvVarGuard::clear(BACKEND_URL_ENV);
        let _websocket = EnvVarGuard::clear(WEBSOCKET_URL_ENV);

        let endpoints = resolve_endpoints().unwrap();
        assert_eq!(endpoints.http_base_url, "http://127.0.0.1:8123");
        assert_eq!(endpoints.websocket_url, "ws://127.0.0.1:8123/ws/menubar");
        assert_eq!(endpoints.source, EndpointSource::Environment);
        assert_eq!(
            api_url("/api/menubar/status").unwrap(),
            "http://127.0.0.1:8123/api/menubar/status"
        );
    }

    #[test]
    fn joins_api_paths_without_duplicate_slashes() {
        assert_eq!(
            join_api_url("http://127.0.0.1:8123/", "/api/menubar/status"),
            "http://127.0.0.1:8123/api/menubar/status"
        );
        assert_eq!(
            join_api_url("http://127.0.0.1:8123", "api/menubar/status"),
            "http://127.0.0.1:8123/api/menubar/status"
        );
    }

    #[test]
    fn normalizes_backend_origin_for_session_binding() {
        assert_eq!(
            http_origin("http://127.0.0.1:8123/prefix/").unwrap(),
            "http://127.0.0.1:8123"
        );
        assert_eq!(
            http_origin("HTTP://LocalHost:8000").unwrap(),
            "http://localhost:8000"
        );
        assert_eq!(
            http_origin("https://Atom.Example/api").unwrap(),
            "https://atom.example"
        );
        assert_eq!(
            http_origin("http://[::1]:8123").unwrap(),
            "http://[::1]:8123"
        );
    }

    #[test]
    fn distinct_backend_origins_never_compare_equal() {
        let loopback = http_origin("http://127.0.0.1:8123").unwrap();
        for other in [
            "http://127.0.0.1:8124",
            "https://127.0.0.1:8123",
            "http://localhost:8123",
            "https://atom.example",
        ] {
            assert_ne!(loopback, http_origin(other).unwrap());
        }
    }

    #[test]
    fn invalid_backend_origin_is_an_error_not_a_default() {
        for raw in [
            "",
            "   ",
            "ws://127.0.0.1:8123",
            "http://user:secret@127.0.0.1:8123",
            "http://127.0.0.1:8123?token=x",
            "not a url",
        ] {
            assert!(http_origin(raw).is_err(), "{raw} must not resolve");
        }
    }

    #[test]
    fn identifies_loopback_hosts() {
        assert!(is_loopback_url("http://localhost:8123"));
        assert!(is_loopback_url("http://127.0.0.1:8123"));
        assert!(is_loopback_url("ws://[::1]:8123/ws/menubar"));
        assert!(!is_loopback_url("https://atom.example"));
        assert!(!is_loopback_url("not a url"));
    }
}
