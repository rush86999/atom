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

  const handleLogin = async (email: string, password: string) => {
    try {
      const result = await invoke<{ token: string; user: User; device_id: string }>(
        "login",
        { email, password, deviceName: "MenuBar" }
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
      setToken(null);
      setUser(null);
      setAuthState({ isAuthenticated: false, isLoading: false });
    } catch (error) {
      console.error("Logout failed:", error);
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
