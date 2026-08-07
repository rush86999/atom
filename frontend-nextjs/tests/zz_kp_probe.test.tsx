import React, { useState } from 'react';
import { render, fireEvent } from '@testing-library/react';
test('keyPress with change + code+charCode', () => {
  const fn = jest.fn();
  const C = () => {
    const [v, setV] = useState('');
    return <input value={v} onChange={(e) => setV(e.target.value)} onKeyPress={(e: any) => { fn(e); e.preventDefault(); }} />;
  };
  const { container } = render(<C />);
  const input = container.querySelector('input')!;
  fireEvent.change(input, { target: { value: 'sales' } });
  fireEvent.keyPress(input, { key: 'Enter', code: 'Enter', charCode: 13, preventDefault: jest.fn() });
  expect(fn).toHaveBeenCalled();
});
