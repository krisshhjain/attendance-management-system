import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";
import { AuthProvider } from "../src/lib/auth.jsx";
import { useAuth } from "../src/lib/useAuth.js";
import { API_BASE_URL, tokenStore } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

test("restores a saved session and keeps login type synchronized with storage", async () => {
  tokenStore.set("saved-access", "saved-refresh");
  window.localStorage.setItem("loginType", "systemadmin");
  server.use(
    http.get(`${API_BASE_URL}/auth/me/`, ({ request }) => {
      expect(request.headers.get("authorization")).toBe("Bearer saved-access");
      return HttpResponse.json({ email: "admin@example.test", is_superuser: true });
    }),
  );

  const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

  await waitFor(() => expect(result.current.ready).toBe(true));
  expect(result.current.isAuthenticated).toBe(true);
  expect(result.current.loginType).toBe("systemadmin");
  expect(result.current.user.email).toBe("admin@example.test");
});

test("clears an expired restored session and falls back to employee login", async () => {
  tokenStore.set("expired", "refresh");
  window.localStorage.setItem("loginType", "admin");
  server.use(http.get(`${API_BASE_URL}/auth/me/`, () => HttpResponse.json({}, { status: 401 })));

  const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

  await waitFor(() => expect(result.current.ready).toBe(true));
  expect(result.current.isAuthenticated).toBe(false);
  expect(result.current.loginType).toBe("employee");
  expect(tokenStore.access).toBeNull();
  expect(window.localStorage.getItem("loginType")).toBeNull();
});

test("rejects an admin login without superuser privileges and rolls back the token", async () => {
  server.use(
    http.post(`${API_BASE_URL}/auth/login/`, () => HttpResponse.json({ access: "temporary" })),
    http.get(`${API_BASE_URL}/auth/me/`, () => HttpResponse.json({ is_superuser: false })),
  );
  function Controls() {
    const auth = useAuth();
    const [error, setError] = useState("");
    return (
      <>
        <button
          onClick={() =>
            auth
              .login("person@example.test", "secret", "admin")
              .catch((err) => setError(err.message))
          }
        >
          Login
        </button>
        {error && <p role="alert">{error}</p>}
      </>
    );
  }
  const user = userEvent.setup();
  render(
    <AuthProvider>
      <Controls />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Login" }));

  await waitFor(() => expect(tokenStore.access).toBeNull());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "You do not have administrative privileges.",
  );
  expect(window.localStorage.getItem("loginType")).toBeNull();
});
