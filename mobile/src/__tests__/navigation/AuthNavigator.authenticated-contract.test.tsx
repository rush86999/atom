import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { mockAllScreens, SCREEN_TEST_IDS } from '../helpers/navigationMocks';

// Screen content is controlled; both navigator implementations are real.
mockAllScreens();
jest.mock('../../contexts/AuthContext', () => ({useAuth: () => ({isAuthenticated: true, isLoading: false})}));
const {AuthNavigator}: typeof import('../../navigation/AuthNavigator') = require('../../navigation/AuthNavigator');

test('authenticated root mounts the real tab navigator under one navigation container', async () => {
  const view = render(<AuthNavigator />);
  await waitFor(() => expect(view.getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy());
  expect(view.queryByTestId('login-screen')).toBeNull();
});
