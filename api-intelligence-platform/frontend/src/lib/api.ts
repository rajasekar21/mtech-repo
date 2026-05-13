import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

const TOKEN_KEY = "api_intelligence_token";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Request interceptor — attach JWT token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token =
      Cookies.get(TOKEN_KEY) ||
      (typeof window !== "undefined"
        ? localStorage.getItem(TOKEN_KEY)
        : null);

    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response interceptor — handle 401 and normalize errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      Cookies.remove(TOKEN_KEY);
      if (typeof window !== "undefined") {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "/auth/login";
      }
    }

    const normalizedError: ApiError = {
      message:
        error.response?.data?.message ||
        error.response?.data?.detail ||
        error.message ||
        "An unexpected error occurred",
      status: error.response?.status,
      errors: error.response?.data?.errors,
    };

    return Promise.reject(normalizedError);
  }
);

export interface ApiError {
  message: string;
  detail?: string;
  status?: number;
  errors?: Record<string, string[]>;
}

export function setToken(token: string): void {
  Cookies.set(TOKEN_KEY, token, { expires: 7, secure: true, sameSite: "strict" });
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function removeToken(): void {
  Cookies.remove(TOKEN_KEY);
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken(): string | null {
  return (
    Cookies.get(TOKEN_KEY) ||
    (typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null) ||
    null
  );
}

// Typed API methods
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.put<T>(url, data);
  return response.data;
}

export async function patch<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.patch<T>(url, data);
  return response.data;
}

export async function del<T>(url: string): Promise<T> {
  const response = await apiClient.delete<T>(url);
  return response.data;
}

export async function uploadFile<T>(
  url: string,
  file: File,
  additionalData?: Record<string, string>
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, value);
    });
  }
  const response = await apiClient.post<T>(url, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export default apiClient;
