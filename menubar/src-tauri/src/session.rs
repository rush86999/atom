//! Durable menu bar sessions across application relaunches.
//!
//! A successful sign-in writes the bearer token to the macOS Keychain through
//! `keyring` (the same per-email entry the original implementation used) and a
//! non-secret session record that names the account, the device id and the
//! backend origin that issued the token. On relaunch `get_session` loads that
//! record, refuses to use it when the effective backend origin changed, and
//! validates the token against the authenticated menu bar status endpoint
//! before any session is restored. A successful HTTP response is not enough:
//! the endpoint also has to report `status: "connected"` for the same device id
//! the record was issued to.
//!
//! Failure policy is deliberately fail-closed:
//!
//! - a token rejected by the backend is deleted;
//! - a record bound to another origin is deleted, token included;
//! - a missing/corrupted record restores nothing;
//! - a transient validation failure (network, 5xx) restores nothing but keeps
//!   the record so a later launch can try again;
//! - logout deletes the record before the token, so a partially failed cleanup
//!   can never leave a restorable session behind, and the caller clears
//!   in-memory state regardless of the cleanup result.
//!
//! No secret is ever written to diagnostics or to the session record itself.

use std::future::Future;
use std::pin::Pin;
use std::time::Duration;

use keyring::Entry;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Version of the persisted session record. Unknown versions are treated as
/// corrupted and never restored.
pub const SAVED_SESSION_VERSION: u32 = 1;

/// Keychain account that holds the non-secret session record.
///
/// The token keeps its historical per-email account so existing Keychain
/// entries and logout semantics are preserved.
pub const SESSION_RECORD_ACCOUNT: &str = "__atom_menubar_session_v1__";

/// Authenticated endpoint used to prove a saved token is still accepted.
pub const SESSION_VALIDATION_PATH: &str = "/api/menubar/status";

/// How long session validation may take before it fails closed.
///
/// Kept short because this runs while the menu bar is showing its startup
/// spinner: an unreachable backend should land on the sign-in screen promptly
/// rather than hold the UI for a network timeout.
pub const SESSION_VALIDATION_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionUser {
    pub id: String,
    pub email: String,
    pub first_name: String,
    pub last_name: String,
}

/// A saved session as used in memory. The token is stored separately in the
/// Keychain and is never part of the serialized record.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SavedSession {
    pub token: String,
    pub user: SessionUser,
    pub device_id: String,
    pub backend_origin: String,
}

/// The non-secret part persisted in the Keychain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct SessionRecord {
    version: u32,
    user: SessionUser,
    device_id: String,
    backend_origin: String,
}

impl From<&SavedSession> for SessionRecord {
    fn from(session: &SavedSession) -> Self {
        Self {
            version: SAVED_SESSION_VERSION,
            user: session.user.clone(),
            device_id: session.device_id.clone(),
            backend_origin: session.backend_origin.clone(),
        }
    }
}

/// Port for durable session persistence.
///
/// Production uses [`KeychainSessionStore`]; tests use an in-memory
/// implementation so no test touches the real Keychain.
pub trait SessionStore: Send + Sync {
    /// Load a complete session (record plus token), or `None` when there is no
    /// restorable session.
    fn load(&self) -> Result<Option<SavedSession>, String>;
    fn save(&self, session: &SavedSession) -> Result<(), String>;
    fn delete_record(&self) -> Result<(), String>;
    fn delete_token(&self, email: &str) -> Result<(), String>;
}

/// Keychain-backed session store.
pub struct KeychainSessionStore {
    service: String,
}

impl KeychainSessionStore {
    pub fn new(service: impl Into<String>) -> Self {
        Self {
            service: service.into(),
        }
    }

    fn record_entry(&self) -> Result<Entry, String> {
        Entry::new(&self.service, SESSION_RECORD_ACCOUNT)
            .map_err(|e| format!("Keychain error: {e}"))
    }

    fn token_entry(&self, email: &str) -> Result<Entry, String> {
        Entry::new(&self.service, email).map_err(|e| format!("Keychain error: {e}"))
    }

