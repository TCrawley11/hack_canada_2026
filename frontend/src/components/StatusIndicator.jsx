export default function StatusIndicator({ isThreat }) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 font-semibold text-sm uppercase tracking-wider transition-all duration-300 ${isThreat ? 'threat-pulse' : ''}`}
      style={{
        backgroundColor: 'var(--panel_bg)',
        borderRadius: '8px',
        color: isThreat ? 'var(--status_alert)' : 'var(--status_safe)'
      }}
    >
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: isThreat ? 'var(--status_alert)' : 'var(--status_safe)' }}
      />
      {isThreat ? 'Threat' : 'Safe'}
    </div>
  )
}
