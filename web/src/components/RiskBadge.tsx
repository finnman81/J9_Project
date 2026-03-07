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
  const colors = {
    backgroundColor: `var(--color-status-${key}-bg)`,
    borderColor: `var(--color-status-${key}-border)`,
    color: `var(--color-status-${key}-text)`,
  }
  
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border font-medium ${className}`}
      style={{
        backgroundColor: colors.backgroundColor,
        borderColor: colors.borderColor,
        color: colors.color,
        fontSize: 'var(--chip-text-size)',
        padding: '6px 12px',
      }}
    >
      <span
        aria-hidden="true"
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: colors.color }}
      />
      {label}
    </span>
  )
}