    fn read_record(&self) -> Result<Option<SessionRecord>, String> {
        let entry = self.record_entry()?;
        match entry.get_password() {
            Ok(raw) => match decode_record(&raw) {
                Ok(record) => Ok(Some(record)),
                Err(_) => {
                    // A corrupted, truncated or future-version record can never
                    // become valid. Drop it so one bad record neither restores a
                    // session nor blocks a future sign-in.
                    let _ = self.delete_record();
                    Ok(None)
                }
            },
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(format!("Failed to read saved session: {e}")),
        }
    }

    fn write_record(&self, record: &SessionRecord) -> Result<(), String> {
        let raw = serde_json::to_string(record)
            .map_err(|_| "Failed to encode saved session".to_string())?;
        self.record_entry()?
            .set_password(&raw)
            .map_err(|e| format!("Failed to store saved session: {e}"))
    }
}

impl SessionStore for KeychainSessionStore {
    fn load(&self) -> Result<Option<SavedSession>, String> {
        let record = match self.read_record() {
            Ok(Some(record)) => record,
            Ok(None) => return Ok(None),
            Err(error) => return Err(error),
        };

        let token = match self.token_entry(&record.user.email)?.get_password() {
            Ok(token) => token,
            Err(keyring::Error::NoEntry) => {
                // The record outlived its token. Remove the dangling pointer so
                // no later launch mistakes it for a restorable session.
                let _ = self.delete_record();
                return Ok(None);
            }
            Err(e) => return Err(format!("Failed to read saved token: {e}")),
        };

        if token.is_empty() {
            let _ = self.delete_record();
            let _ = self.delete_token(&record.user.email);
            return Ok(None);
        }

        Ok(Some(SavedSession {
            token,
            user: record.user,
            device_id: record.device_id,
            backend_origin: record.backend_origin,
        }))
    }

    fn save(&self, session: &SavedSession) -> Result<(), String> {
        validate_session(session)?;

        // Reading first lets an older account's token be retired after the new
        // record is durable, and surfaces an inaccessible Keychain before a new
        // secret is written.
        let previous = self.load()?;

        self.token_entry(&session.user.email)?
            .set_password(&session.token)
            .map_err(|e| format!("Failed to store token: {e}"))?;

        if let Err(error) = self.write_record(&SessionRecord::from(session)) {
            // Never leave a token without a record: that would be an
            // unaccounted credential and could restore against a stale binding.
            let _ = self.delete_token(&session.user.email);
            return Err(error);
        }

        if let Some(previous) = previous {
            if previous.user.email != session.user.email {
                // Best effort. The record now points at the new account, so the
                // old token is no longer restorable even if deletion fails.
                let _ = self.delete_token(&previous.user.email);
            }
        }

        Ok(())
    }

    fn delete_record(&self) -> Result<(), String> {
        let entry = self.record_entry()?;
        match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(delete_error) => {
                // Defense in depth: if the item cannot be deleted, overwrite it
                // with an unparsable value so it can never be restored. The
                // error is still reported to the caller.
                if entry.set_password("").is_ok() {
                    Err(format!(
                        "Failed to delete saved session; it was invalidated instead: {delete_error}"
                    ))
                } else {
                    Err(format!("Failed to delete saved session: {delete_error}"))
                }
            }
        }
    }

    fn delete_token(&self, email: &str) -> Result<(), String> {
        match self.token_entry(email)?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(format!("Failed to delete token: {e}")),
        }
    }
}

fn validate_session(session: &SavedSession) -> Result<(), String> {
    if session.token.trim().is_empty() {
        return Err("Refusing to save an empty session token".to_string());
    }
    if session.user.email.trim().is_empty() {
        return Err("Refusing to save a session without an email".to_string());
    }
    if session.backend_origin.trim().is_empty() {
        return Err("Refusing to save a session without a backend origin".to_string());
    }
    Ok(())
}

