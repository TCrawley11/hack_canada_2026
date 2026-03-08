import { useEffect, useCallback } from 'react'

const MOCK_SPECIES = [
  { species: 'raccoon', threat: true },
  { species: 'coyote', threat: true },
  { species: 'deer', threat: false },
  { species: 'fox', threat: true },
  { species: 'bear', threat: true },
  { species: 'raven', threat: true },
  { species: 'human', threat: true },
  { species: 'rabbit', threat: false },
]

const MOCK_SCARES = [
  'hawk screech',
  'dog bark',
  'loud alarm',
  'human warning',
]

function getTimestamp() {
  const now = new Date()
  return now.toTimeString().split(' ')[0]
}

function generateMockEvent() {
  const speciesData = MOCK_SPECIES[Math.floor(Math.random() * MOCK_SPECIES.length)]
  const scare = MOCK_SCARES[Math.floor(Math.random() * MOCK_SCARES.length)]
  const confidence = 0.7 + Math.random() * 0.28

  return {
    type: 'detection',
    species: speciesData.species,
    confidence,
    scare,
    timestamp: getTimestamp(),
    id: Date.now() + Math.random(),
  }
}

export default function useMockEvents(onEvent, enabled = true, intervalMs = 4000) {
  const generateEvent = useCallback(() => {
    if (enabled) {
      onEvent(generateMockEvent())
    }
  }, [enabled, onEvent])

  useEffect(() => {
    if (!enabled) return

    const interval = setInterval(generateEvent, intervalMs)

    return () => clearInterval(interval)
  }, [enabled, intervalMs, generateEvent])
}
