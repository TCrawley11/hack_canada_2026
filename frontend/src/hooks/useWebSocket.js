import { useEffect, useRef, useCallback } from 'react'

export default function useWebSocket(url, onMessage, enabled = true) {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const connect = useCallback(() => {
    if (!enabled) return

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
      }

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage(data)
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
  }, [url, onMessage, enabled])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  return wsRef.current
}
