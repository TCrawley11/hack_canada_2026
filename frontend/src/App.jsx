import { useState, useCallback } from 'react'
import VideoFeed from './components/VideoFeed'
import DetectionLog from './components/DetectionLog'
import ScareControls from './components/ScareControls'
import useWebSocket from './hooks/useWebSocket'
import useMockEvents from './hooks/useMockEvents'

const WS_URL = 'ws://localhost:8000/events'

function App() {
  const [events, setEvents] = useState([])
  const [mockMode, setMockMode] = useState(false)

  const handleEvent = useCallback((event) => {
    if (event.type === 'detection') {
      const newEvent = {
        ...event,
        id: Date.now() + Math.random(),
      }
      setEvents((prev) => [newEvent, ...prev].slice(0, 50))
    }
  }, [])

  useWebSocket(WS_URL, handleEvent, !mockMode)
  useMockEvents(handleEvent, mockMode, 3000 + Math.random() * 2000)

  return (
    <div className="w-screen h-screen overflow-hidden flex flex-col" style={{ backgroundColor: 'var(--dark_bg)', color: 'var(--light)' }}>
      {/* Floating Controls over Video */}
      <div className="fixed top-4 right-4 flex items-center gap-3 z-50">
        <label className="flex items-center gap-2 text-sm cursor-pointer px-4 py-2 font-medium" style={{ 
          color: 'var(--light)',
          backgroundColor: 'var(--panel_bg)',
          borderRadius: '8px'
        }}>
          <input
            type="checkbox"
            checked={mockMode}
            onChange={(e) => setMockMode(e.target.checked)}
            className="w-4 h-4"
          />
          Mock Mode
        </label>
        <ScareControls />
      </div>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {/* Video Feed - Max 70vh */}
        <section 
          style={{ 
            maxHeight: '70vh',
            height: '70vh',
            padding: '1rem 1rem 0.5rem 1rem'
          }}
        >
          <VideoFeed />
        </section>

        {/* Detection Log - Takes remaining space */}
        <section className="flex-1 overflow-hidden px-4 py-2">
          <DetectionLog events={events} />
        </section>
      </main>
    </div>
  )
}

export default App
