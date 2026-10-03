import { StrictMode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CodeStructWorkbench } from './workbench';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it.runIf(Boolean(process.env.CODESTRUCT_LIVE_SMOKE))('loads a real backend analysis into graph, table and inspector', async () => {
  const origin = process.env.CODESTRUCT_LIVE_SMOKE!;
  const nativeFetch = globalThis.fetch;
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => nativeFetch(new URL(String(url), origin), options));
  render(<StrictMode><CodeStructWorkbench /></StrictMode>);
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Select authorized project' }).querySelectorAll('option').length).toBeGreaterThan(0));
  await waitFor(() => expect((screen.getByRole('button', { name: 'Analyze' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Analyze' }));
  await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/Analysis complete|Cached result|Partially completed/), { timeout: 15000 });
  fireEvent.click(screen.getByRole('button', { name: 'Accessible table' }));
  await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(1));
  const row = screen.getAllByRole('row')[1];
  fireEvent.click(row);
  expect(screen.getByLabelText('Selection inspector').textContent).toContain('Source location');
  expect(screen.getByLabelText('Selection inspector').textContent).toContain('Loaded relationships');
  expect(screen.queryByRole('alert')).toBeNull();
  expect(document.body.textContent).not.toContain('Demo data');
}, 20000);
