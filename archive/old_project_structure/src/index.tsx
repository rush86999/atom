import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

import TauriChatInterface from './components/Chat/TauriChatInterface';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <TauriChatInterface />
  </React.StrictMode>
);