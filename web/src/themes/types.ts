/**
 * Theme contract: palette, typography, and optional assets.
 * Components consume CSS variables set by the active theme.
 */
export interface ThemePalette {
  primary: string
  primaryAccent: string
  /** Slightly desaturated/lighter for sidebar (optional) */
  sidebarBg?: string
  pattern: string
  secondary: string
  highlight: string
  surface: string
  text: string
  textOnPrimary: string
  border: string
  /** Risk/tier: On Track, Monitor, Needs Support */
  riskLow: string
  riskMedium: string
  riskHigh: string
}

export interface ThemeTypography {
  fontHeading: string
  fontBody: string
}

export interface Theme {
  name: string
  appTitle: string
  palette: ThemePalette
  typography: ThemeTypography
  radius: string
  /** Optional: CSS class for sidebar/header background pattern */
  sidebarPattern?: string
}