fn decode_record(raw: &str) -> Result<SessionRecord, String> {
    let record: SessionRecord =
        serde_json::from_str(raw).map_err(|_| "Saved session is not valid JSON".to_string())?;
    if record.version != SAVED_SESSION_VERSION {
        return Err(format!(
            "Unsupported saved session version {}",
            record.version
        ));
    }
    if record.user.email.trim().is_empty()
        || record.backend_origin.trim().is_empty()
    {
        return Err("Saved session is missing required fields".to_string());
    }
    Ok(record)
}

/// Remove a saved session, record first and token second.
///
/// `email` is the in-memory account when one is known (logout), so a record
/// that disappeared or never loaded cannot leave its token behind. Failures are
/// reported without including any credential material.
pub fn clear_saved_session(store: &dyn SessionStore, email: Option<&str>) -> Result<(), String> {
    let mut emails: Vec<String> = Vec::new();
    if let Some(email) = email.filter(|value| !value.trim().is_empty()) {
        emails.push(email.to_string());
    }
    if let Ok(Some(saved)) = store.load() {
        if !emails.iter().any(|known| known == &saved.user.email) {
            emails.push(saved.user.email);
        }
    }

    let mut errors: Vec<String> = Vec::new();

    // Deleting the record first makes a partial cleanup fail closed: without a
    // record, `load` cannot restore even if a token deletion later fails.
    if let Err(error) = store.delete_record() {
        errors.push(error);
    }
    for email in emails {
        if let Err(error) = store.delete_token(&email) {
            errors.push(error);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors.join("; "))
    }
}

/// The subset of `GET /api/menubar/status` that proves a saved session.
///
/// The endpoint answers `200` with `status: "disconnected"` when the device id
/// is missing or belongs to another account, so the body must be checked as
/// well as the HTTP status.
#[derive(Debug, Deserialize)]
struct StatusResponse {
    status: String,
    #[serde(default)]
    device_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationOutcome {
    Valid,
    /// The backend definitively refused the token or the session (401/403, a
    /// `disconnected` status, or a device id that does not match the record).
    Rejected,
    /// The backend could not be reached, or answered with a retryable error.
    Unavailable(String),
}

pub type ValidationFuture<'a> =
    Pin<Box<dyn Future<Output = ValidationOutcome> + Send + 'a>>;

/// Port for proving a saved token is still accepted by the effective backend.
pub trait SessionValidator: Send + Sync {
    fn validate<'a>(
        &'a self,
        token: &'a str,
        device_id: Option<&'a str>,
    ) -> ValidationFuture<'a>;
}

/// Validates a token with `GET /api/menubar/status`, which requires the same
/// bearer and device headers as the rest of the companion API.
pub struct HttpSessionValidator {
    client: Client,
    base_url: String,
}

impl HttpSessionValidator {
    pub fn new(base_url: impl Into<String>) -> Result<Self, String> {
        let client = Client::builder()
            .timeout(SESSION_VALIDATION_TIMEOUT)
            // A status probe that redirects is not proof that the configured
            // origin accepted the token. Treat it as retryable instead of
            // following the redirect somewhere else.
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .map_err(|e| format!("Failed to create session validator: {e}"))?;
        Ok(Self {
            client,
            base_url: base_url.into(),
        })
    }
}

impl SessionValidator for HttpSessionValidator {
    fn validate<'a>(
        &'a self,
        token: &'a str,
        device_id: Option<&'a str>,
    ) -> ValidationFuture<'a> {
        Box::pin(async move {
            let url = crate::config::join_api_url(&self.base_url, SESSION_VALIDATION_PATH);
            let mut request = self
                .client
                .get(url)
                .header("Authorization", format!("Bearer {token}"));

            let expected_device_id = device_id.filter(|value| !value.trim().is_empty());

            if let Some(device_id) = expected_device_id {
                request = request.header("X-Device-ID", device_id);
            }

            match request.send().await {
                Ok(response) if response.status().is_success() => match response.text().await {
                    Ok(body) => classify_status_body(expected_device_id, &body),
                    Err(error) => ValidationOutcome::Unavailable(format!(
                        "Session validation response could not be read: {error}"
                    )),
                },
                Ok(response) if matches!(response.status().as_u16(), 401 | 403) => {
                    ValidationOutcome::Rejected
                }
                Ok(response) => ValidationOutcome::Unavailable(format!(
                    "Session validation returned HTTP {}",
                    response.status().as_u16()
                )),
                Err(error) => ValidationOutcome::Unavailable(format!(
                    "Session validation request failed: {error}"
                )),
            }
        })
    }
}

