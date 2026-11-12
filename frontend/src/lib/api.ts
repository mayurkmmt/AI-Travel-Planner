import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// Auto-attach JWT token
api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// Auth helpers
export const auth = {
  register: (data: { email: string; full_name: string; password: string }) =>
    api.post("/api/auth/register", data),
  login: (email: string, password: string) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return api.post("/api/auth/login", form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  me: () => api.get("/api/auth/me"),
  forgotPassword: (email: string) => api.post("/api/auth/forgot-password", { email }),
  resetPassword: (token: string, password: string) =>
    api.post("/api/auth/reset-password", { token, password }),
};

// Chat helpers
export const chat = {
  send: (message: string, tripId?: number) =>
    api.post("/api/chat/", { message, trip_id: tripId ?? null }),
  history: (tripId: number) => api.get(`/api/chat/${tripId}/history/`),
};

// Trip helpers
export const trips = {
  list: (page = 1, pageSize = 10, status = "all") =>
    api.get("/api/trips/", { params: { page, page_size: pageSize, status } }),
  get: (id: number) => api.get(`/api/trips/${id}/`),
  status: (id: number) => api.get(`/api/trips/${id}/status/`),
  delete: (id: number) => api.delete(`/api/trips/${id}/`),
  duplicate: (id: number) => api.post(`/api/trips/${id}/duplicate/`),
  itinerary: (id: number) => api.get(`/api/trips/${id}/itinerary/`),
  hotels: (id: number) => api.get(`/api/trips/${id}/hotels/`),
  restaurants: (id: number) => api.get(`/api/trips/${id}/restaurants/`),
  budget: (id: number) => api.get(`/api/trips/${id}/budget/`),
  weather: (id: number) => api.get(`/api/trips/${id}/weather/`),
  tips: (id: number) => api.get(`/api/trips/${id}/tips/`),
  emergency: (id: number) => api.get(`/api/trips/${id}/emergency/`),
  packingList: (id: number) => api.get(`/api/trips/${id}/packing-list/`),
  map: (id: number) => api.get(`/api/trips/${id}/map/`),
  share: (id: number) => api.post(`/api/trips/${id}/share/`),
  revokeShare: (id: number) => api.delete(`/api/trips/${id}/share/`),
  regenerate: (id: number, params: {
    budget?: number;
    days?: number;
    travelers_adults?: number;
    travel_style?: string;
    pace?: string;
    interests?: string[];
    diet?: string[];
    transport_mode?: string;
    special_requests?: string;
  }) => api.post(`/api/trips/${id}/regenerate/`, params),
};

// Shared (public)
export const shared = {
  get: (token: string) => api.get(`/api/shared/${token}/`),
};
