import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import { getConfig } from './config';

// App configuration and initialization
const APP_NAME = 'Tic Tac Toe';
const config = getConfig();
console.log(`Starting ${APP_NAME} v${config.version}...`);

const root = createRoot(document.getElementById('root'));
root.render(<App />);