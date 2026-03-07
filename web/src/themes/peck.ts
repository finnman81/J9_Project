/**
 * Peck theme — The Peck School (peckschool.org)
 * Deep slate blue, teal accent, yellow-orange highlight. Source Sans 3 throughout.
 */
import type { Theme } from './types'

export const peckTheme: Theme = {
  name: 'peck',
  appTitle: 'Peck Intelligence',
  palette: {
    primary: '#295BA7',
    primaryAccent: '#5D82D8',
    sidebarBg: '#F7FAFF',
    pattern: '#DCE8FF',
    secondary: '#B8CBF5',
    highlight: '#F3B455',
    surface: '#FFFFFF',
    text: '#14213D',
    textOnPrimary: '#FFFFFF',
    border: '#D9E2EC',
    riskLow: '#17663D',
    riskMedium: '#A8570C',
    riskHigh: '#B23754',
  },
  typography: {
    fontHeading: '"Source Sans 3", "Source Sans Pro", system-ui, sans-serif',
    fontBody: '"Source Sans 3", "Source Sans Pro", system-ui, sans-serif',
  },
  radius: '6px',
  sidebarPattern: 'peck-pattern',
}
