/**
 * Agents-page guidance must distinguish training/readiness from a reviewed
 * promotion, and must not promise approval for every action.
 */
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import { EmployeeOnboardingGuide } from '../EmployeeOnboardingGuide';

function renderGuide() {
  render(<EmployeeOnboardingGuide />);
  const restore = screen.queryByTestId('agent-guide-restore');
  if (restore) fireEvent.click(restore);
}

describe('EmployeeOnboardingGuide truthful lifecycle copy', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('requires readiness and a review of actual work, not automatic graduation', () => {
    renderGuide();
    const lifecycle = screen.getByTestId('agent-guide-lifecycle');
    expect(lifecycle).toHaveTextContent(/readiness requirements/i);
    expect(lifecycle).toHaveTextContent(/review of the employee's actual work for the role/i);
    expect(lifecycle).toHaveTextContent(/owner exception/i);
    expect(lifecycle).toHaveTextContent(/recorded with its reason/i);
    expect(lifecycle).toHaveTextContent(/domain selectors do not create exemptions/i);
    expect(lifecycle).toHaveTextContent(/domain rules can still require human review/i);
    expect(lifecycle).not.toHaveTextContent(/every clean run builds confidence/i);
    expect(lifecycle).not.toHaveTextContent(/automatically as they earn trust/i);
  });

  it('describes STUDENT as read-only instead of inventing approval for every action', () => {
    renderGuide();
    const supervision = screen.getByTestId('agent-guide-supervision');
    expect(supervision).toHaveTextContent(/read-only/i);
    expect(supervision).toHaveTextContent(/cannot change anything/i);
    expect(supervision).toHaveTextContent(/high-risk steps and domain rules still pause for review/i);
    expect(supervision).not.toHaveTextContent(/approval for every action/i);
  });
});
