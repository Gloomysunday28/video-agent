import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

export function useSession() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [sessionId, setSessionId] = useState<string>(() => {
    const idFromUrl = searchParams.get('id')
    return idFromUrl || crypto.randomUUID()
  })

  // 更新URL中的session_id
  useEffect(() => {
    const currentId = searchParams.get('id')
    if (currentId !== sessionId) {
      const newParams = new URLSearchParams(searchParams)
      newParams.set('id', sessionId)
      setSearchParams(newParams, { replace: true })
    }
  }, [sessionId, searchParams, setSearchParams])

  const createNewSession = () => {
    const newSessionId = crypto.randomUUID()
    setSessionId(newSessionId)
    return newSessionId
  }

  const switchToSession = (targetSessionId: string) => {
    setSessionId(targetSessionId)
  }

  return {
    sessionId,
    createNewSession,
    switchToSession
  }
}
