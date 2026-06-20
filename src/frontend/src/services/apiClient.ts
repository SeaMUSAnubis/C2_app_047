// A simple API client wrapper
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  // Mock interception could be implemented here or in services
  
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

export const isMockMode = () => USE_MOCKS;

// Helper to simulate network delay for mocks
export const delay = (ms: number) => new Promise(res => setTimeout(res, ms));
