import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { UserProfile } from '../types';

interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: RegisterData) => Promise<void>;
  updateProfile: (updates: Partial<UserProfile>) => Promise<void>;
  refreshToken: () => Promise<void>;
}

interface RegisterData {
  email: string;
  password: string;
  name: string;
  preferences?: any;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Check for existing session on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('authToken');
        const userData = localStorage.getItem('userData');

        if (token && userData) {
          const user = JSON.parse(userData);
          setAuthState({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } else {
          setAuthState(prev => ({ ...prev, isLoading: false }));
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        setAuthState(prev => ({
          ...prev,
          isLoading: false,
          error: 'Failed to restore session',
        }));
      }
    };

    checkAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      // Mock API call - replace with actual authentication
      const response = await mockAuthAPI('/login', { email, password });

      const { user, token } = response.data;

      localStorage.setItem('authToken', token);
      localStorage.setItem('userData', JSON.stringify(user));

      setAuthState({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Login failed',
      }));
      throw error;
    }
  };

  const register = async (userData: RegisterData) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await mockAuthAPI('/register', userData);
      const { user, token } = response.data;

      localStorage.setItem('authToken', token);
      localStorage.setItem('userData', JSON.stringify(user));

      setAuthState({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Registration failed',
      }));
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');

    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  };

  const updateProfile = async (updates: Partial<UserProfile>) => {
    if (!authState.user) throw new Error('No user logged in');

    try {
      const response = await mockAuthAPI('/profile', updates, 'PATCH');
      const updatedUser = { ...authState.user, ...response.data };

      localStorage.setItem('userData', JSON.stringify(updatedUser));

      setAuthState(prev => ({
        ...prev,
        user: updatedUser,
      }));
    } catch (error: any) {
      setAuthState(prev => ({
        ...prev,
        error: error.message || 'Profile update failed',
      }));
      throw error;
    }
  };

  const refreshToken = async () => {
    try {
      const response = await mockAuthAPI('/refresh', {}, 'POST');
      const { token } = response.data;

      localStorage.setItem('authToken', token);
    } catch (error) {
      logout(); // Force logout if refresh fails
      throw error;
    }
  };

  const value: AuthContextType = {
    ...authState,
    login,
    logout,
    register,
    updateProfile,
    refreshToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Mock API function - replace with actual API calls
const mockAuthAPI = async (endpoint: string, data: any, method = 'POST') => {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 1000));

  if (endpoint === '/login') {
    if (data.email === 'demo@atom.com' && data.password === 'demo') {
      return {
        data: {
          user: {
            id: '1',
            name: 'Demo User',
            email: data.email,
            avatar: '',
            preferences: {},
            createdAt: new Date().toISOString(),
          },
          token: 'mock-jwt-token',
        },
      };
    } else {
      throw new Error('Invalid credentials');
    }
  }

  if (endpoint === '/register') {
    return {
      data: {
        user: {
          id: Date.now().toString(),
          name: data.name,
          email: data.email,
          avatar: '',
          preferences: data.preferences || {},
          createdAt: new Date().toISOString(),
        },
        token: 'mock-jwt-token',
      },
    };
  }

  if (endpoint === '/profile') {
    return {
      data: data, // Return the updates
    };
  }

  if (endpoint === '/refresh') {
    return {
      data: {
        token: 'refreshed-mock-jwt-token',
      },
    };
  }

  throw new Error('Unknown endpoint');
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Higher-order component for protected routes
export const withAuth = <P extends object>(
  Component: React.ComponentType<P>
) => {
  return (props: P) => {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
        </div>
      );
    }

    if (!isAuthenticated) {
      // Redirect to login or show login component
      return <LoginPrompt />;
    }

    return <Component {...props} />;
  };
};

const LoginPrompt: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Sign in to ATOM
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
            Access your intelligent workspace
          </p>
        </div>
        <AuthForm />
      </div>
    </div>
  );
};

const AuthForm: React.FC = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
  });

  const { login, register, isLoading, error } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (isLogin) {
        await login(formData.email, formData.password);
      } else {
        await register({
          email: formData.email,
          password: formData.password,
          name: formData.name,
        });
      }
    } catch (err) {
      // Error is handled by the context
    }
  };

  return (
    <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
      <div className="rounded-md shadow-sm -space-y-px">
        {!isLogin && (
          <div>
            <input
              type="text"
              required
              className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="Full Name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            />
          </div>
        )}
        <div>
          <input
            type="email"
            required
            className={`appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 ${
              isLogin ? 'rounded-t-md' : ''
            } focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm`}
            placeholder="Email address"
            value={formData.email}
            onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
          />
        </div>
        <div>
          <input
            type="password"
            required
            className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
            placeholder="Password"
            value={formData.password}
            onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
          />
        </div>
      </div>

      {error && (
        <div className="text-red-600 text-sm text-center">
          {error}
        </div>
      )}

      <div>
        <button
          type="submit"
          disabled={isLoading}
          className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {isLoading ? 'Processing...' : (isLogin ? 'Sign In' : 'Sign Up')}
        </button>
      </div>

      <div className="text-center">
        <button
          type="button"
          onClick={() => setIsLogin(!isLogin)}
          className="text-blue-600 hover:text-blue-500 text-sm"
        >
          {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
        </button>
      </div>
    </form>
  );
};
