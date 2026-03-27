/**
 * Authentication module — Magic Link + Dev Session only.
 * No Firebase dependency.
 */

import { setupFetch, pageState } from "./utils.js";

let _currentUser = null;
let _authChangeCallbacks = [];

export function onAuthChange(callback) {
  _authChangeCallbacks.push(callback);
  if (_currentUser !== null) callback(_currentUser);
}

function _notifyAuthChange(user) {
  _currentUser = user;
  _authChangeCallbacks.forEach((cb) => cb(user));
}

/** Send a magic link to the given email. */
export async function sendMagicLink(email) {
  const res = await setupFetch("/api/v1/auth/magic-link", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.message || data.error || data.detail || "Failed to send magic link");
    err.errorCode = data.error;
    throw err;
  }
  return res.json();
}

/** Verify a magic link token (from URL parameter). */
export async function verifyMagicToken(token) {
  const res = await setupFetch("/api/v1/auth/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Invalid or expired link");
  }
  const data = await res.json();
  _notifyAuthChange(data);
  return data;
}

/** Dev mode auto-login (only available when DEV_AUTH=true). */
export async function devSignIn(email, fullName, language) {
  const res = await setupFetch("/api/v1/auth/dev-session", {
    method: "POST",
    body: JSON.stringify({ email, full_name: fullName, language }),
  });
  if (!res.ok) throw new Error("Dev sign-in failed");
  const data = await res.json();
  _notifyAuthChange(data);
  return data;
}

/** Log out — clears server session cookie. */
export async function logout() {
  await setupFetch("/api/v1/auth/logout", { method: "POST" });
  _notifyAuthChange(null);
  window.location.href = `/${pageState.language || "en"}`;
}

/** Get active session token (cookie-based, no explicit token needed). */
export function getActiveToken() {
  return _currentUser ? "session" : null;
}

/** Open the auth modal. */
export function openAuthModal(reason, defaultEmail) {
  const modal = document.getElementById("auth-modal");
  if (!modal) return;
  modal.classList.add("is-active");
  const emailInput = modal.querySelector('input[type="email"]');
  if (emailInput && defaultEmail) emailInput.value = defaultEmail;
  const reasonEl = modal.querySelector(".auth-reason");
  if (reasonEl && reason) reasonEl.textContent = reason;
}

/** Close the auth modal. */
export function closeAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) modal.classList.remove("is-active");
}

