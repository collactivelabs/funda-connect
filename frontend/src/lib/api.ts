import axios, { type AxiosError } from "axios";
import type { ApiError, AuthSession } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// snake_case → camelCase deep transformer for API responses
function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function transformKeys(data: unknown): unknown {
  if (Array.isArray(data)) return data.map(transformKeys);
  if (data !== null && typeof data === "object" && !(data instanceof Date)) {
    return Object.fromEntries(
      Object.entries(data as Record<string, unknown>).map(([k, v]) => [toCamelCase(k), transformKeys(v)])
    );
  }
  return data;
}

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  withCredentials: true, // send HttpOnly refresh token cookie
});

// Transform all response data from snake_case to camelCase
api.interceptors.response.use((res) => {
  if (res.data) res.data = transformKeys(res.data);
  return res;
});

// Attach access token from memory on every request
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// Transparent token refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError<ApiError>) => {
    const original = error.config as typeof error.config & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const { data } = await api.post<{ accessToken: string }>("/auth/refresh");
        setAccessToken(data.accessToken);
        original.headers!.Authorization = `Bearer ${data.accessToken}`;
        return api(original);
      } catch {
        setAccessToken(null);
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Typed helpers
export const apiClient = {
  auth: {
    register: (body: unknown) => api.post("/auth/register", body),
    login: (body: unknown) => api.post("/auth/login", body),
    listSessions: () => api.get<AuthSession[]>("/auth/sessions"),
    revokeSession: (sessionId: string) => api.delete(`/auth/sessions/${sessionId}`),
    revokeOtherSessions: () => api.post("/auth/sessions/revoke-others"),
    requestEmailVerification: (body: unknown) => api.post("/auth/verify-email/request", body),
    verifyEmail: (body: unknown) => api.post("/auth/verify-email", body),
    forgotPassword: (body: unknown) => api.post("/auth/forgot-password", body),
    resetPassword: (body: unknown) => api.post("/auth/reset-password", body),
    logout: () => api.post("/auth/logout"),
    me: () => api.get("/auth/me"),
  },
  teachers: {
    search: (params: unknown) => api.get("/teachers", { params }),
    get: (id: string) => api.get(`/teachers/${id}`),
    getMe: () => api.get("/teachers/me"),
    updateProfile: (body: unknown) => api.patch("/teachers/me/profile", body),
    addSubject: (body: unknown) => api.post("/teachers/me/subjects", body),
    removeSubject: (subjectId: string) => api.delete(`/teachers/me/subjects/${subjectId}`),
    getAvailability: () => api.get("/teachers/me/availability"),
    setAvailability: (body: unknown) => api.put("/teachers/me/availability", body),
    getPublicAvailability: (id: string) => api.get(`/teachers/${id}/availability`),
    getBookableSlots: (
      id: string,
      params: { durationMinutes: number; recurringWeeks?: number; days?: number }
    ) =>
      api.get(`/teachers/${id}/bookable-slots`, {
        params: {
          duration_minutes: params.durationMinutes,
          recurring_weeks: params.recurringWeeks,
          days: params.days,
        },
      }),
    listDocuments: () => api.get("/teachers/me/documents"),
    getDocumentAccess: (documentId: string) => api.get(`/teachers/me/documents/${documentId}/access`),
    uploadDocument: (documentType: string, form: FormData) =>
      api.post(`/teachers/me/documents?document_type=${encodeURIComponent(documentType)}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      }),
    getEarnings: () => api.get("/teachers/me/earnings"),
  },
  parents: {
    getLearners: () => api.get("/parents/me/learners"),
    createLearner: (body: unknown) => api.post("/parents/me/learners", body),
    updateLearner: (id: string, body: unknown) =>
      api.patch(`/parents/me/learners/${id}`, body),
    deleteLearner: (id: string) => api.delete(`/parents/me/learners/${id}`),
  },
  bookings: {
    create: (body: unknown) => api.post("/bookings", body),
    list: () => api.get("/bookings/my"),
    get: (id: string) => api.get(`/bookings/${id}`),
    cancel: (id: string, body: unknown) =>
      api.post(`/bookings/${id}/cancel`, body),
    complete: (id: string) => api.post(`/bookings/${id}/complete`),
    cancelSeries: (id: string, body: unknown) =>
      api.post(`/bookings/${id}/cancel-series`, body),
  },
  subjects: {
    list: () => api.get("/subjects"),
  },
  reviews: {
    create: (body: unknown) => api.post("/reviews", body),
    reply: (id: string, body: unknown) => api.post(`/reviews/${id}/reply`, body),
    listForTeacher: (teacherId: string) => api.get(`/reviews/teacher/${teacherId}`),
  },
  admin: {
    getStats: () => api.get("/admin/stats"),
    listTeachers: (params?: { verification_status?: string }) =>
      api.get("/admin/teachers", { params }),
    getTeacherVerification: (id: string) => api.get(`/admin/teachers/${id}/verification`),
    reviewTeacherDocument: (
      teacherId: string,
      documentId: string,
      body: { status: "approved" | "rejected"; reviewer_notes?: string }
    ) => api.patch(`/admin/teachers/${teacherId}/documents/${documentId}`, body),
    getTeacherDocumentAccess: (teacherId: string, documentId: string) =>
      api.get(`/admin/teachers/${teacherId}/documents/${documentId}/access`),
    verifyTeacher: (id: string, body: { action: string; notes?: string }) =>
      api.patch(`/admin/teachers/${id}/verify`, body),
    togglePremium: (id: string) => api.patch(`/admin/teachers/${id}/premium`),
    listPayouts: (params?: { payout_status?: string }) =>
      api.get("/admin/payouts", { params }),
    updatePayout: (id: string, body: { status: string; bank_reference?: string; notes?: string }) =>
      api.patch(`/admin/payouts/${id}`, body),
  },
};
