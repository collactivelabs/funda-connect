import axios, { type AxiosError } from "axios";
import type { ApiError } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  withCredentials: true, // send HttpOnly refresh token cookie
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
    logout: () => api.post("/auth/logout"),
    me: () => api.get("/auth/me"),
  },
  teachers: {
    search: (params: unknown) => api.get("/teachers", { params }),
    get: (id: string) => api.get(`/teachers/${id}`),
    updateProfile: (body: unknown) => api.patch("/teachers/me/profile", body),
    getAvailability: () => api.get("/teachers/me/availability"),
    setAvailability: (body: unknown) => api.put("/teachers/me/availability", body),
    uploadDocument: (form: FormData) =>
      api.post("/teachers/me/documents", form, {
        headers: { "Content-Type": "multipart/form-data" },
      }),
  },
  parents: {
    getLearners: () => api.get("/parents/me/learners"),
    createLearner: (body: unknown) => api.post("/parents/me/learners", body),
    updateLearner: (id: string, body: unknown) =>
      api.patch(`/parents/me/learners/${id}`, body),
  },
  bookings: {
    create: (body: unknown) => api.post("/bookings", body),
    list: () => api.get("/bookings/my"),
    get: (id: string) => api.get(`/bookings/${id}`),
    cancel: (id: string, body: unknown) =>
      api.post(`/bookings/${id}/cancel`, body),
  },
  subjects: {
    list: () => api.get("/subjects"),
  },
  reviews: {
    create: (body: unknown) => api.post("/reviews", body),
    reply: (id: string, body: unknown) =>
      api.post(`/reviews/${id}/reply`, body),
  },
};