/** Initialize auth — check for magic link token in URL, load account. */
export async function initAuth() {
  // Check for magic link token in URL
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token) {
    try {
      await verifyMagicToken(token);
      // Clean URL
      const url = new URL(window.location);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url);
    } catch (e) {
      console.error("Magic link verification failed:", e);
    }
  }

  // Load account from server-rendered state
  const account = window.__QUIEN_ACCOUNT__;
  if (account && account.authenticated) {
    _notifyAuthChange(account);
  } else {
    _notifyAuthChange(null);
  }

  // Auto-open auth modal if redirected from /app with ?login=1
  const loginParam = new URLSearchParams(window.location.search).get("login");
  if (loginParam === "1") {
    openAuthModal("Sign in to access the workspace");
    const url = new URL(window.location);
    url.searchParams.delete("login");
    window.history.replaceState({}, "", url);
  }

  // Bind Sign In buttons on landing page
  document.querySelectorAll('[data-auth-action="open"]').forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      openAuthModal();
    });
  });

  // Bind magic link / OTP form submission
  const magicForm = document.getElementById("magic-link-form");
  const otpStep = document.getElementById("otp-step");
  let _pendingOtpEmail = null;

  if (magicForm) {
    magicForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const statusEl = document.getElementById("magic-link-status");
      const emailInput = magicForm.querySelector('input[type="email"]');
      const email = emailInput?.value;
      if (!email) return;

      const submitBtn = magicForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      if (statusEl) { statusEl.textContent = ""; }

      try {
        const ps = pageState || {};
        if (ps.devAuthEnabled) {
          await devSignIn(email, email.split("@")[0], ps.language || "en");
          closeAuthModal();
          window.location.href = `/${ps.language || "en"}/app`;
        } else {
          const result = await sendMagicLink(email);
          if (result && result.method === "otp") {
            // OTP sent — show code input
            _pendingOtpEmail = email;
            magicForm.style.display = "none";
            if (otpStep) otpStep.style.display = "block";
            if (statusEl) {
              statusEl.style.color = "var(--accent-green)";
              statusEl.textContent = "";
            }
            const otpInput = document.getElementById("otp-input");
            if (otpInput) { otpInput.value = ""; otpInput.focus(); }
          }
        }
      } catch (err) {
        if (statusEl) {
          if (err.errorCode === "corporate_email_required") {
            statusEl.innerHTML = err.message || "Corporate email required.";
            statusEl.style.color = "var(--accent-red)";
            statusEl.style.display = "block";
          } else {
            statusEl.style.color = "var(--accent-red)";
            statusEl.textContent = err.message || "Failed to send verification code.";
          }
        }
        if (err.errorCode === "not_registered") {
          setTimeout(() => {
            closeAuthModal();
            const accessForm = document.getElementById("access-request-form");
            if (accessForm) {
              accessForm.scrollIntoView({ behavior: "smooth", block: "center" });
              const emailField = accessForm.querySelector('input[type="email"]');
              if (emailField) emailField.value = email;
            }
          }, 2000);
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // OTP verify button
  const otpVerifyBtn = document.getElementById("otp-verify-btn");
  if (otpVerifyBtn) {
    otpVerifyBtn.addEventListener("click", async () => {
      const statusEl = document.getElementById("magic-link-status");
      const otpInput = document.getElementById("otp-input");
      const code = otpInput?.value?.trim();
      if (!code || !_pendingOtpEmail) return;
      otpVerifyBtn.disabled = true;
      try {
        const res = await setupFetch("/api/v1/auth/verify-otp", {
          method: "POST",
          body: JSON.stringify({ email: _pendingOtpEmail, code }),
        });
        const data = await res.json().catch(() => ({}));
        if (data.action === "complete_registration") {
          // New user — show registration step
          if (otpStep) otpStep.style.display = "none";
          const regStep = document.getElementById("auth-step-register");
          if (regStep) regStep.style.display = "block";
          window._regToken = data.registration_token;
          return;
        }
        if (res.ok && data.authenticated) {
          _notifyAuthChange(data);
          closeAuthModal();
          const ps = pageState || {};
          window.location.href = `/${ps.language || "en"}/app`;
        } else {
          if (statusEl) {
            statusEl.style.color = "var(--accent-red)";
            statusEl.textContent = data.error || "Invalid code.";
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = "var(--accent-red)";
          statusEl.textContent = err.message || "Verification failed.";
        }
      } finally {
        otpVerifyBtn.disabled = false;
      }
    });
  }

  // OTP resend button
  const otpResendBtn = document.getElementById("otp-resend-btn");
  if (otpResendBtn) {
    otpResendBtn.addEventListener("click", async () => {
      if (!_pendingOtpEmail) return;
      const statusEl = document.getElementById("magic-link-status");
      otpResendBtn.disabled = true;
      try {
        await sendMagicLink(_pendingOtpEmail);
        if (statusEl) {
          statusEl.style.color = "var(--accent-green)";
          statusEl.textContent = "New code sent!";
        }
      } catch (err) {
        if (statusEl) {
          statusEl.style.color = "var(--accent-red)";
          statusEl.textContent = err.message || "Failed to resend.";
        }
      } finally {
        setTimeout(() => { otpResendBtn.disabled = false; }, 30000);
      }
    });
  }

  // OTP input: auto-submit on 6 digits and Enter key
  const otpInput = document.getElementById("otp-input");
  if (otpInput) {
    otpInput.addEventListener("input", () => {
      otpInput.value = otpInput.value.replace(/[^0-9]/g, "");
      if (otpInput.value.length === 6 && otpVerifyBtn) otpVerifyBtn.click();
    });
    otpInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && otpVerifyBtn) otpVerifyBtn.click();
    });
  }

  // Registration step: complete account creation
  const btnCompleteReg = document.getElementById("btn-complete-register");
  if (btnCompleteReg) {
    btnCompleteReg.addEventListener("click", async () => {
      const nameInput = document.getElementById("register-name");
      const regError = document.getElementById("register-error");
      const name = nameInput?.value?.trim();
      const ps = pageState || {};
      const lang = ps.language || "en";
      if (!name || name.length < 2) {
        if (regError) {
          regError.textContent = lang === "es" ? "El nombre debe tener al menos 2 caracteres." : "Name must be at least 2 characters.";
          regError.style.display = "block";
        }
        return;
      }
      btnCompleteReg.disabled = true;
      try {
        const res = await setupFetch("/api/v1/auth/complete-registration", {
          method: "POST",
          body: JSON.stringify({ registration_token: window._regToken, full_name: name }),
        });
        const result = await res.json().catch(() => ({}));
        if (result.action === "registered" || (res.ok && result.authenticated)) {
          _notifyAuthChange(result);
          closeAuthModal();
          window.location.href = `/${lang}/app#dashboard`;
        } else {
          if (regError) {
            regError.textContent = result.error || result.detail || (lang === "es" ? "Error al registrar." : "Registration failed.");
            regError.style.display = "block";
          }
        }
      } catch (err) {
        if (regError) {
          regError.textContent = err.message || "Registration failed.";
          regError.style.display = "block";
        }
      } finally {
        btnCompleteReg.disabled = false;
      }
    });
  }
}

export function openSignIn(reason, defaultEmail) {
  openAuthModal(reason, defaultEmail);
}
