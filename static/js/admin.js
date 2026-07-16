import * as api from "./api.js";
import { showToast } from "./app-shell.js";

export function wireAdminScreen() {
  // Delegated event handlers for dynamic elements
  document.addEventListener("click", async (e) => {
    if (e.target.matches("[data-action]")) {
      const action = e.target.dataset.action;
      const email = e.target.dataset.email;
      if (action === "deactivate") {
        await handleUserAction(email, { active: false });
      } else if (action === "reactivate") {
        await handleUserAction(email, { active: true });
      } else if (action === "reset-password") {
        const newPw = prompt("Enter temporary password:");
        if (newPw) {
          await handleUserAction(email, { new_password: newPw });
        }
      }
    }
  });

  document.addEventListener("submit", async (e) => {
    if (e.target.id === "adminCreateUserForm") {
      e.preventDefault();
      const email = e.target.elements.email?.value;
      const password = e.target.elements.password?.value;
      if (!email || !password) return showToast("All fields required", "error");
      try {
        await api.adminCreateUser(email, password);
        showToast(`User ${email} created`, "success");
        e.target.reset();
        await refreshAdminScreen(window.state || {});
      } catch (err) {
        showToast("Create failed: " + err.message, "error");
      }
    }
  });
}

async function handleUserAction(email, payload) {
  try {
    await api.adminPatchUser(email, payload);
    showToast("User updated", "success");
    await refreshAdminScreen(window.state || {});
  } catch (err) {
    showToast("Update failed: " + err.message, "error");
  }
}

export async function refreshAdminScreen(state) {
  window.state = state; // for delegated handlers
  const container = document.getElementById("adminContent");
  if (!container) return;

  try {
    const [statsResp, usersResp] = await Promise.all([
      api.adminStats(30),
      api.adminListUsers(),
    ]);

    let html = `<div style="padding:var(--space-3)">`;

    // Scans by user
    html += `<h2 style="margin-bottom:var(--space-2)">Scans by user</h2>`;
    if (statsResp.totals?.length) {
      html += `<table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid #ccc">
            <th style="text-align:left;padding:8px">User</th>
            <th style="text-align:center;padding:8px">Total</th>
            <th style="text-align:center;padding:8px">Errors</th>
            <th style="text-align:left;padding:8px">Last scan</th>
          </tr>
        </thead>
        <tbody>`;
      statsResp.totals.forEach((row) => {
        html += `<tr style="border-bottom:1px solid #eee">
          <td style="padding:8px">${row.email}</td>
          <td style="text-align:center;padding:8px">${row.total}</td>
          <td style="text-align:center;padding:8px">${row.errors || 0}</td>
          <td style="padding:8px;font-size:12px">${row.last_scan_at?.slice(0, 10) || "—"}</td>
        </tr>`;
      });
      html += `</tbody></table>`;
    }
    if (statsResp.untracked_records > 0) {
      html += `<p style="font-size:12px;color:#666;margin-top:8px">(before tracking) ${statsResp.untracked_records} records</p>`;
    }

    // Users management
    html += `<h2 style="margin-top:var(--space-3);margin-bottom:var(--space-2)">Users</h2>`;
    if (usersResp.users?.length) {
      html += `<table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid #ccc">
            <th style="text-align:left;padding:8px">Email</th>
            <th style="text-align:center;padding:8px">Status</th>
            <th style="text-align:center;padding:8px">Actions</th>
          </tr>
        </thead>
        <tbody>`;
      usersResp.users.forEach((user) => {
        const status = user.active ? "Active" : "Inactive";
        const action1 = user.active ? "Deactivate" : "Reactivate";
        const data1 = user.active ? "deactivate" : "reactivate";
        html += `<tr style="border-bottom:1px solid #eee">
          <td style="padding:8px">${user.email}</td>
          <td style="text-align:center;padding:8px">${status}</td>
          <td style="text-align:center;padding:8px;font-size:12px">
            <button data-action="${data1}" data-email="${user.email}" style="padding:4px 8px;margin:0 2px;cursor:pointer">${action1}</button>
            <button data-action="reset-password" data-email="${user.email}" style="padding:4px 8px;margin:0 2px;cursor:pointer">Reset PW</button>
          </td>
        </tr>`;
      });
      html += `</tbody></table>`;
    }

    // Add user form
    html += `<h3 style="margin-top:var(--space-3);margin-bottom:var(--space-2)">Add user</h3>`;
    html += `<form id="adminCreateUserForm" style="display:flex;gap:8px;flex-wrap:wrap">
      <input type="email" name="email" placeholder="user@tritorc.com" required style="padding:8px;border:1px solid #ccc;border-radius:4px">
      <input type="password" name="password" placeholder="Temporary password" required style="padding:8px;border:1px solid #ccc;border-radius:4px">
      <button type="submit" style="padding:8px 16px;background:#14213d;color:white;border:none;border-radius:4px;cursor:pointer">Create</button>
    </form>`;

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<p style="color:red;padding:var(--space-3)">${err.message}</p>`;
  }
}
