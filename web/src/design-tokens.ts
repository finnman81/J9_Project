/**
 * Universal design token set — single source of truth for the application.
 * Enforces: readable base (15–16px), clear hierarchy, consistent rhythm,
 * comfortable tables, soft surfaces.
 *
 * Use tokensToCssVars(tokens) to inject as CSS custom properties.
 * Theme overrides (e.g. brand primary) are applied on top of these defaults.
 */

// -----------------------------------------------------------------------------
// Typography
// -----------------------------------------------------------------------------
export const font = {
  family: {
    sans:
      'Source Sans 3, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
    mono:
      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  },
  size: {
    xs: '12px',
    sm: '13px',
    md: '15px',
    lg: '16px',
    xl: '18px',
    '2xl': '20px',
    '3xl': '24px',
    '4xl': '32px',
    kpi: '34px',
  },
  weight: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  lineHeight: {
    tight: 1.2,
    snug: 1.3,
    normal: 1.45,
    relaxed: 1.6,
  },
  letterSpacing: {
    tight: '-0.01em',
    normal: '0',
    wide: '0.01em',
  },
} as const

// -----------------------------------------------------------------------------
// Spacing (8px grid)
// -----------------------------------------------------------------------------
export const space = {
  0: '0px',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  7: '28px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
} as const

// -----------------------------------------------------------------------------
// Radii + Shadows
// -----------------------------------------------------------------------------
export const radius = {
  sm: '8px',
  md: '12px',
  lg: '18px',
  xl: '24px',
} as const

export const shadow = {
  sm: '0 10px 30px rgba(24, 39, 75, 0.06)',
  md: '0 18px 48px rgba(24, 39, 75, 0.10)',
  focus: '0 0 0 3px rgba(72, 118, 255, 0.18)',
} as const

// -----------------------------------------------------------------------------
// Borders + Layout
// -----------------------------------------------------------------------------
export const border = {
  width: {
    hairline: '1px',
    strong: '2px',
  },
} as const

export const layout = {
  containerMax: '1400px',
  gutter: '24px',
  sectionGap: '28px',
} as const

// -----------------------------------------------------------------------------
// Color (dashboard neutral + education friendly)
// -----------------------------------------------------------------------------
export const color = {
  bg: {
    app: '#F4F7FB',
    surface: '#FFFFFF',
    surfaceMuted: '#EEF3F9',
  },
  text: {
    primary: '#14213D',
    secondary: '#31415F',
    muted: '#62748D',
    disabled: '#98A2B3',
    inverse: '#FFFFFF',
  },
  border: {
    subtle: '#D9E2EC',
    default: '#C7D3E0',
    strong: '#91A3BC',
  },
  brand: {
    primary: '#295BA7',
    primaryHover: '#204A89',
    primarySoft: '#EAF1FF',
  },
  focus: {
    ring: '#4876FF',
  },
  status: {
    core: { bg: '#E8F7EE', text: '#17663D', border: '#C8E8D4' },
    strategic: { bg: '#FFF3E4', text: '#A8570C', border: '#FFD6AE' },
    intensive: { bg: '#FFE8EC', text: '#B23754', border: '#F7C5D1' },
    stable: { bg: '#EEF3F9', text: '#415A77', border: '#D3DDE9' },
    improving: { bg: '#E7F4EC', text: '#17663D', border: '#BFE1CB' },
    declining: { bg: '#FFF0F2', text: '#B23754', border: '#F6CAD3' },
    unknown: { bg: '#F5F7FB', text: '#62748D', border: '#D9E2EC' },
  },
} as const

// -----------------------------------------------------------------------------
// Component tokens
// -----------------------------------------------------------------------------
export const button = {
  height: { sm: '32px', md: '40px', lg: '44px' },
  radius: '12px',
  paddingX: { sm: '10px', md: '14px', lg: '16px' },
  font: { size: '14px', weight: 600 },
} as const

export const input = {
  height: { md: '40px', lg: '44px' },
  radius: '12px',
  paddingX: '12px',
  font: { size: '14px', weight: 500 },
  placeholder: '#98A2B3',
} as const

export const card = {
  radius: '18px',
  padding: '22px',
  border: '#D9E2EC',
  shadow: '0 12px 34px rgba(24, 39, 75, 0.08)',
} as const

export const kpiCard = {
  padding: '22px',
  valueSize: '32px',
  labelSize: '13px',
} as const

export const table = {
  headerBg: '#F4F7FB',
  rowHoverBg: '#F8FBFF',
  border: '#D9E2EC',
  radius: '18px',
  fontSize: '15px',
  rowHeight: {
    comfortable: '56px',
    compact: '44px',
  },
} as const

// -----------------------------------------------------------------------------
// Aggregate token set
// -----------------------------------------------------------------------------
export const tokens = {
  font,
  space,
  radius,
  shadow,
  border,
  layout,
  color,
  button,
  input,
  card,
  kpiCard,
  table,
} as const

