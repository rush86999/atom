import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { mockAllScreens, SCREEN_TEST_IDS } from '../helpers/navigationMocks';

// Screen content is controlled; both navigator implementations are real.
mockAllScreens();
// Only canvas content is doubled: registration, linking and parent navigators
// remain real. Its WebView native host is qualified in the component lane.
jest.mock('../../screens/canvas/CanvasViewerScreen', () => ({CanvasViewerScreen: ({route}: {route: {params: {canvasId: string}}}) => {
  const React = require('react'); const {Text} = require('react-native');
  return React.createElement(Text, {testID: 'linked-canvas-viewer'}, route.params.canvasId);
}}));

let mockSignedIn = true;
beforeEach(() => { mockSignedIn = true; });
jest.mock('../../contexts/AuthContext', () => ({useAuth: () => ({isAuthenticated: mockSignedIn, isLoading: false})}));
const {AuthNavigator}: typeof import('../../navigation/AuthNavigator') = require('../../navigation/AuthNavigator');

test('authenticated root mounts the real tab navigator under one navigation container', async () => {
  const view = render(<AuthNavigator />);
  await waitFor(() => expect(view.getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy());
  expect(view.queryByTestId('login-screen')).toBeNull();
});


test.each([
  {path: 'workflow/wf-123', tab: 'WorkflowsTab', screen: 'WorkflowDetail', params: {workflowId: 'wf-123'}},
  {path: 'agent/agent-123', tab: 'AgentsTab', screen: 'AgentChat', params: {agentId: 'agent-123'}},
  {path: 'execution/exec-123', tab: 'WorkflowsTab', screen: 'ExecutionProgress', params: {executionId: 'exec-123'}},
  {path: 'workflow/PO%2F0007?source=review', tab: 'WorkflowsTab', screen: 'WorkflowDetail', params: {workflowId: 'PO/0007', source: 'review'}},
])('real parser resolves $path with exact leaf identity', ({path, tab, screen, params}) => {
  const {getStateFromPath} = jest.requireActual('@react-navigation/native');
  const {linking} = require('../../navigation/AuthNavigator');
  const state = getStateFromPath(path, linking.config);
  expect(state).toMatchObject({routes: [{name: 'Main', state: {routes: [{name: tab, state: {routes: [{name: screen, params}]}}]}}]});
});

test('canvas deep link targets the actual registered viewer name', () => {
  const {getStateFromPath} = jest.requireActual('@react-navigation/native');
  const {linking} = require('../../navigation/AuthNavigator');
  expect(getStateFromPath('canvas/canvas-123', linking.config)).toMatchObject({routes: [{name: 'CanvasViewer', params: {canvasId: 'canvas-123'}}]});
});

test('logout and login switch the real root without retaining protected tabs', async () => {
  const view = render(<AuthNavigator />);
  await waitFor(() => expect(view.getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy());
  mockSignedIn = false;
  view.rerender(<AuthNavigator />);
  await waitFor(() => expect(view.getByTestId('login-screen')).toBeTruthy());
  expect(view.queryByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeNull();
  mockSignedIn = true;
  view.rerender(<AuthNavigator />);
  await waitFor(() => expect(view.getByTestId(SCREEN_TEST_IDS.WORKFLOWS_LIST)).toBeTruthy());
  expect(view.queryByTestId('login-screen')).toBeNull();
});


test.each([true, false])('canvas initial link is protected when signedIn=%s', async signedIn => {
  mockSignedIn = signedIn;
  const {Linking} = require('react-native');
  const initialUrl = jest.spyOn(Linking, 'getInitialURL').mockResolvedValue('atom://canvas/canvas-123');
  try {
    const view = render(<AuthNavigator />);
    if (signedIn) await waitFor(() => expect(view.getByTestId('linked-canvas-viewer').props.children).toBe('canvas-123'));
    else {
      await waitFor(() => expect(view.getByTestId('login-screen')).toBeTruthy());
      expect(view.queryByTestId('linked-canvas-viewer')).toBeNull();
    }
  } finally { initialUrl.mockRestore(); }
});
