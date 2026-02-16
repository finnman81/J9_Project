/**
 * Peck theme — The Peck School (peckschool.org)
 * Deep slate blue, teal accent, yellow-orange highlight. Source Sans 3 throughout.
 */
import type { Theme } from './types'

export const peckTheme: Theme = {
  name: 'peck',
  appTitle: 'Peck Assessment',
  palette: {
    primary: '#315376',
    primaryAccent: '#385A7E',
    sidebarBg: '#3a5875',
    pattern: '#45678A',
    secondary: '#A7CBDE',
    highlight: '#FFC000',
    surface: '#FFFFFF',
    text: '#333333',
    textOnPrimary: '#FFFFFF',
    border: '#e0e0e0',
    riskLow: '#155724',
    riskMedium: '#856404',
    riskHigh: '#721c24',
  },
  typography: {
    fontHeading: '"Source Sans 3", "Source Sans Pro", system-ui, sans-serif',
    fontBody: '"Source Sans 3", "Source Sans Pro", system-ui, sans-serif',
  },
  radius: '6px',
  sidebarPattern: 'peck-pattern',
}
