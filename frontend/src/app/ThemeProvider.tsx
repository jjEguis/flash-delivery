import { createContext, useContext, useEffect, useLayoutEffect, useState } from 'react';
import type { ReactNode } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';
export const THEME_KEY = 'flashdelivery:theme:v1';
const query = '(prefers-color-scheme: dark)';

export function readTheme(storage?: Pick<Storage, 'getItem'>, fallback: ThemePreference = 'system'): ThemePreference {
  try {
    const value = storage?.getItem(THEME_KEY);
    if (value === 'light' || value === 'dark') return value;
  } catch { return fallback; }
  return 'system';
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): 'light' | 'dark' {
  return preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
}

type ThemeContextValue = { preference: ThemePreference; theme: 'light' | 'dark'; setPreference: (value: ThemePreference) => void };
const ThemeContext = createContext<ThemeContextValue | null>(null);
const useClientLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setValue] = useState<ThemePreference>(() => {
    const current = typeof document === 'undefined' ? undefined : document.documentElement.dataset.themePreference;
    const fallback: ThemePreference = current === 'light' || current === 'dark' ? current : 'system';
    try { return readTheme(typeof window === 'undefined' ? undefined : window.localStorage, fallback); } catch { return fallback; }
  });
  const [systemDark, setSystemDark] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  const theme = resolveTheme(preference, systemDark);

  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setSystemDark(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useClientLayoutEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.dataset.themePreference = preference; }, [theme, preference]);
  useEffect(() => {
    const update = (event: Event) => {
      const value = event instanceof CustomEvent ? event.detail : (event as StorageEvent).newValue;
      if (event instanceof StorageEvent && event.key !== THEME_KEY && event.key !== null) return;
      if (['system', 'light', 'dark'].includes(value)) setValue(value as ThemePreference);
      else if (event instanceof StorageEvent && value === null) setValue('system');
    };
    window.addEventListener('flashdelivery:theme-change', update);
    window.addEventListener('storage', update);
    return () => {window.removeEventListener('flashdelivery:theme-change', update);window.removeEventListener('storage', update);};
  }, []);

  function setPreference(value: ThemePreference) {
    setValue(value);
    try { window.localStorage.setItem(THEME_KEY, value); } catch { /* respaldo en estado React */ }
    window.dispatchEvent(new CustomEvent('flashdelivery:theme-change', {detail:value}));
  }
  return <ThemeContext.Provider value={{ preference, theme, setPreference }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('ThemeProvider no está disponible');
  return context;
}
