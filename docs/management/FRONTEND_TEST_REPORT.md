# Frontend Test Report

**Project:** UEBA Endpoint Monitoring  
**Date:** 2026-06-17  
**Branch:** BuiHoangLinh_2A202600804  

---

## 1. Tổng quan Frontend

### 1.1 Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2.6 | UI framework |
| TypeScript | 6.0.2 | Type safety |
| Vite | 8.0.12 | Build tool |
| React Router | 7.17.0 | Client-side routing |

### 1.2 Cấu trúc Frontend

```
frontend/src/
├── app/              # App component, routes
├── components/       # UI components
│   ├── auth/         # LoginForm, ProtectedRoute
│   ├── layout/       # AppShell, Sidebar, Topbar
│   └── common/       # Shared components
├── lib/              # Utilities
│   ├── apiClient.ts  # API client (CRITICAL)
│   ├── authStore.ts  # Auth state management
│   └── mockData.ts   # Mock data
├── pages/            # Page components
└── types/            # TypeScript types
```

---

## 2. Phân tích vấn đề (Bugs & Security Issues)

### 2.1 CRITICAL: Login bypass không cần password

**File:** `frontend/src/lib/apiClient.ts:31-42`

**Mô tả:** Khi `VITE_API_BASE_URL` không được set, hàm `login()` trả về mock data mà **KHÔNG kiểm tra password**.

**Code lỗi:**
```typescript
export async function login(email: string, password: string) {
  if (!API_BASE_URL) {
    return {
      accessToken: 'mock-token',
      user: {
        role: email.includes('admin') ? 'admin' : 'analyst',
      },
    };
  }
}
```

**Tác động:** Bypass hoàn toàn authentication. Bất kỳ ai cũng đăng nhập được.

**Mức độ:** CRITICAL

---

### 2.2 HIGH: API fallback trả về mock data

**File:** `frontend/src/lib/apiClient.ts:57-87`

**Mô tả:** Các hàm `getUsers()`, `getDevices()`, `getLogs()` fallback trả về mock data khi API fail.

**Tác động:** User thấy dữ liệu giả mà không biết.

**Mức độ:** HIGH

---

### 2.3 MEDIUM: Token không có expiry check

**File:** `frontend/src/lib/authStore.ts`

**Mô tả:** `isAuthenticated()` chỉ kiểm tra token tồn tại, không kiểm tra hết hạn.

**Mức độ:** MEDIUM

---

## 3. Test Cases

### 3.1 Authentication Tests

| ID | Test Case | Status |
|----|-----------|--------|
| FE-AUTH-01 | Login với email admin + password đúng | PASS |
| FE-AUTH-02 | Login với email analyst + password đúng | PASS |
| FE-AUTH-03 | Login với password sai | PASS |
| FE-AUTH-04 | Login với email không tồn tại | PASS |
| FE-AUTH-05 | Login khi `API_BASE_URL` rỗng (BUG) | PASS |
| FE-AUTH-06 | Login không validate password (BUG) | PASS |
| FE-AUTH-07 | Save auth session vào localStorage | PASS |
| FE-AUTH-08 | Clear auth session | PASS |
| FE-AUTH-09 | `isAuthenticated` khi có token | PASS |
| FE-AUTH-10 | `isAuthenticated` khi không có token | PASS |
| FE-AUTH-11 | `getAuthUser` với data lỗi | PASS |

### 3.2 API Client Tests

| ID | Test Case | Status |
|----|-----------|--------|
| FE-API-01 | Login mock mode - admin role | PASS |
| FE-API-02 | Login mock mode - analyst role | PASS |
| FE-API-03 | Login không validate password (BUG) | PASS |
| FE-API-04 | `getDashboardSummary` fallback | PASS |
| FE-API-05 | `getUsers` fallback | PASS |
| FE-API-06 | `getDevices` fallback | PASS |
| FE-API-07 | `getLogs` fallback | PASS |
| FE-API-08 | Mock data format | PASS |

---

## 4. Test Results

```
Test Files:  2 passed (2)
Tests:       19 passed (19)
Duration:    ~500ms
```

---

## 5. Cách chạy Frontend Tests

```bash
cd frontend

# Cài đặt testing dependencies (lần đầu)
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom

# Chạy tests
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

---

## 6. Kết luận

### Vấn đề nghiêm trọng nhất

1. **CRITICAL: Login bypass** - Không cần password để đăng nhập
2. **HIGH: Mock data fallback** - User thấy data giả
3. **MEDIUM: Không token expiry check** - Token hết hạn vẫn sử dụng được

### Ưu tiên fix

1. Fix login bypass (CRITICAL)
2. Xóa mock data fallback (HIGH)
3. Thêm token expiry check (MEDIUM)
