import { apiRequest } from "./client";

export async function fetchUsers() {
  return apiRequest("/users");
}

export async function inviteUser(email) {
  return apiRequest("/users/invitations", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function replaceUserRoles(userId, roles) {
  // The backend currently exposes both PUT /users/{id}/roles and PUT /roles/{id}.
  // Prefer the user-scoped route because it is easier to read in network traces.
  return apiRequest(`/users/${userId}/roles`, {
    method: "PUT",
    body: JSON.stringify({ roles }),
  });
}
