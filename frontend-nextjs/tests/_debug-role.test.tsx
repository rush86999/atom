import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RoleSettings from '../components/Agents/RoleSettings';

const mockRole = {
  id: 'test-role-1', name: 'Test Role', description: 'A test role',
  capabilities: ['test_capability'],
  permissions: { canAccessFiles: true, canAccessWeb: false, canExecuteCode: false, canAccessDatabase: false, canSendEmails: false, canMakeAPICalls: false },
  systemPrompt: 'You are a test assistant',
  modelConfig: { model: 'gpt-4', temperature: 0.7, maxTokens: 1000, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
  isDefault: false, createdAt: new Date(), updatedAt: new Date(),
};

test('debug permissions accordion', async () => {
  const user = userEvent.setup();
  render(<RoleSettings initialRoles={[mockRole]} />);
  await screen.findByText('Test Role');
  const editBtn = screen.getAllByRole('button').find((b) => b.querySelector('.lucide-square-pen'));
  await user.click(editBtn!);
  const dialog = await screen.findByRole('dialog');
  const form = within(dialog);
  const permTrigger = form.getByRole('button', { name: 'Permissions' });
  console.log('PERM TRIGGER FOUND:', !!permTrigger);
  await user.click(permTrigger);
  const switches = form.getAllByRole('switch');
  console.log('SWITCHES AFTER EXPAND:', switches.length);
  if (switches.length) console.log('SWITCH[0] id/aria:', switches[0].getAttribute('id'), switches[0].getAttribute('aria-checked'));
  // dump labels
  const labels = form.getAllByText(/Can Access/i);
  console.log('LABELS MATCHING /Can Access/i:', labels.length);
  labels.forEach(l => console.log('LABEL text:', l.textContent, 'for:', l.getAttribute('for')));
  const webToggle = form.getByLabelText('Can Access Web');
  console.log('WEB TOGGLE FOUND:', !!webToggle);
});
