import { request } from './client'
import type { TokenResponse, User } from './types'

export function login(username: string, password: string) {
  return request<TokenResponse>('POST', '/auth/login', {
    body: { username, password },
  })
}

export function logout() {
  return request<{ message: string }>('POST', '/auth/logout')
}

export function getMe() {
  return request<User>('GET', '/auth/me')
}

export function register(username: string, password: string) {
  return request<User>('POST', '/auth/register', {
    body: { username, password },
  })
}
