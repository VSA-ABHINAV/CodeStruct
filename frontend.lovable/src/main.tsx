import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { CodeStructWorkbench } from './features/workbench';
import './styles.css';

createRoot(document.getElementById('root')!).render(<StrictMode><CodeStructWorkbench /></StrictMode>);
