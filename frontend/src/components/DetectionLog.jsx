export default function DetectionLog({ events }) {
  return (
    <div 
      className="h-full flex flex-col"
      style={{
        backgroundColor: 'var(--panel_bg)',
        borderRadius: '8px',
        padding: '1rem'
      }}
    >
      <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--light)' }}>
        Detection Log
      </h2>
      <div className="flex-1 overflow-y-auto space-y-2">
        {events.length === 0 ? (
          <p className="text-sm text-center py-8" style={{ color: 'var(--light_50)' }}>No detections yet...</p>
        ) : (
          events.map((event, index) => (
            <div
              key={event.id || index}
              className="flex items-center gap-3 p-3 text-sm animate-slide-in"
              style={{ 
                backgroundColor: 'var(--dark_10)',
                borderRadius: '6px',
                animationDelay: `${index * 50}ms`
              }}
            >
              <span className="font-mono text-xs" style={{ color: 'var(--light_60)' }}>[{event.timestamp}]</span>
              <span 
                className="font-medium"
                style={{ color: 'var(--light)' }}
              >
                {event.species.charAt(0).toUpperCase() + event.species.slice(1)}
              </span>
              <span style={{ color: 'var(--light_50)' }}>
                ({Math.round(event.confidence * 100)}%)
              </span>
              <span style={{ color: 'var(--light_30)' }}>→</span>
              <span style={{ color: 'var(--light_70)' }}>
                {event.scare}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
