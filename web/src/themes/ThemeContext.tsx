/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { tokensToCssVars } from '../design-tokens'
import { getTheme } from './index'
import type { Theme } from './types'
import './peck.css'

const themeName = import.meta.env.VITE_THEME || 'peck'
const theme = getTheme(themeName)

const ThemeContext = createContext<Theme>(theme)

/** Theme overrides: map theme palette onto design token vars + legacy names for backward compat. */
function themeToCssOverrides(t: Theme): Record<string, string> {
  const p = t.palette
  return {
    '--color-brand-primary': p.primary,
    '--color-brand-primary-hover': p.primaryAccent ?? p.primary,
    '--color-bg-surface': p.surface,
    '--color-text-primary': p.text,
    '--color-text-inverse': p.textOnPrimary,
    '--color-border-default': p.border,
    '--color-border-subtle': p.border,
    '--color-primary': p.primary,
    '--color-primary-accent': p.primaryAccent ?? p.primary,
    '--color-pattern': p.pattern,
    '--color-secondary': p.secondary,
    '--color-highlight': p.highlight,
    '--color-surface': p.surface,
    '--color-text': p.text,
    '--color-text-on-primary': p.textOnPrimary,
    '--color-border': p.border,
    '--color-risk-low': p.riskLow,
    '--color-risk-medium': p.riskMedium,
    '--color-risk-high': p.riskHigh,
    '--font-family-sans': t.typography.fontBody,
    '--font-heading': t.typography.fontHeading,
    '--font-sans': t.typography.fontBody,
    '--radius': t.radius,
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const rootVars = useMemo(() => {
    const base = tokensToCssVars()
    const overrides = themeToCssOverrides(theme)
    const merged = { ...base, ...overrides }
    return Object.entries(merged)
      .map(([k, v]) => `${k}: ${v}`)
      .join('; ')
  }, [])

  return (
    <ThemeContext.Provider value={theme}>
      <style dangerouslySetInnerHTML={{ __html: `:root { ${rootVars} }` }} />
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
