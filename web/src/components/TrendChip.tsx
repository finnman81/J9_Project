interface TrendChipProps {
  trend?: string | null
  className?: string
}

const TREND_CONFIG: Record<string, { icon: string; label: string; statusKey: string }> = {
  Improving: { icon: '↑', label: 'Improving', statusKey: 'improving' },
  Declining: { icon: '↓', label: 'Declining', statusKey: 'declining' },
  Stable: { icon: '→', label: 'Stable', statusKey: 'stable' },
  Unknown: { icon: '—', label: 'Unknown', statusKey: 'unknown' },
}

export function TrendChip({ trend, className = '' }: TrendChipProps) {
  const key = trend && TREND_CONFIG[trend] ? trend : 'Unknown'
  const config = TREND_CONFIG[key]
  const statusKey = config.statusKey
  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded-[var(--button-radius)] ${className}`}
      style={{
        backgroundColor: `var(--color-status-${statusKey}-bg)`,
        color: `var(--color-status-${statusKey}-text)`,
        fontSize: 'var(--chip-text-size)',
        padding: 'var(--chip-padding)',
      }}
      title={config.label}
    >
      <span className="opacity-90">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  )
}
