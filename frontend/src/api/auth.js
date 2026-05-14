import { apiRequest, clearToken, setToken } from "./client";

export async function login(email, password) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const data = await apiRequest("/auth/jwt/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });

  setToken(data.access_token);
  return data;
}

export async function fetchCurrentUser() {
  return apiRequest("/users/me");
}

export function logout() {
  clearToken();
}
