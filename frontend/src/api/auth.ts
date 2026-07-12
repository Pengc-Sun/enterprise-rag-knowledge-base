import { apiRequest } from './client';
import type { AccessToken, LoginPayload, RegisterPayload, UserRead } from './types';

export function login(payload: LoginPayload): Promise<AccessToken> {
  return apiRequest<AccessToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterPayload): Promise<UserRead> {
  return apiRequest<UserRead>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
