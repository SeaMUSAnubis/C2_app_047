import { getAccessToken } from './authStore';
import {
  mockDashboardSummary,
  mockDevices,
  mockLogs,
  mockUsers,
} from './mockData';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('Missing API base URL');
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  if (!API_BASE_URL) {
    return {
      accessToken: 'mock-token',
      user: {
        id: email.includes('admin') ? 'admin-demo' : 'analyst-demo',
        email,
        name: email.includes('admin') ? 'Demo Admin' : 'Demo Analyst',
        role: email.includes('admin') ? 'admin' : 'analyst',
      },
    } as const;
  }

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error('Login failed');
  }

  return response.json();
}

export async function getDashboardSummary() {
  try {
    return await request('/dashboard/summary');
  } catch {
    return mockDashboardSummary;
  }
}

export async function getUsers() {
  try {
    return await request('/users');
  } catch {
    return mockUsers;
  }
}

export async function getDevices() {
  try {
    return await request('/devices');
  } catch {
    return mockDevices;
  }
}

export async function getLogs() {
  try {
    return await request('/logs');
  } catch {
    return mockLogs;
  }
}

export async function analyzeDemo(payload: any) {
  if (!API_BASE_URL) {
    throw new Error('API Base URL is required for demo analysis');
  }

  const response = await fetch(`${API_BASE_URL}/demo/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Demo analyze failed: ${errorText}`);
  }

  return response.json();
}
