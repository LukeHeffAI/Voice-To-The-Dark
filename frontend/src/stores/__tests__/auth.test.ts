import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock the API client
vi.mock('@/api/client', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
    }
  },
}))

import { authApi, ApiError } from '@/api/client'

describe('Auth Store', () => {
  let store: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAuthStore()
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with null token and user', () => {
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })

    it('isLoggedIn is false', () => {
      expect(store.isLoggedIn).toBe(false)
    })

    it('isAdmin is false', () => {
      expect(store.isAdmin).toBe(false)
    })
  })

  describe('login', () => {
    it('sets token and user on success', async () => {
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'test-token',
        token_type: 'bearer',
        user: { id: 1, username: 'testuser', is_admin: false },
      })

      await store.login('testuser', 'password')

      expect(store.token).toBe('test-token')
      expect(store.user).toEqual({ id: 1, username: 'testuser', is_admin: false })
      expect(store.isLoggedIn).toBe(true)
    })

    it('sets isAdmin when user is admin', async () => {
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'admin-token',
        token_type: 'bearer',
        user: { id: 1, username: 'admin', is_admin: true },
      })

      await store.login('admin', 'password')
      expect(store.isAdmin).toBe(true)
    })
  })

  describe('logout', () => {
    it('clears token and user', async () => {
      store.token = 'existing-token'
      store.user = { id: 1, username: 'test', is_admin: false }

      vi.mocked(authApi.logout).mockResolvedValue(undefined)

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isLoggedIn).toBe(false)
    })

    it('clears state even if API call fails', async () => {
      store.token = 'existing-token'
      store.user = { id: 1, username: 'test', is_admin: false }

      vi.mocked(authApi.logout).mockRejectedValue(new Error('Network error'))

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })

  describe('fetchMe', () => {
    it('does nothing without token', async () => {
      store.token = null
      await store.fetchMe()
      expect(authApi.me).not.toHaveBeenCalled()
    })

    it('sets user on success', async () => {
      store.token = 'valid-token'
      vi.mocked(authApi.me).mockResolvedValue({
        id: 1,
        username: 'testuser',
        is_admin: false,
      })

      await store.fetchMe()
      expect(store.user).toEqual({ id: 1, username: 'testuser', is_admin: false })
    })

    it('clears state on 401', async () => {
      store.token = 'expired-token'
      store.user = { id: 1, username: 'test', is_admin: false }

      vi.mocked(authApi.me).mockRejectedValue(new ApiError('Unauthorized', 401))

      await store.fetchMe()
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })
})
