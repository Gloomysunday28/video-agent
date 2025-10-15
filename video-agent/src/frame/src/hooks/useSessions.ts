import { useState, useEffect } from 'react'
import type { Session } from '../types/chat'

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)

  const loadSessions = async () => {
    setIsLoadingSessions(true)
    try {
      const response = await fetch('/api/chat/sessions')
      const data = await response.json()
      
      if (data.success && data.sessions) {
        setSessions(data.sessions)
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
    } finally {
      setIsLoadingSessions(false)
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const refreshSessions = async () => {
    await loadSessions()
  }

  return {
    sessions,
    isLoadingSessions,
    refreshSessions
  }
}
