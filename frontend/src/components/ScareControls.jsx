import { useState, useEffect } from 'react'

const API_URL = 'http://localhost:8000'

export default function ScareControls() {
  const [isOpen, setIsOpen] = useState(false)
  const [lastPlayed, setLastPlayed] = useState(null)
  const [sounds, setSounds] = useState([])
  const [loading, setLoading] = useState(false)

  // Fetch available sounds from backend
  useEffect(() => {
    fetch(`${API_URL}/sounds`)
      .then(res => res.json())
      .then(data => setSounds(data.sounds || []))
      .catch(err => console.warn('Failed to fetch sounds:', err))
  }, [])

  const playSound = async (soundName) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/play/sound/${soundName}`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        setLastPlayed(soundName)
        setTimeout(() => setLastPlayed(null), 2000)
      } else {
        console.warn('Sound not played:', data.reason)
      }
    } catch (err) {
      console.warn('Failed to play sound:', err)
    }
    setLoading(false)
    setIsOpen(false)
  }

  const playRandom = async () => {
    if (sounds.length === 0) return
    const randomSound = sounds[Math.floor(Math.random() * sounds.length)]
    await playSound(randomSound)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-4 py-2 font-medium text-sm transition-all duration-200 cursor-pointer"
        style={{
          backgroundColor: 'var(--panel_bg)',
          color: 'var(--light)',
          borderRadius: '8px'
        }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--panel_bg_hover)'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--panel_bg)'}
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        </svg>
        Scare
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div 
          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-64 overflow-hidden z-50 max-h-80 overflow-y-auto"
          style={{
            backgroundColor: 'var(--panel_bg)',
            borderRadius: '8px'
          }}
        >
          <button
            onClick={playRandom}
            className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer"
            style={{
              color: 'var(--light)',
              backgroundColor: 'transparent',
              borderBottom: '1px solid rgba(255,255,255,0.1)'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--panel_bg_hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <span className="text-sm">Random Sound</span>
          </button>
          {sounds.map((sound) => (
            <button
              key={sound}
              onClick={() => playSound(sound)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer"
              style={{
                color: 'var(--light)',
                backgroundColor: 'transparent'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--panel_bg_hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <span className="text-sm">{sound}</span>
            </button>
          ))}
        </div>
      )}

      {lastPlayed && (
        <div 
          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-4 py-2 text-sm animate-slide-in"
          style={{
            backgroundColor: 'var(--panel_bg)',
            borderRadius: '8px',
            color: 'var(--status_safe)'
          }}
        >
          ✓ {lastPlayed} triggered!
        </div>
      )}
    </div>
  )
}
