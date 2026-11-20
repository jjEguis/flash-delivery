import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { readTheme, resolveTheme, THEME_KEY, ThemeProvider } from '../../src/app/ThemeProvider';
import { ThemeSwitcher } from '../../src/app/AppShell';

describe('apariencia', () => {
  it('distingue preferencia de tema resuelto y admite valores inválidos o almacenamiento bloqueado', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
    expect(readTheme({ getItem: () => 'wrong' })).toBe('system');
    expect(readTheme({ getItem: () => { throw Error('blocked'); } })).toBe('system');
  });

  it('elige, guarda y restaura la preferencia explícita sin alterar la sesión', async () => {
    localStorage.setItem('fd.session', 'existing-session');
    const view = render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Apariencia' }), 'dark');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(localStorage.getItem('fd.session')).toBe('existing-session');
    view.unmount();
    render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
    expect(screen.getByRole('combobox')).toHaveValue('dark');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('reacciona al sistema solo cuando la preferencia es Sistema y elimina el listener', async () => {
    let listener = () => {};
    const media = { matches: false, addEventListener: vi.fn((_event, callback) => { listener = callback; }), removeEventListener: vi.fn() };
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    const view = render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
    act(() => { media.matches = true; listener(); });
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    await userEvent.selectOptions(screen.getByRole('combobox'), 'light');
    act(() => { media.matches = false; listener(); media.matches = true; listener(); });
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    await userEvent.selectOptions(screen.getByRole('combobox'), 'system');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    view.unmount();
    expect(media.removeEventListener).toHaveBeenCalledWith('change', listener);
  });

  it('permite cambiar aunque falle la escritura en localStorage', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw Error('blocked'); });
    render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
    await userEvent.selectOptions(screen.getByRole('combobox'), 'dark');
    expect(screen.getByRole('combobox')).toHaveValue('dark');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });
});
