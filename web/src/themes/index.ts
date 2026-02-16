import type { Theme } from './types'
import { peckTheme } from './peck'

const themes: Record<string, Theme> = {
  peck: peckTheme,
}

export function getTheme(name: string): Theme {
  return themes[name] ?? themes.peck
}

export type { Theme, ThemePalette, ThemeTypography } from './types'
export { peckTheme } from './peck'
