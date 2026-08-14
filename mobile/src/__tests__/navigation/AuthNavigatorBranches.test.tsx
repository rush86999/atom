/**
 * AuthNavigator Branch Coverage Tests
 *
 * Covers two branches the main AuthNavigator suite cannot reach:
 * 1. The loading gate when isReady=true but isLoading=true (the `||`
 *    second operand in `!isReady || isLoading`).
 * 2. The authenticated ternary branches (initialRouteName 'Main' and the
 *    Main Stack.Screen) — the main suite renders the real AppNavigator
 *    directly because its nested NavigationContainer cannot mount inside
 *    AuthNavigator's own container; here AppNavigator is stubbed.
 */

import React from 'react';
import { View, Text } from 'react-native';
import { render, waitFor, act } from '@testing-library/react-native';

const mockLogin = jest.fn();
const mockLogout = jest.fn();
const mockRegister = jest.fn();
const mockRefreshToken = jest.fn();

let mockAuthState: any = {
  isAuthenticated: true,
  isLoading: false,
  user: { id: 'user-1', email: 'a@b.c' },
  token: 'tok',
  login: mockLogin,
  logout: mockLogout,
  register: mockRegister,
  refreshToken: mockRefreshToken,
};

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockAuthState,
}));

// Stub the real AppNavigator: it owns its own NavigationContainer, which
// react-navigation 6.4.x forbids nesting inside AuthNavigator's container.
// (react is resolved inside the factory — jest.mock factories may not
// reference out-of-scope imports.)
jest.mock('../../navigation/AppNavigator', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return {
    AppNavigator: () =>
      React.createElement(View, { testID: 'mock-main-navigator' },
        React.createElement(Text, null, 'Mock Main Navigator')
      ),
  };
});

const { AuthNavigator } = require('../../navigation/AuthNavigator');

describe('AuthNavigator branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
    mockAuthState = {
      isAuthenticated: true,
      isLoading: false,
      user: { id: 'user-1', email: 'a@b.c' },
      token: 'tok',
      login: mockLogin,
      logout: mockLogout,
      register: mockRegister,
      refreshToken: mockRefreshToken,
    };
  });

  it('should render the Main screen when authenticated', async () => {
    const { getByTestId, queryByTestId } = render(<AuthNavigator />);

    await waitFor(() => {
      expect(getByTestId('mock-main-navigator')).toBeTruthy();
    });
    // Auth screens must not mount while authenticated
    expect(queryByTestId('login-screen')).toBeNull();
  });

  it('should keep the loading gate when ready but still loading', async () => {
    mockAuthState = { ...mockAuthState, isLoading: true };

    const { queryByTestId } = render(<AuthNavigator />);

    // Let the isReady effect settle — with isLoading still true the gate
    // must persist (evaluates `!isReady || isLoading` with isReady=true).
    await act(async () => {});
    await waitFor(() => {
      expect(queryByTestId('login-screen')).toBeNull();
      expect(queryByTestId('mock-main-navigator')).toBeNull();
    });
  });
});
