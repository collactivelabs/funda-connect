import axios, { type AxiosError } from "axios";
import type {
  ApiError,
  AccountConsent,
  AccountDataExportResponse,
  AccountDeletionStatus,
  AuthSession,
  AuthResponse,
  CurriculumOption,
  GradeLevelGroup,
  GoogleOAuthStartResponse,
  LearnerReport,
  LearnerProgress,
  NotificationListResponse,
  NotificationPreferences,
  ParentPaymentHistorySummary,
  ParentPaymentReceipt,
  TopicReference,
} from "@/types";

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

const authApi = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

const AUTH_STORAGE_KEY = "funda-auth";

// Transform all response data from snake_case to camelCase
api.interceptors.response.use((res) => {
  if (res.data) res.data = transformKeys(res.data);
  return res;
});

authApi.interceptors.response.use((res) => {
  if (res.data) res.data = transformKeys(res.data);
  return res;
});

// Attach access token from memory on every request
let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let redirectingToLogin = false;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function syncPersistedAuthToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return;
  }

  try {
    const parsed = JSON.parse(raw) as {
      state?: { token?: string | null; user?: unknown | null };
      version?: number;
    };
    const next = {
      ...parsed,
      state: {
        ...parsed.state,
        token,
      },
    };
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(next));
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

function clearPersistedAuth() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

function clearLiveAuthState() {
  if (typeof window === "undefined") {
    return;
  }

  clearPersistedAuth();
  window.dispatchEvent(new CustomEvent("funda-auth-cleared"));
}

function redirectToLogin() {
  if (typeof window === "undefined" || redirectingToLogin) {
    return;
  }

  redirectingToLogin = true;
  const currentPath = `${window.location.pathname}${window.location.search}`;
  const target =
    currentPath && currentPath !== "/login"
      ? `/login?redirect=${encodeURIComponent(currentPath)}`
      : "/login";
  window.location.assign(target);
}

async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = authApi
      .post<AuthResponse>("/auth/refresh")
      .then(({ data }) => {
        setAccessToken(data.accessToken);
        syncPersistedAuthToken(data.accessToken);
        redirectingToLogin = false;
        return data.accessToken;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
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
    const requestUrl = original?.url ?? "";

    if (error.response?.status === 401 && original && !original._retry && requestUrl !== "/auth/refresh") {
      original._retry = true;
      try {
        const token = await refreshAccessToken();
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        setAccessToken(null);
        clearLiveAuthState();
        redirectToLogin();
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
    startGoogle: (body: unknown) => authApi.post<GoogleOAuthStartResponse>("/auth/google/start", body),
    refreshSession: () => authApi.post<AuthResponse>("/auth/refresh"),
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
  account: {
    getConsents: () => api.get<AccountConsent>("/account/consents"),
    updateConsents: (body: { marketingEmail: boolean; marketingSms: boolean }) =>
      api.put<AccountConsent>("/account/consents", {
        marketing_email: body.marketingEmail,
        marketing_sms: body.marketingSms,
      }),
    getDeletionStatus: () => api.get<AccountDeletionStatus>("/account/deletion-status"),
    requestDeletion: () => api.post<AccountDeletionStatus>("/account/delete-request"),
    getDataExport: () => api.get<AccountDataExportResponse>("/account/data-export"),
  },
  referenceData: {
    listCurricula: () => api.get<CurriculumOption[]>("/curricula"),
    listGradeLevels: () => api.get<GradeLevelGroup[]>("/grade-levels"),
    listTopics: (params?: {
      subject?: string;
      grade?: string;
      curriculum?: string;
      term?: number;
      q?: string;
    }) => api.get<TopicReference[]>("/topics", { params }),
  },
  notifications: {
    list: () => api.get<NotificationListResponse>("/notifications"),
    markRead: (notificationId: string) => api.put(`/notifications/${notificationId}/read`),
    markAllRead: () => api.put("/notifications/read-all"),
    getPreferences: () => api.get<NotificationPreferences>("/notifications/preferences"),
    updatePreferences: (body: Partial<NotificationPreferences>) =>
      api.put<NotificationPreferences>("/notifications/preferences", {
        in_app_enabled: body.inAppEnabled,
        email_enabled: body.emailEnabled,
        sms_enabled: body.smsEnabled,
        push_enabled: body.pushEnabled,
      }),
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
    getBlockedDates: () => api.get("/teachers/me/blocked-dates"),
    setBlockedDates: (body: unknown) => api.put("/teachers/me/blocked-dates", body),
    getPublicAvailability: (id: string) => api.get(`/teachers/${id}/availability`),
    getBookableSlots: (
      id: string,
      params: { durationMinutes: number; recurringWeeks?: number; days?: number; ignoreBookingId?: string }
    ) =>
      api.get(`/teachers/${id}/bookable-slots`, {
        params: {
          duration_minutes: params.durationMinutes,
          recurring_weeks: params.recurringWeeks,
          days: params.days,
          ignore_booking_id: params.ignoreBookingId,
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
    getLearnerProgress: (learnerId: string) => api.get<LearnerProgress>(`/parents/me/learners/${learnerId}/progress`),
    getLearnerReport: (learnerId: string) => api.get<LearnerReport>(`/parents/me/learners/${learnerId}/report`),
    getPayments: () => api.get<ParentPaymentHistorySummary>("/parents/me/payments"),
    getPaymentReceipt: (paymentId: string) => api.get<ParentPaymentReceipt>(`/parents/me/payments/${paymentId}/receipt`),
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
    reschedule: (id: string, body: { scheduled_at: string }) =>
      api.post(`/bookings/${id}/reschedule`, body),
    raiseDispute: (id: string, body: { reason: string }) =>
      api.post(`/bookings/${id}/dispute`, body),
    reportNoShow: (id: string, body: { reason?: string | null }) =>
      api.post(`/bookings/${id}/report-no-show`, body),
    complete: (id: string, body: { lessonNotes?: string | null; topicsCovered: string[] }) =>
      api.post(`/bookings/${id}/complete`, {
        lesson_notes: body.lessonNotes,
        topics_covered: body.topicsCovered,
      }),
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
    listRefunds: (params?: { refund_status?: string }) =>
      api.get("/admin/refunds", { params }),
    updateRefund: (id: string, body: { status: string; gateway_reference?: string; notes?: string }) =>
      api.patch(`/admin/refunds/${id}`, body),
    listDisputes: (params?: { dispute_status?: string }) =>
      api.get("/admin/disputes", { params }),
    resolveDispute: (id: string, body: { resolution: "completed" | "refunded"; notes?: string }) =>
      api.patch(`/admin/disputes/${id}`, body),
  },
};
