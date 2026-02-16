interface RiskBadgeProps {
  risk?: string | null
  tier?: string | null
  /** When true, show "Not assessed" for empty/unknown */
  showNotAssessed?: boolean
  className?: string
}

/** Maps tier/risk labels to design token status keys (--color-status-*-bg / -text). */
const STATUS_KEY: Record<string, string> = {
  High: 'intensive',
  Medium: 'strategic',
  Low: 'core',
  'Core (Tier 1)': 'core',
  'Strategic (Tier 2)': 'strategic',
  'Intensive (Tier 3)': 'intensive',
  Unknown: 'unknown',
  'Not assessed': 'unknown',
}

export function RiskBadge({ risk, tier, showNotAssessed, className = '' }: RiskBadgeProps) {
  const raw = tier || risk
  const isMissing = !raw || raw === 'Unknown'
  const label = showNotAssessed && isMissing ? 'Not assessed' : raw || '—'
  const key = STATUS_KEY[tier || risk || (showNotAssessed && isMissing ? 'Not assessed' : '')] ?? 'unknown'
  return (
    <span
      className={`inline-flex items-center font-medium rounded-[var(--button-radius)] ${className}`}
      style={{
        backgroundColor: `var(--color-status-${key}-bg)`,
        color: `var(--color-status-${key}-text)`,
        fontSize: 'var(--chip-text-size)',
        padding: 'var(--chip-padding)',
      }}
    >
      {label}
    </span>
  )
}
