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
  const colors = {
    backgroundColor: `var(--color-status-${statusKey}-bg)`,
    borderColor: `var(--color-status-${statusKey}-border)`,
    color: `var(--color-status-${statusKey}-text)`,
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
      title={config.label}
    >
      <span className="opacity-90 text-[11px]">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  )
}