export type DesignTokens = typeof tokens

// -----------------------------------------------------------------------------
// Flatten tokens to CSS custom properties (--key-path: value)
// -----------------------------------------------------------------------------
function toKebab(s: string): string {
  return s.replace(/([A-Z])/g, '-$1').toLowerCase().replace(/^-/, '')
}

/** Convert design tokens to a flat object of CSS custom property key-value pairs for injection into a style. */
export function tokensToCssVars(t: DesignTokens = tokens): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(t.font.family)) {
    result[`--font-family-${toKebab(k)}`] = v
  }
  for (const [k, v] of Object.entries(t.font.size)) {
    result[`--font-size-${toKebab(k)}`] = v
  }
  for (const [k, v] of Object.entries(t.font.weight)) {
    result[`--font-weight-${toKebab(k)}`] = String(v)
  }
  for (const [k, v] of Object.entries(t.font.lineHeight)) {
    result[`--font-line-height-${toKebab(k)}`] = String(v)
  }
  for (const [k, v] of Object.entries(t.font.letterSpacing)) {
    result[`--font-letter-spacing-${toKebab(k)}`] = v
  }
  for (const [k, v] of Object.entries(t.space)) {
    result[`--space-${k}`] = v
  }
  for (const [k, v] of Object.entries(t.radius)) {
    result[`--radius-${toKebab(k)}`] = v
  }
  for (const [k, v] of Object.entries(t.shadow)) {
    result[`--shadow-${toKebab(k)}`] = v
  }
  result['--border-width-hairline'] = t.border.width.hairline
  result['--border-width-strong'] = t.border.width.strong
  result['--layout-container-max'] = t.layout.containerMax
  result['--layout-gutter'] = t.layout.gutter
  result['--layout-section-gap'] = t.layout.sectionGap

  result['--color-bg-app'] = t.color.bg.app
  result['--color-bg-surface'] = t.color.bg.surface
  result['--color-bg-surface-muted'] = t.color.bg.surfaceMuted
  result['--color-text-primary'] = t.color.text.primary
  result['--color-text-secondary'] = t.color.text.secondary
  result['--color-text-muted'] = t.color.text.muted
  result['--color-text-disabled'] = t.color.text.disabled
  result['--color-text-inverse'] = t.color.text.inverse
  result['--color-border-subtle'] = t.color.border.subtle
  result['--color-border-default'] = t.color.border.default
  result['--color-border-strong'] = t.color.border.strong
  result['--color-brand-primary'] = t.color.brand.primary
  result['--color-brand-primary-hover'] = t.color.brand.primaryHover
  result['--color-brand-primary-soft'] = t.color.brand.primarySoft
  result['--color-focus-ring'] = t.color.focus.ring
  for (const [statusKey, statusVal] of Object.entries(t.color.status)) {
    result[`--color-status-${toKebab(statusKey)}-bg`] = statusVal.bg
    result[`--color-status-${toKebab(statusKey)}-text`] = statusVal.text
    result[`--color-status-${toKebab(statusKey)}-border`] = statusVal.border
  }

  result['--button-height-sm'] = t.button.height.sm
  result['--button-height-md'] = t.button.height.md
  result['--button-height-lg'] = t.button.height.lg
  result['--button-radius'] = t.button.radius
  result['--button-padding-x-sm'] = t.button.paddingX.sm
  result['--button-padding-x-md'] = t.button.paddingX.md
  result['--button-padding-x-lg'] = t.button.paddingX.lg
  result['--button-font-size'] = t.button.font.size
  result['--button-font-weight'] = String(t.button.font.weight)

  result['--input-height-md'] = t.input.height.md
  result['--input-height-lg'] = t.input.height.lg
  result['--input-radius'] = t.input.radius
  result['--input-padding-x'] = t.input.paddingX
  result['--input-font-size'] = t.input.font.size
  result['--input-font-weight'] = String(t.input.font.weight)
  result['--input-placeholder'] = t.input.placeholder

  result['--card-radius'] = t.card.radius
  result['--card-padding'] = t.card.padding
  result['--card-border'] = t.card.border
  result['--card-shadow'] = t.card.shadow

  result['--kpi-card-padding'] = t.kpiCard.padding
  result['--kpi-card-value-size'] = t.kpiCard.valueSize
  result['--kpi-card-label-size'] = t.kpiCard.labelSize

  result['--table-header-bg'] = t.table.headerBg
  result['--table-row-hover-bg'] = t.table.rowHoverBg
  result['--table-border'] = t.table.border
  result['--table-radius'] = t.table.radius
  result['--table-font-size'] = t.table.fontSize
  result['--table-row-height-comfortable'] = t.table.rowHeight.comfortable
  result['--table-row-height-compact'] = t.table.rowHeight.compact

  return result
}
