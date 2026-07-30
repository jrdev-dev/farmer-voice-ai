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
        document.getElementById("email");

    const passwordInput =
        document.getElementById("password");

    const loginButton =
        document.getElementById("loginButton");

    const loginButtonText =
        document.getElementById("loginButtonText");

    const loginLoader =
        document.getElementById("loginLoader");

    const loginMessage =
        document.getElementById("loginMessage");

    // IMPORTANT:
    // This matches login.html:
    // id="togglePassword"

    const passwordToggle =
        document.getElementById("togglePassword");


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

    if (!loginForm) {

        console.error(
            "Farmer Voice AI: loginForm was not found."
        );

        return;
    }


    // ========================================================
    // LOGIN SUBMIT
    // ========================================================

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

        }
    );


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

        if (!loginMessage) {
            return;
        }


        loginMessage.textContent =
            message;


        loginMessage.classList.remove(
            "success",
            "error",
            "info"
        );


        loginMessage.classList.add(
            type
        );


        loginMessage.hidden =
            false;
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
