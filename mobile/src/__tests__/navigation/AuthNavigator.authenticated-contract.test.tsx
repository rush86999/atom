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


test.each(['workflow/wf-123', 'agent/agent-123', 'execution/exec-123'])('real parser resolves %s to the registered authenticated tree', path => {
  const {getStateFromPath} = jest.requireActual('@react-navigation/native');
  const {linking} = require('../../navigation/AuthNavigator');
  const state = getStateFromPath(path, linking.config);
  expect(state.routes[0].name).toBe('Main');
});
