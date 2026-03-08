import { useEffect, useRef, useState } from 'react'
import Iridescence from './Iridescence'

export default function VideoFeed() {
  const videoRef = useRef(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: false
        })
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          setIsLoading(false)
        }
      } catch (err) {
        setError('Camera access denied or unavailable')
        setIsLoading(false)
      }
    }
    startCamera()

    return () => {
      if (videoRef.current?.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks()
        tracks.forEach(track => track.stop())
      }
    }
  }, [])

  return (
    <div 
      className="relative w-full h-full overflow-hidden"
      style={{
        backgroundColor: 'var(--panel_bg)',
        border: '2px solid var(--panel_border)',
        borderRadius: '8px',
        boxShadow: '0 4px 12px var(--dark_50)'
      }}
    >
      <div className="absolute inset-0">
        <Iridescence
          color={[0.1, 0.1, 0.1]}
          mouseReact
          amplitude={0.1}
          speed={0.2}
        />
      </div>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div 
            className="w-8 h-8 rounded-full animate-spin"
            style={{
              border: '2px solid var(--panel_border)',
              borderTopColor: 'var(--light)'
            }}
          />
        </div>
      )}
      {error ? (
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ color: 'var(--light_70)' }}>
          <div className="text-center">
            <svg className="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--light_40)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p>{error}</p>
          </div>
        </div>
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="relative w-full h-full object-contain z-10"
        />
      )}
      <div 
        className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 z-20"
        style={{
          backgroundColor: 'var(--dark_80)',
          borderRadius: '6px'
        }}
      >
        <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--status_alert)' }} />
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--light)' }}>Live</span>
      </div>
    </div>
  )
}
