import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import MenuBar from "./MenuBar";
import LoginScreen from "./components/LoginScreen";
import type { User, AuthState } from "./types";

function App() {
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
  });
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Check for existing session
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const session = await invoke<{ token: string; user: User } | null>("get_session");
      if (session) {
        setToken(session.token);
        setUser(session.user);
        setAuthState({ isAuthenticated: true, isLoading: false });
      } else {
        setAuthState({ isAuthenticated: false, isLoading: false });
      }
    } catch (error) {
      console.error("Failed to check session:", error);
      setAuthState({ isAuthenticated: false, isLoading: false });
    }
  };

  const handleLogin = async (
    email: string,
    password: string,
    totpCode?: string
  ) => {
    try {
      const result = await invoke<{ token: string; user: User; device_id: string }>(
        "login",
        {
          email,
          password,
          deviceName: "MenuBar",
          // Always include the key so the native Option<String> receives an
          // explicit null (None). LoginRequest still omits totp_code from the
          // HTTP body, so password-only requests are unchanged.
          totpCode: totpCode ?? null,
        }
      );

      setToken(result.token);
      setUser(result.user);
      setAuthState({ isAuthenticated: true, isLoading: false });
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await invoke("logout");
    } catch (error) {
      // Native logout clears in-memory state even when Keychain cleanup fails.
      // The UI must fail closed as well instead of leaving an authenticated
      // session on screen.
      console.error("Logout failed:", error);
    } finally {
      setToken(null);
      setUser(null);
      setAuthState({ isAuthenticated: false, isLoading: false });
    }
  };

  if (authState.isLoading) {
    return (
      <div className="menubar-container">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (!authState.isAuthenticated) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <MenuBar
      user={user}
      token={token}
      onLogout={handleLogout}
    />
  );
}

export default App;
