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
  
  // Custom colors: soft red for declining, desaturated greens for others
  const getColors = () => {
    if (statusKey === 'declining') {
      return {
        backgroundColor: '#FCE8E8', // Soft red background
        color: '#9B1C1C', // Darker red text
      }
    }
    if (statusKey === 'improving') {
      return {
        backgroundColor: '#E6F2EC', // Soft green background (desaturated)
        color: '#1E6B43', // Darker green text
      }
    }
    if (statusKey === 'stable') {
      return {
        backgroundColor: '#E6F2EC', // Soft green background (desaturated)
        color: '#1E6B43', // Darker green text
      }
    }
    // Fallback to CSS variables for unknown
    return {
      backgroundColor: `var(--color-status-${statusKey}-bg)`,
      color: `var(--color-status-${statusKey}-text)`,
    }
  }
  
  const colors = getColors()
  
  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded-[var(--button-radius)] ${className}`}
      style={{
        backgroundColor: colors.backgroundColor,
        color: colors.color,
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
