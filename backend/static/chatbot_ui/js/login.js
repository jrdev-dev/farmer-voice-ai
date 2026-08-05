// ============================================================
// FARMER VOICE AI - LOGIN
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // ========================================================
    // DOM ELEMENTS
    // ========================================================

    const loginForm =
        document.getElementById("loginForm");

    const emailInput =
        document.getElementById("loginEmail") || document.getElementById("email");

    const passwordInput =
        document.getElementById("loginPassword") || document.getElementById("password");

    const loginButton =
        document.getElementById("loginSubmitBtn") || document.getElementById("loginButton");

    const loginButtonText =
        document.querySelector("#loginSubmitBtn .btn-label") || document.getElementById("loginButtonText");

    const loginLoader =
        document.querySelector("#loginSubmitBtn .btn-spinner") || document.getElementById("loginLoader");

    const loginMessage =
        document.getElementById("authMessage") || document.getElementById("loginMessage");

    const passwordToggle =
        document.getElementById("toggleLoginPassword") || document.getElementById("togglePassword");


    // ========================================================
    // STORAGE KEYS
    // ========================================================
    //
    // These MUST match chat.js.
    // ========================================================

    const ACCESS_TOKEN_KEY =
        "farmer_access_token";

    const REFRESH_TOKEN_KEY =
        "farmer_refresh_token";

    const USER_KEY =
        "farmer_user";


    // ========================================================
    // ALREADY LOGGED IN
    // ========================================================

    const existingAccessToken =
        localStorage.getItem(
            ACCESS_TOKEN_KEY
        );

    if (existingAccessToken) {

        window.location.replace(
            "/chat/"
        );

        return;
    }


    // ========================================================
    // PASSWORD VISIBILITY
    // ========================================================

    if (
        passwordToggle &&
        passwordInput
    ) {

        passwordToggle.addEventListener(
            "click",
            (event) => {

                event.preventDefault();


                const isPassword =
                    passwordInput.type ===
                    "password";


                passwordInput.type =
                    isPassword
                        ? "text"
                        : "password";


                passwordToggle.textContent =
                    isPassword
                        ? "🙈"
                        : "👁️";


                passwordToggle.setAttribute(
                    "aria-label",
                    isPassword
                        ? "Hide password"
                        : "Show password"
                );

            }
        );

    }


    // ========================================================
    // FORM CHECK
    // ========================================================
    // LOGIN SUBMIT
    // ========================================================

    if (loginForm) {
        loginForm.addEventListener(
            "submit",
            async (event) => {

            event.preventDefault();


            // =================================================
            // INPUT VALUES
            // =================================================

            const email =
                emailInput
                    ? emailInput.value.trim()
                    : "";


            const password =
                passwordInput
                    ? passwordInput.value
                    : "";


            // =================================================
            // BASIC VALIDATION
            // =================================================

            if (!email) {

                showMessage(
                    "Please enter your email address.",
                    "error"
                );

                emailInput?.focus();

                return;
            }


            if (!password) {

                showMessage(
                    "Please enter your password.",
                    "error"
                );

                passwordInput?.focus();

                return;
            }


            // =================================================
            // LOADING STATE
            // =================================================

            setLoading(true);

            showMessage(
                "Signing in...",
                "info"
            );


            try {

                // =============================================
                // LOGIN API
                // =============================================

                const response =
                    await fetch(
                        "/api/accounts/login/",
                        {
                            method: "POST",

                            headers: {
                                "Accept":
                                    "application/json",

                                "Content-Type":
                                    "application/json",
                            },

                            body: JSON.stringify({
                                email,
                                password,
                            }),
                        }
                    );


                // =============================================
                // PARSE RESPONSE
                // =============================================

                let result = null;


                try {

                    result =
                        await response.json();

                } catch (parseError) {

                    console.error(
                        "Login response JSON error:",
                        parseError
                    );

                    throw new Error(
                        "Server returned an invalid response."
                    );
                }


                // =============================================
                // HTTP ERROR
                // =============================================

                if (!response.ok) {

                    const errorMessage =
                        getErrorMessage(
                            result
                        );


                    throw new Error(
                        errorMessage
                    );
                }


                // =============================================
                // SUPPORT API WRAPPER
                // =============================================
                //
                // Expected:
                //
                // {
                //   success: true,
                //   message: "...",
                //   data: {
                //      access: "...",
                //      refresh: "...",
                //      user: {...}
                //   }
                // }
                //
                // =================================================

                const data =
                    result?.data ||
                    result;


                const accessToken =
                    data?.access;


                const refreshToken =
                    data?.refresh;


                const user =
                    data?.user;


                // =============================================
                // ACCESS TOKEN REQUIRED
                // =============================================

                if (!accessToken) {

                    console.error(
                        "Login API response:",
                        result
                    );

                    throw new Error(
                        "Login succeeded but access token was not returned."
                    );
                }


                // =============================================
                // SAVE ACCESS TOKEN
                // =============================================

                localStorage.setItem(
                    ACCESS_TOKEN_KEY,
                    accessToken
                );


                // =============================================
                // SAVE REFRESH TOKEN
                // =============================================

                if (refreshToken) {

                    localStorage.setItem(
                        REFRESH_TOKEN_KEY,
                        refreshToken
                    );

                } else {

                    localStorage.removeItem(
                        REFRESH_TOKEN_KEY
                    );
                }


                // =============================================
                // SAVE USER
                // =============================================

                if (user) {

                    localStorage.setItem(
                        USER_KEY,
                        JSON.stringify(user)
                    );

                } else {

                    localStorage.removeItem(
                        USER_KEY
                    );
                }


                // =============================================
                // SUCCESS
                // =============================================

                showMessage(
                    result?.message ||
                    "Login successful. Opening assistant...",
                    "success"
                );


                // =============================================
                // REDIRECT
                // =============================================

                window.location.replace(
                    "/chat/"
                );

            } catch (error) {

                // =============================================
                // LOGIN FAILURE
                // =============================================

                console.error(
                    "Farmer Voice AI login failed:",
                    error
                );


                showMessage(
                    error?.message ||
                    "Unable to login. Please try again.",
                    "error"
                );


            } finally {

                setLoading(false);
            }

        });
    }


    // ========================================================
    // REGISTER FORM SUBMISSION
    // ========================================================

    const registerForm = document.getElementById("registerForm");
    const regNameInput = document.getElementById("regName");
    const regEmailInput = document.getElementById("regEmail");
    const regPasswordInput = document.getElementById("regPassword");
    const regLanguageInput = document.getElementById("regLanguage");
    const regSubmitBtn = document.getElementById("registerSubmitBtn");
    const toggleRegPassword = document.getElementById("toggleRegPassword");

    if (toggleRegPassword && regPasswordInput) {
        toggleRegPassword.addEventListener("click", (e) => {
            e.preventDefault();
            const isPassword = regPasswordInput.type === "password";
            regPasswordInput.type = isPassword ? "text" : "password";
            toggleRegPassword.textContent = isPassword ? "🙈" : "👁️";
        });
    }

    if (registerForm) {
        registerForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const name = regNameInput?.value?.trim() || "";
            const email = regEmailInput?.value?.trim() || "";
            const password = regPasswordInput?.value || "";
            const preferred_language = regLanguageInput?.value || "hi";

            if (!name || !email || !password) {
                showMessage("Please fill out all required registration fields.", "error");
                return;
            }

            const nameParts = name.split(" ");
            const first_name = nameParts[0] || name;
            const last_name = nameParts.slice(1).join(" ") || "";

            try {
                if (regSubmitBtn) regSubmitBtn.disabled = true;
                showMessage("Creating your account...", "info");

                const response = await fetch("/api/accounts/register/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body: JSON.stringify({
                        email,
                        first_name,
                        last_name,
                        password,
                        confirm_password: password,
                        preferred_language,
                    }),
                });

                const result = await response.json();

                if (!response.ok) {
                    let err = "Registration failed. Please try again.";
                    if (result) {
                        if (result.message) err = result.message;
                        else if (result.detail) err = result.detail;
                        else if (result.email) err = typeof result.email === 'string' ? result.email : result.email[0];
                        else if (result.password) err = typeof result.password === 'string' ? result.password : result.password[0];
                        else if (result.error) err = result.error;
                        else if (result.errors) err = typeof result.errors === 'string' ? result.errors : Object.values(result.errors)[0][0];
                    }
                    throw new Error(err);
                }

                const tokenData = result?.data || result;

                if (tokenData?.access) {
                    localStorage.setItem(ACCESS_TOKEN_KEY, tokenData.access);
                    if (tokenData.refresh) localStorage.setItem(REFRESH_TOKEN_KEY, tokenData.refresh);
                    if (tokenData.user) localStorage.setItem(USER_KEY, JSON.stringify(tokenData.user));
                    showMessage("Account created! Redirecting to assistant...", "success");
                    window.location.replace("/chat/");
                } else {
                    // Fallback to explicit login call
                    const loginResponse = await fetch("/api/accounts/login/", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                        body: JSON.stringify({ email, password }),
                    });
                    const loginResult = await loginResponse.json();
                    const loginTokenData = loginResult?.data || loginResult;

                    if (loginTokenData?.access) {
                        localStorage.setItem(ACCESS_TOKEN_KEY, loginTokenData.access);
                        if (loginTokenData.refresh) localStorage.setItem(REFRESH_TOKEN_KEY, loginTokenData.refresh);
                        if (loginTokenData.user) localStorage.setItem(USER_KEY, JSON.stringify(loginTokenData.user));
                    }
                    window.location.replace("/chat/");
                }
            } catch (error) {
                console.error("Registration error:", error);
                showMessage(error.message || "Registration failed.", "error");
            } finally {
                if (regSubmitBtn) regSubmitBtn.disabled = false;
            }
        });
    }


    // ========================================================
    // GET ERROR MESSAGE
    // ========================================================

    function getErrorMessage(result) {

        if (!result) {

            return (
                "Unable to login. " +
                "Please check your email and password."
            );
        }


        if (
            typeof result.message ===
            "string"
        ) {

            return result.message;
        }


        if (
            typeof result.detail ===
            "string"
        ) {

            return result.detail;
        }


        if (
            Array.isArray(
                result.non_field_errors
            ) &&
            result.non_field_errors.length
        ) {

            return String(
                result.non_field_errors[0]
            );
        }


        if (
            Array.isArray(result.email) &&
            result.email.length
        ) {

            return String(
                result.email[0]
            );
        }


        if (
            Array.isArray(result.password) &&
            result.password.length
        ) {

            return String(
                result.password[0]
            );
        }


        return (
            "Invalid email or password."
        );
    }


    // ========================================================
    // SHOW MESSAGE
    // ========================================================

    function showMessage(
        message,
        type = "info"
    ) {
        let msgEl = loginMessage || document.getElementById("authMessage") || document.getElementById("loginMessage");
        if (!msgEl) {
            return;
        }

        msgEl.textContent = message;
        msgEl.classList.remove("success", "error", "info");
        msgEl.classList.add(type);
        msgEl.removeAttribute("hidden");
        msgEl.style.display = "block";
    }


    // ========================================================
    // LOADING STATE
    // ========================================================

    function setLoading(
        isLoading
    ) {

        if (loginButton) {

            loginButton.disabled =
                isLoading;
        }


        if (loginButtonText) {

            loginButtonText.textContent =
                isLoading
                    ? "Signing in..."
                    : "Login";

        } else if (loginButton) {

            loginButton.textContent =
                isLoading
                    ? "Signing in..."
                    : "Login";
        }


        if (loginLoader) {

            loginLoader.hidden =
                !isLoading;
        }


        if (emailInput) {

            emailInput.disabled =
                isLoading;
        }


        if (passwordInput) {

            passwordInput.disabled =
                isLoading;
        }
    }

});
