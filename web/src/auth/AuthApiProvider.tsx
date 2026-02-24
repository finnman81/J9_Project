import { useEffect, type ReactNode } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { setApiFetch } from '../api/client'

/**
 * Wires the Clerk session token into the API client module.
 *
 * Every `api.*` call made while this provider is mounted will automatically
 * include `Authorization: Bearer <clerk-jwt>` in its headers.
 */
export function AuthApiProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth()

  useEffect(() => {
    const authFetch: typeof fetch = async (input, init) => {
      const token = await getToken()
      const headers = new Headers(init?.headers)
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
      return fetch(input, { ...init, headers })
    }

    setApiFetch(authFetch)

    return () => setApiFetch(fetch)
  }, [getToken])

  return <>{children}</>
}