/// Decide whether an authenticated status response proves this exact session.
///
/// Only `status: "connected"` together with the device id the record was
/// issued to restores a session. A `disconnected` answer is definitive (the
/// device is missing or owned by another account), so it is treated like a
/// rejection. An unreadable body is treated as retryable: a captive portal or
/// misbehaving proxy must not sign the user out by returning HTML with a 200.
fn classify_status_body(expected_device_id: Option<&str>, body: &str) -> ValidationOutcome {
    let status: StatusResponse = match serde_json::from_str(body) {
        Ok(status) => status,
        Err(_) => {
            return ValidationOutcome::Unavailable(
                "Session validation returned an unreadable status response".to_string(),
            )
        }
    };

    if status.status != "connected" {
        return match status.status.as_str() {
            "disconnected" => ValidationOutcome::Rejected,
            other => ValidationOutcome::Unavailable(format!(
                "Session validation reported status {other}"
            )),
        };
    }

    let returned_device_id = status.device_id.as_deref().unwrap_or_default();
    match expected_device_id {
        Some(expected) if returned_device_id == expected => ValidationOutcome::Valid,
        // Either the record has no device binding or the backend reported a
        // different one. Neither can ever prove this is the saved session.
        _ => ValidationOutcome::Rejected,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RestoreOutcome {
    Restored(SavedSession),
    Absent,
    FailedClosed {
        /// True when the saved session was removed because it could never be
        /// valid again (origin change, rejected token, corrupted record).
        cleared: bool,
        detail: String,
    },
}

/// Restore a saved session only when it belongs to the effective backend
/// origin and the backend still accepts its token.
pub async fn restore_saved_session(
    store: &dyn SessionStore,
    effective_origin: &str,
    validator: &dyn SessionValidator,
) -> RestoreOutcome {
    if effective_origin.trim().is_empty() {
        return RestoreOutcome::FailedClosed {
            cleared: false,
            detail: "Effective backend origin is unavailable".to_string(),
        };
    }

    let saved = match store.load() {
        Ok(Some(saved)) => saved,
        Ok(None) => return RestoreOutcome::Absent,
        Err(error) => {
            return RestoreOutcome::FailedClosed {
                cleared: false,
                detail: error,
            }
        }
    };

    if saved.backend_origin != effective_origin {
        let cleared = clear_saved_session(store, Some(&saved.user.email)).is_ok();
        return RestoreOutcome::FailedClosed {
            cleared,
            detail: "Saved session belongs to a different backend origin".to_string(),
        };
    }

    let device_id = if saved.device_id.trim().is_empty() {
        None
    } else {
        Some(saved.device_id.as_str())
    };

    match validator.validate(&saved.token, device_id).await {
        ValidationOutcome::Valid => RestoreOutcome::Restored(saved),
        ValidationOutcome::Rejected => {
            let cleared = clear_saved_session(store, Some(&saved.user.email)).is_ok();
            RestoreOutcome::FailedClosed {
                cleared,
                detail: "Saved session was rejected by the backend".to_string(),
            }
        }
        ValidationOutcome::Unavailable(detail) => RestoreOutcome::FailedClosed {
            cleared: false,
            // Kept across launches: a backend outage must not silently sign the
            // user out, but it must also never restore an unvalidated token.
            detail,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::Mutex;
    use std::thread;

    fn saved_session() -> SavedSession {
        SavedSession {
            token: "secret-token".to_string(),
            user: SessionUser {
                id: "user-1".to_string(),
                email: "user@example.com".to_string(),
                first_name: "Ada".to_string(),
                last_name: "Lovelace".to_string(),
            },
            device_id: "device-1".to_string(),
            backend_origin: "http://127.0.0.1:8123".to_string(),
        }
    }

    #[derive(Default)]
    struct FakeStore {
        state: Mutex<FakeStoreState>,
    }

    #[derive(Default)]
    struct FakeStoreState {
        session: Option<SavedSession>,
        events: Vec<String>,
        fail_delete_record: bool,
        fail_delete_token: bool,
    }

    impl FakeStore {
        fn with_session(session: SavedSession) -> Self {
            let store = Self::default();
            store.state.lock().unwrap().session = Some(session);
            store
        }

        fn session(&self) -> Option<SavedSession> {
            self.state.lock().unwrap().session.clone()
        }

        fn events(&self) -> Vec<String> {
            self.state.lock().unwrap().events.clone()
        }
    }

    impl SessionStore for FakeStore {
        fn load(&self) -> Result<Option<SavedSession>, String> {
            Ok(self.state.lock().unwrap().session.clone())
        }

        fn save(&self, session: &SavedSession) -> Result<(), String> {
            self.state.lock().unwrap().session = Some(session.clone());
            Ok(())
        }

        fn delete_record(&self) -> Result<(), String> {
            let mut state = self.state.lock().unwrap();
            state.events.push("record".to_string());
            if state.fail_delete_record {
                return Err("record delete failed".to_string());
            }
            state.session = None;
            Ok(())
        }

        fn delete_token(&self, email: &str) -> Result<(), String> {
            let mut state = self.state.lock().unwrap();
            state.events.push(format!("token:{email}"));
            if state.fail_delete_token {
                return Err("token delete failed".to_string());
            }
            Ok(())
        }
    }

    struct FakeValidator {
        outcome: ValidationOutcome,
        calls: Mutex<Vec<(String, Option<String>)>>,
    }

    impl FakeValidator {
        fn new(outcome: ValidationOutcome) -> Self {
            Self {
                outcome,
                calls: Mutex::new(Vec::new()),
            }
        }

        fn calls(&self) -> Vec<(String, Option<String>)> {
            self.calls.lock().unwrap().clone()
        }
    }

    impl SessionValidator for FakeValidator {
        fn validate<'a>(
            &'a self,
            token: &'a str,
            device_id: Option<&'a str>,
        ) -> ValidationFuture<'a> {
            let outcome = self.outcome.clone();
            self.calls
                .lock()
                .unwrap()
                .push((token.to_string(), device_id.map(str::to_string)));
            Box::pin(async move { outcome })
        }
    }

    #[test]
    fn record_never_contains_the_token() {
        let session = saved_session();
        let record = SessionRecord::from(&session);
        let raw = serde_json::to_string(&record).unwrap();

        assert!(!raw.contains(&session.token));
        assert!(raw.contains("user@example.com"));
        assert!(raw.contains("http://127.0.0.1:8123"));
        assert!(raw.contains("\"version\":1"));
    }

    #[test]
    fn record_decode_rejects_unknown_versions_and_missing_fields() {
        let record = SessionRecord::from(&saved_session());
        let mut value = serde_json::to_value(&record).unwrap();
        value["version"] = serde_json::json!(99);
        assert!(decode_record(&value.to_string()).is_err());

        let mut value = serde_json::to_value(&record).unwrap();
        value["backend_origin"] = serde_json::json!("   ");
        assert!(decode_record(&value.to_string()).is_err());

        assert!(decode_record("not-json").is_err());
    }

    #[test]
    fn saving_refuses_incomplete_sessions() {
        let mut session = saved_session();
        session.token = "".to_string();
        assert!(validate_session(&session).is_err());

        let mut session = saved_session();
        session.user.email = "".to_string();
        assert!(validate_session(&session).is_err());

        let mut session = saved_session();
        session.backend_origin = "".to_string();
        assert!(validate_session(&session).is_err());
    }

    #[tokio::test]
    async fn restores_matching_origin_after_authenticated_validation() {
        let session = saved_session();
        let store = FakeStore::with_session(session.clone());
        let validator = FakeValidator::new(ValidationOutcome::Valid);

        let outcome = restore_saved_session(&store, "http://127.0.0.1:8123", &validator).await;

        assert_eq!(outcome, RestoreOutcome::Restored(session));
        assert_eq!(
            validator.calls(),
            vec![("secret-token".to_string(), Some("device-1".to_string()))]
        );
        assert!(store.session().is_some());
    }

    #[tokio::test]
    async fn origin_mismatch_clears_the_session_without_calling_the_backend() {
        let store = FakeStore::with_session(saved_session());
        let validator = FakeValidator::new(ValidationOutcome::Valid);

        let outcome = restore_saved_session(&store, "http://127.0.0.1:8124", &validator).await;

        assert_eq!(
            outcome,
            RestoreOutcome::FailedClosed {
                cleared: true,
                detail: "Saved session belongs to a different backend origin".to_string(),
            }
        );
        assert!(validator.calls().is_empty());
        assert!(store.session().is_none());
        assert_eq!(
            store.events(),
            vec![
                "record".to_string(),
                "token:user@example.com".to_string()
            ]
        );
    }

    #[tokio::test]
    async fn rejected_token_is_deleted() {
        let store = FakeStore::with_session(saved_session());
        let validator = FakeValidator::new(ValidationOutcome::Rejected);

        let outcome = restore_saved_session(&store, "http://127.0.0.1:8123", &validator).await;

        assert_eq!(
            outcome,
            RestoreOutcome::FailedClosed {
                cleared: true,
                detail: "Saved session was rejected by the backend".to_string(),
            }
        );
        assert!(store.session().is_none());
    }

    #[tokio::test]
    async fn transient_validation_failure_keeps_the_session_for_a_later_launch() {
        let session = saved_session();
        let store = FakeStore::with_session(session.clone());
        let validator =
            FakeValidator::new(ValidationOutcome::Unavailable("backend offline".to_string()));

        let outcome = restore_saved_session(&store, "http://127.0.0.1:8123", &validator).await;

        assert_eq!(
            outcome,
            RestoreOutcome::FailedClosed {
                cleared: false,
                detail: "backend offline".to_string(),
            }
        );
        assert_eq!(store.session(), Some(session));
    }

    #[tokio::test]
    async fn absent_session_and_missing_effective_origin_fail_closed() {
        let store = FakeStore::default();
        let validator = FakeValidator::new(ValidationOutcome::Valid);

        assert_eq!(
            restore_saved_session(&store, "http://127.0.0.1:8123", &validator).await,
            RestoreOutcome::Absent
        );
        assert!(validator.calls().is_empty());

        let store = FakeStore::with_session(saved_session());
        let outcome = restore_saved_session(&store, "   ", &validator).await;
        assert_eq!(
            outcome,
            RestoreOutcome::FailedClosed {
                cleared: false,
                detail: "Effective backend origin is unavailable".to_string(),
            }
        );
        assert!(store.session().is_some());
        assert!(validator.calls().is_empty());
    }

    #[test]
    fn clearing_deletes_record_before_token_and_is_idempotent() {
        let store = FakeStore::with_session(saved_session());

        clear_saved_session(&store, Some("user@example.com")).unwrap();

        assert_eq!(
            store.events(),
            vec![
                "record".to_string(),
                "token:user@example.com".to_string()
            ]
        );
        assert!(store.session().is_none());

        clear_saved_session(&store, None).unwrap();
        assert_eq!(
            store.events(),
            vec![
                "record".to_string(),
                "token:user@example.com".to_string(),
                "record".to_string()
            ]
        );
    }

    #[test]
    fn clearing_uses_the_in_memory_email_when_the_record_is_missing() {
        let store = FakeStore::default();

        clear_saved_session(&store, Some("logout@example.com")).unwrap();

        assert_eq!(
            store.events(),
            vec![
                "record".to_string(),
                "token:logout@example.com".to_string()
            ]
        );
    }

    #[test]
    fn cleanup_failures_are_reported_without_credentials() {
        let store = FakeStore::with_session(saved_session());
        {
            let mut state = store.state.lock().unwrap();
            state.fail_delete_record = true;
            state.fail_delete_token = true;
        }

        let error = clear_saved_session(&store, Some("user@example.com")).unwrap_err();

        assert!(error.contains("record delete failed"));
        assert!(error.contains("token delete failed"));
        assert!(!error.contains("secret-token"));
    }

    fn spawn_status_server(
        status: &'static str,
        body: &'static str,
    ) -> (String, thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind scratch server");
        let address = listener.local_addr().expect("scratch server address");
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept scratch request");
            stream
                .set_read_timeout(Some(Duration::from_secs(5)))
                .expect("set read timeout");
            let mut request = Vec::new();
            let mut buffer = [0u8; 1024];
            loop {
                let read = stream.read(&mut buffer).expect("read scratch request");
                if read == 0 {
                    break;
                }
                request.extend_from_slice(&buffer[..read]);
                if request.windows(4).any(|window| window == b"\r\n\r\n") {
                    break;
                }
            }
            let response = format!(
                "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            stream
                .write_all(response.as_bytes())
                .expect("write scratch response");
            String::from_utf8_lossy(&request).to_string()
        });
        (format!("http://127.0.0.1:{}", address.port()), handle)
    }

    #[tokio::test]
    async fn http_validator_sends_authenticated_status_request() {
        let (base_url, server) = spawn_status_server(
            "200 OK",
            r#"{"status":"connected","device_id":"device-1"}"#,
        );
        let validator = HttpSessionValidator::new(base_url).unwrap();

        let outcome = validator.validate("secret-token", Some("device-1")).await;
        let request = server.join().unwrap().to_ascii_lowercase();

        assert_eq!(outcome, ValidationOutcome::Valid);
        assert!(request.starts_with("get /api/menubar/status "));
        assert!(request.contains("authorization: bearer secret-token"));
        assert!(request.contains("x-device-id: device-1"));
    }

    async fn validate_against_local_mock(body: &'static str) -> (ValidationOutcome, String) {
        let (base_url, server) = spawn_status_server("200 OK", body);
        let validator = HttpSessionValidator::new(base_url).unwrap();
        let outcome = validator.validate("secret-token", Some("device-1")).await;
        (outcome, server.join().unwrap())
    }

    #[tokio::test]
    async fn http_validator_requires_connected_status_and_matching_device_id() {
        // The status endpoint answers 200 for a missing/foreign device id, so
        // only a connected status for the saved device may restore a session.
        let (outcome, request) = validate_against_local_mock(
            r#"{"status":"connected","device_id":"device-1","server_time":"2026-11-14T00:00:00Z"}"#,
        )
        .await;
        assert_eq!(outcome, ValidationOutcome::Valid);
        assert!(request
            .to_ascii_lowercase()
            .contains("x-device-id: device-1"));

        let (outcome, _) = validate_against_local_mock(
            r#"{"status":"disconnected","server_time":"2026-11-14T00:00:00Z"}"#,
        )
        .await;
        assert_eq!(outcome, ValidationOutcome::Rejected);

        let (outcome, _) = validate_against_local_mock(
            r#"{"status":"connected","device_id":"device-2"}"#,
        )
        .await;
        assert_eq!(outcome, ValidationOutcome::Rejected);

        // A connected answer without the device binding cannot prove the record
        // is for the device the backend reports.
        let (outcome, _) =
            validate_against_local_mock(r#"{"status":"connected"}"#).await;
        assert_eq!(outcome, ValidationOutcome::Rejected);
    }

    #[tokio::test]
    async fn http_validator_fails_closed_on_malformed_or_error_status_bodies() {
        for body in ["not-json", r#"{"device_id":"device-1"}"#] {
            let (outcome, _) = validate_against_local_mock(body).await;
            match outcome {
                ValidationOutcome::Unavailable(detail) => {
                    assert!(detail.contains("unreadable"), "unexpected detail: {detail}");
                    assert!(!detail.contains("secret-token"));
                }
                other => panic!("expected Unavailable for {body}, got {other:?}"),
            }
        }

        // A 200 `error` state is retryable (the backend could not answer), not
        // a reason to delete an otherwise valid credential.
        let (outcome, _) =
            validate_against_local_mock(r#"{"status":"error","server_time":"x"}"#).await;
        match outcome {
            ValidationOutcome::Unavailable(detail) => {
                assert!(detail.contains("error"), "unexpected detail: {detail}");
            }
            other => panic!("expected Unavailable for error status, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn http_validator_refuses_connected_without_a_saved_device_binding() {
        let (base_url, server) = spawn_status_server(
            "200 OK",
            r#"{"status":"connected","device_id":"device-1"}"#,
        );
        let validator = HttpSessionValidator::new(base_url).unwrap();

        let outcome = validator.validate("secret-token", None).await;
        server.join().unwrap();

        assert_eq!(outcome, ValidationOutcome::Rejected);
    }

    /// Run the real restore gate against a local status mock.
    async fn restore_against_local_mock(
        body: &'static str,
        saved_device_id: &'static str,
    ) -> (RestoreOutcome, Option<SavedSession>) {
        let (base_url, server) = spawn_status_server("200 OK", body);
        let mut session = saved_session();
        session.backend_origin = base_url.clone();
        session.device_id = saved_device_id.to_string();
        let origin = session.backend_origin.clone();
        let store = FakeStore::with_session(session);
        let validator = HttpSessionValidator::new(base_url).unwrap();

        let outcome = restore_saved_session(&store, &origin, &validator).await;
        server.join().unwrap();
        (outcome, store.session())
    }

    #[tokio::test]
    async fn restore_only_succeeds_for_a_connected_status_with_the_saved_device() {
        let body = r#"{"status":"connected","device_id":"device-1","server_time":"2026-11-14T00:00:00Z"}"#;
        let (outcome, kept) = restore_against_local_mock(body, "device-1").await;
        match outcome {
            RestoreOutcome::Restored(saved) => assert_eq!(saved.device_id, "device-1"),
            other => panic!("expected the matching session to restore, got {other:?}"),
        }
        assert!(kept.is_some());

        let (outcome, kept) = restore_against_local_mock(
            r#"{"status":"disconnected","server_time":"2026-11-14T00:00:00Z"}"#,
            "device-1",
        )
        .await;
        assert!(matches!(
            outcome,
            RestoreOutcome::FailedClosed { cleared: true, .. }
        ));
        assert!(kept.is_none());

        let (outcome, kept) = restore_against_local_mock(
            r#"{"status":"connected","device_id":"device-2"}"#,
            "device-1",
        )
        .await;
        assert!(matches!(
            outcome,
            RestoreOutcome::FailedClosed { cleared: true, .. }
        ));
        assert!(kept.is_none());

        let (outcome, kept) = restore_against_local_mock("not-json", "device-1").await;
        assert!(matches!(
            outcome,
            RestoreOutcome::FailedClosed { cleared: false, .. }
        ));
        assert!(kept.is_some());
    }

    #[tokio::test]
    async fn http_validator_classifies_rejections_and_retryable_failures() {
        for (status, body, expected) in [
            (
                "401 Unauthorized",
                r#"{"detail":"expired"}"#,
                ValidationOutcome::Rejected,
            ),
            (
                "403 Forbidden",
                r#"{"detail":"denied"}"#,
                ValidationOutcome::Rejected,
            ),
        ] {
            let (base_url, server) = spawn_status_server(status, body);
            let validator = HttpSessionValidator::new(base_url).unwrap();
            let outcome = validator.validate("token", None).await;
            server.join().unwrap();

            assert_eq!(outcome, expected);
        }

        for status in ["302 Found", "503 Service Unavailable"] {
            let (base_url, server) = spawn_status_server(status, "{}");
            let validator = HttpSessionValidator::new(base_url).unwrap();
            let outcome = validator.validate("token", None).await;
            server.join().unwrap();

            match outcome {
                ValidationOutcome::Unavailable(detail) => {
                    assert!(detail.contains(status.split(' ').next().unwrap()));
                    assert!(!detail.contains("token"));
                }
                other => panic!("expected Unavailable for {status}, got {other:?}"),
            }
        }
    }
}
