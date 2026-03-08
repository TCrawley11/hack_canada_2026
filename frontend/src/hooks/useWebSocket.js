import { useEffect, useRef } from 'react'

export default function useWebSocket(url, onMessage, enabled = true) {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  
  // Keep callback ref updated
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    if (!enabled) {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    // Prevent duplicate connections
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return
    }

    function connect() {
      try {
        wsRef.current = new WebSocket(url)

        wsRef.current.onopen = () => {
          console.log('WebSocket connected')
        }

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            onMessageRef.current(data)
          } catch (err) {
            console.warn('Failed to parse WebSocket message:', err)
          }
        }

        wsRef.current.onclose = () => {
          console.log('WebSocket disconnected, reconnecting in 3s...')
          reconnectTimeoutRef.current = setTimeout(connect, 3000)
        }

        wsRef.current.onerror = (err) => {
          console.warn('WebSocket error:', err)
        }
      } catch (err) {
        console.warn('Failed to create WebSocket:', err)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [url, enabled])

  return wsRef.current
}
