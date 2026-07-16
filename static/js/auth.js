import * as api from "./api.js";
import { showToast } from "./app-shell.js";

/**
 * Boot-time auth check: GET /auth/me to see if there's an active session.
 * Returns { email, role } on success, null on 401, "offline" on network error.
 */
export async function initAuth(state) {
  try {
    const user = await api.getMe();
    state.user = user;
    return user;
  } catch (err) {
    if (err.status === 401) {
      state.user = null;
      return null;
    }
    // Network error (offline); let boot continue so the app stays usable
    return "offline";
  }
}

/**
 * Show the login screen and hide the main app.
 */
export function showLogin() {
  const screen = document.getElementById("loginScreen");
  if (screen) screen.hidden = false;
  document.body.classList.add("auth-locked");
}

/**
 * Hide the login screen and show the main app.
 */
export function hideLogin() {
  const screen = document.getElementById("loginScreen");
  if (screen) screen.hidden = true;
  document.body.classList.remove("auth-locked");
}

/**
 * Wire up auth UI: login form, logout button, change-password dialog.
 * Listens for the global auth:required event to re-show login on 401.
 */
export function wireAuth({ onLogin }) {
  // Login form
  const loginForm = document.getElementById("loginForm");
  const loginError = document.getElementById("loginError");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = loginForm.elements.email?.value || "";
      const password = loginForm.elements.password?.value || "";
      if (!email || !password) {
        showToast("Email and password required", "error");
        return;
      }
      try {
        const user = await api.login(email, password);
        hideLogin();
        if (loginError) loginError.textContent = "";
        onLogin(user);
      } catch (err) {
        if (loginError) loginError.textContent = err.message;
      }
    });
  }

  // Logout button
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        await api.logout();
        location.reload();
      } catch (err) {
        showToast("Logout failed: " + err.message, "error");
      }
    });
  }

  // Change-password dialog
  const changePasswordSheet = document.getElementById("changePasswordSheet");
  const changePasswordForm = changePasswordSheet?.querySelector("form");
  if (changePasswordForm) {
    changePasswordForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = changePasswordForm.elements.current_password?.value || "";
      const newPw = changePasswordForm.elements.new_password?.value || "";
      const confirm = changePasswordForm.elements.confirm_password?.value || "";
      if (!current || !newPw || !confirm) {
        showToast("All fields required", "error");
        return;
      }
      if (newPw !== confirm) {
        showToast("New passwords don't match", "error");
        return;
      }
      try {
        await api.changePassword(current, newPw);
        changePasswordSheet.close?.();
        showToast("Password changed", "success");
        changePasswordForm.reset();
      } catch (err) {
        showToast("Password change failed: " + err.message, "error");
      }
    });
  }

  // Global auth:required event listener (triggered by 401 in fetchJson)
  window.addEventListener("auth:required", () => {
    showLogin();
  });
}

/**
 * Apply role-based visibility rules: show/hide admin nav, hide destructive buttons for users.
 */
export function applyRoleToUi(state) {
  const isAdmin = state.user?.role === "admin";

  // Admin nav items (bottom nav + desktop)
  document.getElementById("navAdmin")?.hidden !== isAdmin && (document.getElementById("navAdmin").hidden = !isAdmin);
  document.getElementById("navAdminLink")?.hidden !== isAdmin && (document.getElementById("navAdminLink").hidden = !isAdmin);

  // Hide destructive buttons for non-admins
  if (!isAdmin) {
    document.getElementById("appBarDeleteBtn")?.hidden !== true && (document.getElementById("appBarDeleteBtn").hidden = true);
    document.getElementById("moreResetBtn")?.hidden !== true && (document.getElementById("moreResetBtn").hidden = true);
  }
}
