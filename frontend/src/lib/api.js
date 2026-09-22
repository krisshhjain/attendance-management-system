export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 
  (import.meta.env.DEV ? "http://127.0.0.1:8000/api" : "/api")
).replace(/\/$/, "");

const ACCESS_KEY = "sa_access_token";
const REFRESH_KEY = "sa_refresh_token";

export const tokenStore = {
  get access() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(access, refresh) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, access);
    if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function friendlyMessage(status, payload) {
  if (payload && typeof payload === "object") {
    const candidate = payload.detail ?? payload.message ?? payload.error ?? payload.non_field_errors;
    if (typeof candidate === "string") return candidate;
    if (Array.isArray(candidate) && typeof candidate[0] === "string") return candidate[0];
  }
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 400) return "That request couldn't be completed.";
  if (status >= 500) return "The server is unavailable right now. Please try again.";
  return "Something went wrong. Please try again.";
}

let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed(token) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

async function refreshAccessToken() {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });

    if (!res.ok) {
      tokenStore.clear();
      return null;
    }

    const data = await res.json();
    if (data?.access) {
      tokenStore.set(data.access, data.refresh);
      return data.access;
    }
  } catch {
    // ignore
  }

  tokenStore.clear();
  return null;
}

export async function apiRequest(
  path,
  options = {},
  isRetry = false,
) {
  const { method = "GET", body, auth = true } = options;

  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = tokenStore.access;
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ApiError("Unable to reach the server. Check your connection and try again.", 0);
  }

  if (response.status === 401 && auth && !isRetry && !path.includes("/auth/")) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;
      if (newToken) {
        onRefreshed(newToken);
        return apiRequest(path, options, true);
      }
    } else {
      return new Promise((resolve, reject) => {
        refreshSubscribers.push((token) => {
          if (token) {
            resolve(apiRequest(path, options, true));
          } else {
            reject(new ApiError("Your session has expired. Please sign in again.", 401));
          }
        });
      });
    }
  }

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) {
    if (response.status === 401 && auth) {
      tokenStore.clear();
    }
    throw new ApiError(friendlyMessage(response.status, payload), response.status);
  }

  return payload;
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

// Leave Management API functions
export async function fetchLeaveTypes() {
  return apiRequest("/leave/types/");
}

export async function fetchLeaveBalances(year) {
  const query = year ? `?year=${year}` : "";
  return apiRequest(`/leave/balances/${query}`);
}

export async function fetchLeaveRequests(status) {
  const query = status ? `?status=${status}` : "";
  return apiRequest(`/leave/requests/${query}`);
}

export async function submitLeaveRequest(data) {
  return apiRequest("/leave/requests/", { method: "POST", body: data });
}

export async function cancelLeaveRequest(id) {
  return apiRequest(`/leave/requests/${id}/cancel/`, { method: "POST" });
}

export async function estimateLeaveDuration(startDate, endDate, dayType = "FULL_DAY") {
  return apiRequest("/leave/estimate-duration/", {
    method: "POST",
    body: { start_date: startDate, end_date: endDate, day_type: dayType },
  });
}

// Admin Leave APIs
export async function fetchAdminLeaveRequests(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiRequest(`/leave/admin/requests/${query ? `?${query}` : ""}`);
}

export async function approveLeaveRequest(id, remarks = "") {
  return apiRequest(`/leave/admin/requests/${id}/approve/`, {
    method: "POST",
    body: { remarks },
  });
}

export async function denyLeaveRequest(id, remarks) {
  return apiRequest(`/leave/admin/requests/${id}/deny/`, {
    method: "POST",
    body: { remarks },
  });
}

export async function cancelApprovedLeaveRequest(id) {
  return apiRequest(`/leave/admin/requests/${id}/cancel/`, { method: "POST" });
}

export async function fetchAdminLeaveBalances(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiRequest(`/leave/admin/balances/${query ? `?${query}` : ""}`);
}

// Super Admin Configuration APIs
export async function fetchLeaveTypesAll() {
  return apiRequest("/leave/admin/types/");
}

export async function createLeaveType(data) {
  return apiRequest("/leave/admin/types/", { method: "POST", body: data });
}

export async function updateLeaveType(id, data) {
  return apiRequest(`/leave/admin/types/${id}/`, { method: "PATCH", body: data });
}

export async function fetchLeavePoliciesAll() {
  return apiRequest("/leave/admin/policies/");
}

export async function createLeavePolicy(data) {
  return apiRequest("/leave/admin/policies/", { method: "POST", body: data });
}

export async function updateLeavePolicy(id, data) {
  return apiRequest(`/leave/admin/policies/${id}/`, { method: "PATCH", body: data });
}
