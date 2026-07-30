"use strict";


// ============================================================
// FARMER VOICE AI - CHAT FRONTEND
// Part 1:
// Authentication + JWT Refresh + Text Chat + Message Rendering
// ============================================================


// ============================================================
// API ENDPOINTS
// ============================================================

const API = {
    CHAT: "/api/chat/",
    PROFILE: "/api/accounts/profile/",
    REFRESH: "/api/accounts/token/refresh/",
};


// ============================================================
// DOM ELEMENTS
// ============================================================

const messagesContainer =
    document.getElementById("messagesContainer");

const messagesList =
    document.getElementById("messagesList");

const welcomePanel =
    document.getElementById("welcomePanel");

const typingIndicator =
    document.getElementById("typingIndicator");

const messageInput =
    document.getElementById("messageInput");

const sendButton =
    document.getElementById("sendButton");

const languageSelect =
    document.getElementById("languageSelect");

const newChatButton =
    document.getElementById("newChatButton");

const logoutButton =
    document.getElementById("logoutButton");

const userName =
    document.getElementById("userName");

const userEmail =
    document.getElementById("userEmail");

const mobileMenuButton =
    document.getElementById("mobileMenuButton");

const sidebar =
    document.getElementById("sidebar");


// ============================================================
// STATE
// ============================================================

let currentConversationId = null;

let isSendingMessage = false;


// ============================================================
// TOKEN HELPERS
// ============================================================

function getAccessToken() {

    return localStorage.getItem(
        "farmer_access_token"
    );
}


function getRefreshToken() {

    return localStorage.getItem(
        "farmer_refresh_token"
    );
}


function saveAccessToken(token) {

    if (!token) {
        return;
    }

    localStorage.setItem(
        "farmer_access_token",
        token
    );
}


function saveRefreshToken(token) {

    if (!token) {
        return;
    }

    localStorage.setItem(
        "farmer_refresh_token",
        token
    );
}


// ============================================================
// CLEAR AUTH
// ============================================================

function clearAuthentication() {

    localStorage.removeItem(
        "farmer_access_token"
    );

    localStorage.removeItem(
        "farmer_refresh_token"
    );

    localStorage.removeItem(
        "farmer_user"
    );
}


// ============================================================
// REDIRECT TO LOGIN
// ============================================================

function redirectToLogin() {

    clearAuthentication();

    window.location.replace("/");
}


// ============================================================
// REFRESH ACCESS TOKEN
// ============================================================

async function refreshAccessToken() {

    const refreshToken =
        getRefreshToken();


    if (!refreshToken) {

        return false;
    }


    try {

        const response =
            await fetch(
                API.REFRESH,
                {
                    method: "POST",

                    headers: {
                        "Accept":
                            "application/json",

                        "Content-Type":
                            "application/json",
                    },

                    body: JSON.stringify({
                        refresh:
                            refreshToken,
                    }),
                }
            );


        if (!response.ok) {

            return false;
        }


        const data =
            await response.json();


        const newAccessToken =
            data?.access ||
            data?.data?.access;


        const newRefreshToken =
            data?.refresh ||
            data?.data?.refresh;


        if (!newAccessToken) {

            return false;
        }


        saveAccessToken(
            newAccessToken
        );


        if (newRefreshToken) {

            saveRefreshToken(
                newRefreshToken
            );
        }


        return true;

    } catch (error) {

        console.error(
            "Token refresh failed:",
            error
        );


        return false;
    }
}


// ============================================================
// AUTHENTICATED FETCH
// ============================================================

async function authenticatedFetch(
    url,
    options = {},
    retry = true
) {

    const accessToken =
        getAccessToken();


    if (!accessToken) {

        redirectToLogin();

        throw new Error(
            "Authentication required."
        );
    }


    const headers =
        new Headers(
            options.headers || {}
        );


    headers.set(
        "Authorization",
        `Bearer ${accessToken}`
    );


    if (
        options.body &&
        !(options.body instanceof FormData) &&
        !headers.has("Content-Type")
    ) {

        headers.set(
            "Content-Type",
            "application/json"
        );
    }


    if (!headers.has("Accept")) {

        headers.set(
            "Accept",
            "application/json"
        );
    }


    const response =
        await fetch(
            url,
            {
                ...options,
                headers,
            }
        );


    // ========================================================
    // ACCESS TOKEN EXPIRED
    // ========================================================

    if (
        response.status === 401 &&
        retry
    ) {

        const refreshed =
            await refreshAccessToken();


        if (refreshed) {

            return authenticatedFetch(
                url,
                options,
                false
            );
        }


        redirectToLogin();

        throw new Error(
            "Your session has expired."
        );
    }


    return response;
}


// ============================================================
// LOAD USER PROFILE
// ============================================================

async function loadUserProfile() {

    try {

        const cachedUser =
            localStorage.getItem(
                "farmer_user"
            );


        if (cachedUser) {

            try {

                const parsed =
                    JSON.parse(
                        cachedUser
                    );


                updateUserUI(
                    parsed
                );

            } catch (error) {

                console.warn(
                    "Could not parse cached user.",
                    error
                );
            }
        }


        const response =
            await authenticatedFetch(
                API.PROFILE,
                {
                    method: "GET",
                }
            );


        if (!response.ok) {

            return;
        }


        const result =
            await response.json();


        const profile =
            result?.data ||
            result;


        if (!profile) {

            return;
        }


        localStorage.setItem(
            "farmer_user",
            JSON.stringify(
                profile
            )
        );


        updateUserUI(
            profile
        );

    } catch (error) {

        console.error(
            "Unable to load profile:",
            error
        );
    }
}


// ============================================================
// UPDATE USER UI
// ============================================================

function updateUserUI(user) {

    if (!user) {
        return;
    }


    const firstName =
        user.first_name || "";


    const lastName =
        user.last_name || "";


    const fullName =
        `${firstName} ${lastName}`
            .trim();


    if (userName) {

        userName.textContent =
            fullName ||
            user.email ||
            "Farmer";
    }


    if (userEmail) {

        userEmail.textContent =
            user.email || "";
    }
}


// ============================================================
// TEXT CHAT
// ============================================================

async function sendTextMessage(
    forcedMessage = null
) {

    if (isSendingMessage) {
        return;
    }


    const message =
        forcedMessage !== null
            ? String(
                forcedMessage
            ).trim()
            : (
                messageInput
                    ? messageInput.value.trim()
                    : ""
            );


    if (!message) {

        if (messageInput) {
            messageInput.focus();
        }

        return;
    }


    const selectedLanguage =
        languageSelect
            ? languageSelect.value.trim()
            : "";


    isSendingMessage = true;


    setSendButtonState(
        true
    );


    hideWelcomePanel();


    appendUserMessage(
        message
    );


    if (
        messageInput &&
        forcedMessage === null
    ) {

        messageInput.value = "";

        resizeTextarea();
    }


    showTypingIndicator();


    try {

        const payload = {
            message,
        };


        if (selectedLanguage) {

            payload.language =
                selectedLanguage;
        }


        const response =
            await authenticatedFetch(
                API.CHAT,
                {
                    method: "POST",

                    body: JSON.stringify(
                        payload
                    ),
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                "The server returned an invalid chat response."
            );
        }


        if (!response.ok) {

            const errorMessage =
                extractErrorMessage(
                    result
                );


            throw new Error(
                errorMessage
            );
        }


        if (
            result?.conversation_id
        ) {

            currentConversationId =
                result.conversation_id;
        }


        appendAssistantMessage(
            result
        );


    } catch (error) {

        console.error(
            "Chat request failed:",
            error
        );


        appendSystemMessage(
            error?.message ||
            "Unable to get an answer right now. Please try again."
        );


    } finally {

        hideTypingIndicator();


        isSendingMessage =
            false;


        setSendButtonState(
            false
        );


        if (messageInput) {

            messageInput.focus();
        }
    }
}


// ============================================================
// SEND BUTTON
// ============================================================

if (sendButton) {

    sendButton.addEventListener(
        "click",
        () => {

            sendTextMessage();

        }
    );
}


// ============================================================
// ENTER TO SEND
// ============================================================

if (messageInput) {

    messageInput.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendTextMessage();
            }
        }
    );
}


// ============================================================
// AUTO RESIZE TEXTAREA
// ============================================================

if (messageInput) {

    messageInput.addEventListener(
        "input",
        resizeTextarea
    );
}


function resizeTextarea() {

    if (!messageInput) {
        return;
    }


    messageInput.style.height =
        "auto";


    const maxHeight = 150;


    messageInput.style.height =
        `${Math.min(
            messageInput.scrollHeight,
            maxHeight
        )}px`;
}


// ============================================================
// SUGGESTED QUESTIONS
// ============================================================

document
    .querySelectorAll(
        ".suggestion-card"
    )
    .forEach(
        (card) => {

            card.addEventListener(
                "click",
                () => {

                    const question =
                        (
                            card.dataset.question ||
                            card.textContent ||
                            ""
                        ).trim();


                    if (!question) {
                        return;
                    }


                    sendTextMessage(
                        question
                    );
                }
            );

        }
    );


// ============================================================
// MESSAGE HELPERS
// ============================================================

function appendUserMessage(text) {

    if (!messagesList) {
        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "message-row user-message-row";


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message-bubble user-message";


    bubble.textContent =
        text;


    wrapper.appendChild(
        bubble
    );


    messagesList.appendChild(
        wrapper
    );


    scrollMessagesToBottom();
}


// ============================================================
// ASSISTANT MESSAGE
// ============================================================

function appendAssistantMessage(result) {

    if (!messagesList) {
        return;
    }


    const answer =
        result?.answer ||
        result?.message ||
        "I could not generate an answer.";


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "message-row assistant-message-row";


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message-bubble assistant-message";


    // ========================================================
    // ANSWER TEXT
    // ========================================================

    const answerElement =
        document.createElement(
            "div"
        );


    answerElement.className =
        "assistant-answer";


    answerElement.textContent =
        answer;


    bubble.appendChild(
        answerElement
    );


    const isGreeting = Boolean(result?.isGreeting || result?.is_greeting || false);

    // ========================================================
    // METADATA (Skip for Greeting Messages)
    // ========================================================

    const metadata =
        document.createElement(
            "div"
        );


    metadata.className =
        "message-metadata";


    const confidence =
        result?.confidence;


    const confidenceLabel =
        result?.confidence_label;


    if (
        !isGreeting &&
        confidence !== undefined &&
        confidence !== null
    ) {

        const confidenceElement =
            document.createElement(
                "span"
            );


        confidenceElement.className =
            "confidence-badge";


        confidenceElement.textContent =
            confidenceLabel
                ? `Confidence: ${confidence}% (${confidenceLabel})`
                : `Confidence: ${confidence}%`;


        metadata.appendChild(
            confidenceElement
        );
    }


    const language =
        result?.language;


    if (language && !isGreeting) {

        const languageElement =
            document.createElement(
                "span"
            );


        languageElement.className =
            "language-badge";


        languageElement.textContent =
            `Language: ${language}`;


        metadata.appendChild(
            languageElement
        );
    }


    if (metadata.children.length) {

        bubble.appendChild(
            metadata
        );
    }


    // ========================================================
    // SOURCES (Removed per user directive)
    // ========================================================
    const sources = [];


    // ========================================================
    // FEEDBACK CONTROLS
    // ========================================================

    const messageId =
        result?.message_id;


    // ========================================================
    // SPEAKER / LISTEN BUTTON (FOR REGULAR QA RESPONSES ONLY)
    // ========================================================
    if (!isGreeting) {
        const speakerButton = document.createElement("button");
        speakerButton.type = "button";
        speakerButton.className = "speaker-listen-btn";
        speakerButton.innerHTML = "🔊 Listen Answer / उत्तर सुनें";
        speakerButton.title = "Tap to listen to this answer as many times as you want";
        
        let activeAudio = null;
        speakerButton.addEventListener("click", () => {
            const audioUrl = result?.audio_url || result?.tts_url || result?.speech_url;
            if (audioUrl) {
                if (activeAudio) {
                    activeAudio.pause();
                    activeAudio.currentTime = 0;
                }
                activeAudio = new Audio(audioUrl);
                speakerButton.innerHTML = "🔊 Playing Answer...";
                activeAudio.play().then(() => {
                    activeAudio.onended = () => {
                        speakerButton.innerHTML = "🔊 Listen Answer / उत्तर सुनें";
                    };
                }).catch(() => {
                    speakFallbackWebSpeech(answer, result?.language, speakerButton);
                });
            } else {
                speakFallbackWebSpeech(answer, result?.language, speakerButton);
            }
        });

        function speakFallbackWebSpeech(textToSpeak, lang, btn) {
            if (!("speechSynthesis" in window)) return;
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(textToSpeak);
            utterance.lang = lang === "en" ? "en-IN" : "hi-IN";
            btn.innerHTML = "🔊 Speaking Answer...";
            utterance.onend = () => {
                btn.innerHTML = "🔊 Listen Answer / उत्तर सुनें";
            };
            window.speechSynthesis.speak(utterance);
        }

        bubble.appendChild(speakerButton);
    }

    if (messageId) {

        const feedbackContainer =
            document.createElement(
                "div"
            );


        feedbackContainer.className =
            "feedback-controls";


        feedbackContainer.dataset.messageId =
            String(messageId);


        const helpfulButton =
            document.createElement(
                "button"
            );


        helpfulButton.type =
            "button";


        helpfulButton.className =
            "feedback-button";


        helpfulButton.dataset.rating =
            "HELPFUL";


        helpfulButton.textContent =
            "👍";


        helpfulButton.title =
            "Helpful";


        const notHelpfulButton =
            document.createElement(
                "button"
            );


        notHelpfulButton.type =
            "button";


        notHelpfulButton.className =
            "feedback-button";


        notHelpfulButton.dataset.rating =
            "NOT_HELPFUL";


        notHelpfulButton.textContent =
            "👎";


        notHelpfulButton.title =
            "Not helpful";


        feedbackContainer.append(
            helpfulButton,
            notHelpfulButton
        );


        bubble.appendChild(
            feedbackContainer
        );
    }


    wrapper.appendChild(
        bubble
    );


    messagesList.appendChild(
        wrapper
    );


    scrollMessagesToBottom();
}


// ============================================================
// SYSTEM MESSAGE
// ============================================================

function appendSystemMessage(text) {

    if (!messagesList) {
        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "message-row system-message-row";


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message-bubble system-message";


    bubble.textContent =
        text;


    wrapper.appendChild(
        bubble
    );


    messagesList.appendChild(
        wrapper
    );


    scrollMessagesToBottom();
}


// ============================================================
// WELCOME PANEL
// ============================================================

function hideWelcomePanel() {

    if (!welcomePanel) {
        return;
    }


    welcomePanel.hidden =
        true;


    welcomePanel.style.display =
        "none";
}


function showWelcomePanel() {

    if (!welcomePanel) {
        return;
    }


    welcomePanel.hidden =
        false;


    welcomePanel.style.display =
        "";
}


// ============================================================
// TYPING INDICATOR
// ============================================================

function showTypingIndicator() {

    if (!typingIndicator) {
        return;
    }


    typingIndicator.hidden =
        false;


    typingIndicator.style.display =
        "";
}


function hideTypingIndicator() {

    if (!typingIndicator) {
        return;
    }


    typingIndicator.hidden =
        true;


    typingIndicator.style.display =
        "none";
}


// ============================================================
// SEND BUTTON STATE
// ============================================================

function setSendButtonState(
    loading
) {

    if (!sendButton) {
        return;
    }


    sendButton.disabled =
        loading;


    sendButton.setAttribute(
        "aria-busy",
        loading
            ? "true"
            : "false"
    );
}


// ============================================================
// SCROLL
// ============================================================

function scrollMessagesToBottom() {

    if (!messagesContainer) {
        return;
    }


    requestAnimationFrame(
        () => {

            messagesContainer.scrollTop =
                messagesContainer.scrollHeight;

        }
    );
}


// ============================================================
// ERROR MESSAGE EXTRACTION
// ============================================================

function extractErrorMessage(
    result
) {

    if (!result) {

        return (
            "The request could not be completed."
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
        typeof result.error ===
        "string"
    ) {

        return result.error;
    }


    if (
        result.message &&
        Array.isArray(
            result.message
        )
    ) {

        return String(
            result.message[0]
        );
    }


    return (
        "The request could not be completed."
    );
}
// ============================================================
// PART 2 - VOICE CHAT + AUDIO PLAYBACK
// ============================================================


// ============================================================
// VOICE DOM ELEMENTS
// ============================================================

const voiceButton =
    document.getElementById("voiceButton");

const recordingIndicator =
    document.getElementById("recordingIndicator");

const recordingTimer =
    document.getElementById("recordingTimer");

const stopRecordingButton =
    document.getElementById("stopRecordingButton");

const responseAudioPlayer =
    document.getElementById("responseAudioPlayer");


// ============================================================
// VOICE API
// ============================================================

API.VOICE =
    "/api/speech/chat/";


// ============================================================
// VOICE STATE
// ============================================================

let mediaRecorder = null;

let microphoneStream = null;

let recordedAudioChunks = [];

let isRecording = false;

let isProcessingVoice = false;

let recordingStartedAt = null;

let recordingTimerInterval = null;


// ============================================================
// START VOICE RECORDING
// ============================================================

async function startVoiceRecording() {

    if (isRecording || isProcessingVoice) {
        return;
    }


    // ========================================================
    // BROWSER SUPPORT
    // ========================================================

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {

        appendSystemMessage(
            "Voice recording is not supported by this browser."
        );

        return;
    }


    if (
        typeof MediaRecorder ===
        "undefined"
    ) {

        appendSystemMessage(
            "Audio recording is not supported by this browser."
        );

        return;
    }


    try {

        // ====================================================
        // REQUEST MICROPHONE
        // ====================================================

        microphoneStream =
            await navigator.mediaDevices.getUserMedia(
                {
                    audio: true,
                }
            );


        recordedAudioChunks = [];


        // ====================================================
        // SELECT SUPPORTED FORMAT
        // ====================================================

        const recorderOptions =
            getRecorderOptions();


        if (recorderOptions) {

            mediaRecorder =
                new MediaRecorder(
                    microphoneStream,
                    recorderOptions
                );

        } else {

            mediaRecorder =
                new MediaRecorder(
                    microphoneStream
                );
        }


        // ====================================================
        // AUDIO DATA
        // ====================================================

        mediaRecorder.addEventListener(
            "dataavailable",
            (event) => {

                if (
                    event.data &&
                    event.data.size > 0
                ) {

                    recordedAudioChunks.push(
                        event.data
                    );
                }

            }
        );


        // ====================================================
        // RECORDING STOPPED
        // ====================================================

        mediaRecorder.addEventListener(
            "stop",
            async () => {

                const mimeType =
                    mediaRecorder?.mimeType ||
                    "audio/webm";


                const audioBlob =
                    new Blob(
                        recordedAudioChunks,
                        {
                            type: mimeType,
                        }
                    );


                cleanupMicrophoneStream();

                stopRecordingTimer();

                setRecordingUI(
                    false
                );


                isRecording =
                    false;


                // ============================================
                // EMPTY RECORDING
                // ============================================

                if (
                    !audioBlob ||
                    audioBlob.size <= 0
                ) {

                    appendSystemMessage(
                        "No audio was recorded. Please try again."
                    );

                    return;
                }


                // ============================================
                // SEND TO BACKEND
                // ============================================

                await sendVoiceRecording(
                    audioBlob,
                    mimeType
                );

            }
        );


        // ====================================================
        // RECORDER ERROR
        // ====================================================

        mediaRecorder.addEventListener(
            "error",
            (event) => {

                console.error(
                    "MediaRecorder error:",
                    event
                );


                cleanupMicrophoneStream();

                stopRecordingTimer();

                setRecordingUI(
                    false
                );


                isRecording =
                    false;


                appendSystemMessage(
                    "Voice recording failed. Please try again."
                );

            }
        );


        // ====================================================
        // START
        // ====================================================

        mediaRecorder.start();


        isRecording =
            true;


        recordingStartedAt =
            Date.now();


        setRecordingUI(
            true
        );


        startRecordingTimer();


    } catch (error) {

        console.error(
            "Unable to access microphone:",
            error
        );


        cleanupMicrophoneStream();

        stopRecordingTimer();

        setRecordingUI(
            false
        );


        isRecording =
            false;


        let message =
            "Unable to access the microphone.";


        if (
            error?.name ===
            "NotAllowedError"
        ) {

            message =
                "Microphone permission was denied. Please allow microphone access in your browser.";

        } else if (
            error?.name ===
            "NotFoundError"
        ) {

            message =
                "No microphone was found on this device.";

        } else if (
            error?.name ===
            "NotReadableError"
        ) {

            message =
                "The microphone is currently unavailable or being used by another application.";
        }


        appendSystemMessage(
            message
        );
    }
}


// ============================================================
// STOP VOICE RECORDING
// ============================================================

function stopVoiceRecording() {

    if (
        !isRecording ||
        !mediaRecorder
    ) {

        return;
    }


    try {

        if (
            mediaRecorder.state !==
            "inactive"
        ) {

            mediaRecorder.stop();
        }


    } catch (error) {

        console.error(
            "Unable to stop recording:",
            error
        );


        cleanupMicrophoneStream();

        stopRecordingTimer();

        setRecordingUI(
            false
        );


        isRecording =
            false;
    }
}


// ============================================================
// RECORDER FORMAT
// ============================================================

function getRecorderOptions() {

    if (
        typeof MediaRecorder ===
        "undefined"
    ) {

        return null;
    }


    const preferredTypes = [

        "audio/webm;codecs=opus",

        "audio/webm",

        "audio/ogg;codecs=opus",

        "audio/mp4",

    ];


    for (
        const mimeType of preferredTypes
    ) {

        try {

            if (
                MediaRecorder.isTypeSupported(
                    mimeType
                )
            ) {

                return {
                    mimeType,
                };
            }

        } catch (error) {

            console.warn(
                "Unable to check recording format:",
                mimeType,
                error
            );
        }
    }


    return null;
}


// ============================================================
// SEND VOICE RECORDING
// ============================================================

async function sendVoiceRecording(
    audioBlob,
    mimeType
) {

    if (isProcessingVoice) {
        return;
    }


    isProcessingVoice =
        true;


    setVoiceProcessingUI(
        true
    );


    hideWelcomePanel();

    showTypingIndicator();


    try {

        // ====================================================
        // BUILD AUDIO FILE
        // ====================================================

        const extension =
            getAudioExtension(
                mimeType
            );


        const filename =
            `farmer-question-${Date.now()}.${extension}`;


        const audioFile =
            new File(
                [audioBlob],
                filename,
                {
                    type:
                        mimeType ||
                        "audio/webm",
                }
            );


        // ====================================================
        // MULTIPART FORM
        // ====================================================

        const formData =
            new FormData();


        formData.append(
            "audio",
            audioFile
        );


        const selectedLanguage =
            languageSelect
                ? languageSelect.value.trim()
                : "";


        if (selectedLanguage) {

            formData.append(
                "language",
                selectedLanguage
            );
        }


        // ====================================================
        // SPEECH API
        // ====================================================

        const response =
            await authenticatedFetch(
                API.VOICE,
                {
                    method: "POST",

                    body: formData,
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                "The speech server returned an invalid response."
            );
        }


        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        // ====================================================
        // APPLICATION-LEVEL FAILURE
        // ====================================================

        if (
            result?.success === false
        ) {

            throw new Error(
                result?.message ||
                "Unable to process the voice question."
            );
        }


        // ====================================================
        // CONVERSATION
        // ====================================================

        if (
            result?.conversation_id
        ) {

            currentConversationId =
                result.conversation_id;
        }


        // ====================================================
        // TRANSCRIPT
        // ====================================================

        const transcript =
            result?.transcript ||
            result?.text ||
            result?.question ||
            result?.user_message ||
            "";


        if (transcript) {

            appendUserMessage(
                transcript
            );
        }


        // ====================================================
        // NORMALIZE VOICE RESPONSE
        // ====================================================

        const normalizedResult = {
            ...result,

            answer:
                result?.answer ||
                result?.response ||
                result?.message ||
                "Voice request processed successfully.",

            sources:
                Array.isArray(
                    result?.sources
                )
                    ? result.sources
                    : [],

            confidence:
                result?.confidence,

            confidence_label:
                result?.confidence_label,

            language:
                result?.language,

            message_id:
                result?.message_id,
        };


        appendAssistantMessage(
            normalizedResult
        );


        // ====================================================
        // PLAY GENERATED TTS
        // ====================================================

        const audioUrl =
            result?.audio_url ||
            result?.tts_url ||
            result?.speech_url;


        if (audioUrl) {

            await playResponseAudio(
                audioUrl
            );
        }


    } catch (error) {

        console.error(
            "Voice chat failed:",
            error
        );


        appendSystemMessage(
            error?.message ||
            "Unable to process your voice question."
        );


    } finally {

        hideTypingIndicator();


        isProcessingVoice =
            false;


        setVoiceProcessingUI(
            false
        );
    }
}


// ============================================================
// GET AUDIO EXTENSION
// ============================================================

function getAudioExtension(
    mimeType
) {

    const type =
        String(
            mimeType || ""
        ).toLowerCase();


    if (
        type.includes("ogg")
    ) {

        return "ogg";
    }


    if (
        type.includes("mp4") ||
        type.includes("m4a")
    ) {

        return "m4a";
    }


    if (
        type.includes("wav")
    ) {

        return "wav";
    }


    if (
        type.includes("mpeg") ||
        type.includes("mp3")
    ) {

        return "mp3";
    }


    return "webm";
}


// ============================================================
// PLAY RESPONSE AUDIO
// ============================================================

async function playResponseAudio(
    audioUrl
) {

    if (!audioUrl) {
        return;
    }


    try {

        // ====================================================
        // USE EXISTING AUDIO PLAYER
        // ====================================================

        if (responseAudioPlayer) {

            responseAudioPlayer.pause();


            responseAudioPlayer.src =
                audioUrl;


            responseAudioPlayer.load();


            try {

                await responseAudioPlayer.play();

            } catch (playError) {

                // Browser autoplay restrictions can block
                // automatic playback. The audio remains loaded
                // and can still be played manually.

                console.warn(
                    "Automatic audio playback was blocked:",
                    playError
                );
            }


            return;
        }


        // ====================================================
        // FALLBACK AUDIO OBJECT
        // ====================================================

        const audio =
            new Audio(
                audioUrl
            );


        try {

            await audio.play();

        } catch (playError) {

            console.warn(
                "Automatic TTS playback was blocked:",
                playError
            );
        }


    } catch (error) {

        console.error(
            "Unable to play response audio:",
            error
        );
    }
}


// ============================================================
// STOP CURRENT RESPONSE AUDIO
// ============================================================

function stopResponseAudio() {

    if (!responseAudioPlayer) {
        return;
    }


    try {

        responseAudioPlayer.pause();

        responseAudioPlayer.currentTime =
            0;

    } catch (error) {

        console.warn(
            "Unable to stop response audio:",
            error
        );
    }
}


// ============================================================
// RECORDING UI
// ============================================================

function setRecordingUI(
    recording
) {

    if (voiceButton) {

        voiceButton.classList.toggle(
            "recording",
            recording
        );


        voiceButton.setAttribute(
            "aria-pressed",
            recording
                ? "true"
                : "false"
        );


        voiceButton.title =
            recording
                ? "Stop recording"
                : "Ask with voice";
    }


    if (recordingIndicator) {

        recordingIndicator.hidden =
            !recording;


        recordingIndicator.style.display =
            recording
                ? ""
                : "none";
    }


    if (stopRecordingButton) {

        stopRecordingButton.hidden =
            !recording;
    }
}


// ============================================================
// VOICE PROCESSING UI
// ============================================================

function setVoiceProcessingUI(
    processing
) {

    if (!voiceButton) {
        return;
    }


    voiceButton.disabled =
        processing;


    voiceButton.classList.toggle(
        "processing",
        processing
    );


    voiceButton.setAttribute(
        "aria-busy",
        processing
            ? "true"
            : "false"
    );


    if (processing) {

        voiceButton.title =
            "Processing voice question...";

    } else if (!isRecording) {

        voiceButton.title =
            "Ask with voice";
    }
}


// ============================================================
// RECORDING TIMER
// ============================================================

function startRecordingTimer() {

    stopRecordingTimer();


    updateRecordingTimer();


    recordingTimerInterval =
        window.setInterval(
            updateRecordingTimer,
            1000
        );
}


function stopRecordingTimer() {

    if (
        recordingTimerInterval !==
        null
    ) {

        window.clearInterval(
            recordingTimerInterval
        );


        recordingTimerInterval =
            null;
    }


    recordingStartedAt =
        null;


    if (recordingTimer) {

        recordingTimer.textContent =
            "00:00";
    }
}


function updateRecordingTimer() {

    if (
        !recordingTimer ||
        !recordingStartedAt
    ) {

        return;
    }


    const elapsedMilliseconds =
        Date.now() -
        recordingStartedAt;


    const totalSeconds =
        Math.floor(
            elapsedMilliseconds /
            1000
        );


    const minutes =
        Math.floor(
            totalSeconds /
            60
        );


    const seconds =
        totalSeconds %
        60;


    recordingTimer.textContent =
        `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}


// ============================================================
// CLEAN MICROPHONE STREAM
// ============================================================

function cleanupMicrophoneStream() {

    if (!microphoneStream) {
        return;
    }


    microphoneStream
        .getTracks()
        .forEach(
            (track) => {

                try {

                    track.stop();

                } catch (error) {

                    console.warn(
                        "Unable to stop microphone track:",
                        error
                    );
                }

            }
        );


    microphoneStream =
        null;
}


// ============================================================
// VOICE BUTTON
// ============================================================

if (voiceButton) {

    voiceButton.addEventListener(
        "click",
        async () => {

            if (isProcessingVoice) {
                return;
            }


            if (isRecording) {

                stopVoiceRecording();

                return;
            }


            await startVoiceRecording();

        }
    );
}


// ============================================================
// OPTIONAL STOP RECORDING BUTTON
// ============================================================

if (stopRecordingButton) {

    stopRecordingButton.addEventListener(
        "click",
        () => {

            stopVoiceRecording();

        }
    );
}


// ============================================================
// AUDIO PLAYER FINISHED
// ============================================================

if (responseAudioPlayer) {

    responseAudioPlayer.addEventListener(
        "ended",
        () => {

            responseAudioPlayer.currentTime =
                0;

        }
    );
}


// ============================================================
// CLEANUP WHEN PAGE CLOSES
// ============================================================

window.addEventListener(
    "beforeunload",
    () => {

        if (
            mediaRecorder &&
            mediaRecorder.state !==
            "inactive"
        ) {

            try {

                mediaRecorder.stop();

            } catch (error) {

                console.warn(
                    "Unable to stop recorder during page unload:",
                    error
                );
            }
        }


        cleanupMicrophoneStream();

        stopRecordingTimer();

        stopResponseAudio();

    }
);
// ============================================================
// PART 3 - OCR / IMAGE QUESTION
// ============================================================


// ============================================================
// OCR API
// ============================================================

API.OCR =
    "/api/ocr/";


// ============================================================
// OCR DOM ELEMENTS
// ============================================================
//
// Different versions of the HTML may use cameraButton,
// imageButton or attachmentButton.
//
// We safely support all of them.
// ============================================================

const cameraButton =
    document.getElementById("cameraButton") ||
    document.getElementById("imageButton") ||
    document.getElementById("attachmentButton");


let imageInput =
    document.getElementById("imageInput");


// ============================================================
// OCR STATE
// ============================================================

let isProcessingOCR =
    false;


// ============================================================
// CREATE IMAGE INPUT IF HTML DOES NOT HAVE ONE
// ============================================================

function ensureImageInput() {

    if (imageInput) {

        return imageInput;
    }


    imageInput =
        document.createElement(
            "input"
        );


    imageInput.type =
        "file";


    imageInput.id =
        "imageInput";


    imageInput.accept =
        "image/*";


    // On mobile this allows the browser/device to offer
    // camera capture where supported.

    imageInput.setAttribute(
        "capture",
        "environment"
    );


    imageInput.hidden =
        true;


    document.body.appendChild(
        imageInput
    );


    bindImageInput();


    return imageInput;
}


// ============================================================
// CAMERA BUTTON
// ============================================================

if (cameraButton) {

    cameraButton.addEventListener(
        "click",
        () => {

            if (isProcessingOCR) {

                return;
            }


            const input =
                ensureImageInput();


            // Reset so selecting the same image twice
            // still triggers change.

            input.value =
                "";


            input.click();

        }
    );
}


// ============================================================
// BIND IMAGE INPUT
// ============================================================

function bindImageInput() {

    if (!imageInput) {
        return;
    }


    if (
        imageInput.dataset
            .farmerOcrBound ===
        "true"
    ) {

        return;
    }


    imageInput.dataset
        .farmerOcrBound =
        "true";


    imageInput.addEventListener(
        "change",
        async () => {

            const file =
                imageInput.files?.[0];


            if (!file) {

                return;
            }


            await processOCRImage(
                file
            );

        }
    );
}


// Bind existing HTML input if available.

bindImageInput();


// ============================================================
// VALIDATE IMAGE
// ============================================================

function validateOCRImage(
    file
) {

    if (!file) {

        return {
            valid: false,
            message:
                "Please select an image.",
        };
    }


    // ========================================================
    // TYPE
    // ========================================================

    if (
        file.type &&
        !file.type.startsWith(
            "image/"
        )
    ) {

        return {
            valid: false,
            message:
                "Please select a valid image file.",
        };
    }


    // ========================================================
    // SIZE
    // ========================================================
    //
    // Django development configuration currently allows
    // requests up to 10 MB.
    // ========================================================

    const maxSize =
        10 *
        1024 *
        1024;


    if (
        file.size >
        maxSize
    ) {

        return {
            valid: false,
            message:
                "Image is too large. Please select an image smaller than 10 MB.",
        };
    }


    if (
        file.size <= 0
    ) {

        return {
            valid: false,
            message:
                "The selected image is empty.",
        };
    }


    return {
        valid: true,
    };
}


// ============================================================
// PROCESS OCR IMAGE
// ============================================================

async function processOCRImage(
    file
) {

    if (isProcessingOCR) {

        return;
    }


    const validation =
        validateOCRImage(
            file
        );


    if (!validation.valid) {

        appendSystemMessage(
            validation.message
        );

        return;
    }


    isProcessingOCR =
        true;


    setOCRProcessingUI(
        true
    );


    hideWelcomePanel();


    // ========================================================
    // SHOW IMAGE PREVIEW MESSAGE
    // ========================================================

    appendImagePreviewMessage(
        file
    );


    showTypingIndicator();


    try {

        // ====================================================
        // FORM DATA
        // ====================================================

        const formData =
            new FormData();


        formData.append(
            "image",
            file
        );


        const selectedLanguage =
            languageSelect
                ? languageSelect.value.trim()
                : "";


        if (selectedLanguage) {

            formData.append(
                "language",
                selectedLanguage
            );
        }


        // ====================================================
        // OCR API REQUEST
        // ====================================================

        const response =
            await authenticatedFetch(
                API.OCR,
                {
                    method: "POST",

                    body: formData,
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                "The OCR server returned an invalid response."
            );
        }


        // ====================================================
        // HTTP FAILURE
        // ====================================================

        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        // ====================================================
        // APPLICATION FAILURE
        // ====================================================

        if (
            result?.success ===
            false
        ) {

            throw new Error(
                result?.message ||
                "No readable text could be extracted from the image."
            );
        }


        // ====================================================
        // EXTRACT OCR TEXT
        // ====================================================

        const extractedText =
            String(
                result?.text ||
                result?.extracted_text ||
                ""
            ).trim();


        if (!extractedText) {

            throw new Error(
                "No readable text could be extracted from the image."
            );
        }


        // ====================================================
        // SHOW OCR RESULT
        // ====================================================

        appendOCRResultMessage(
            {
                text:
                    extractedText,

                confidence:
                    result?.confidence,

                language:
                    result?.language,

                lines:
                    result?.lines,
            }
        );


        // ====================================================
        // PUT TEXT IN COMPOSER
        // ====================================================
        //
        // OCR output is user-provided extracted text.
        // We do NOT silently treat it as trusted KB evidence.
        //
        // The farmer can edit it before sending.
        // ====================================================

        if (messageInput) {

            messageInput.value =
                extractedText;


            resizeTextarea();


            messageInput.focus();
        }


        appendSystemMessage(
            "Text extracted from the image. You can edit it and press Send to ask Farmer Voice AI."
        );


    } catch (error) {

        console.error(
            "OCR processing failed:",
            error
        );


        appendSystemMessage(
            error?.message ||
            "Unable to read the image. Please try another image."
        );


    } finally {

        hideTypingIndicator();


        isProcessingOCR =
            false;


        setOCRProcessingUI(
            false
        );


        if (imageInput) {

            imageInput.value =
                "";
        }
    }
}


// ============================================================
// IMAGE PREVIEW MESSAGE
// ============================================================

function appendImagePreviewMessage(
    file
) {

    if (
        !messagesList ||
        !file
    ) {

        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "message-row user-message-row";


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message-bubble user-message image-message";


    // ========================================================
    // LABEL
    // ========================================================

    const label =
        document.createElement(
            "div"
        );


    label.className =
        "image-message-label";


    label.textContent =
        "📷 Image uploaded";


    bubble.appendChild(
        label
    );


    // ========================================================
    // PREVIEW
    // ========================================================

    const image =
        document.createElement(
            "img"
        );


    image.className =
        "ocr-image-preview";


    image.alt =
        "Uploaded agricultural image";


    const objectUrl =
        URL.createObjectURL(
            file
        );


    image.src =
        objectUrl;


    image.addEventListener(
        "load",
        () => {

            URL.revokeObjectURL(
                objectUrl
            );

        },
        {
            once: true,
        }
    );


    image.addEventListener(
        "error",
        () => {

            URL.revokeObjectURL(
                objectUrl
            );

        },
        {
            once: true,
        }
    );


    bubble.appendChild(
        image
    );


    // ========================================================
    // FILE NAME
    // ========================================================

    const fileName =
        document.createElement(
            "div"
        );


    fileName.className =
        "image-file-name";


    fileName.textContent =
        file.name ||
        "Uploaded image";


    bubble.appendChild(
        fileName
    );


    wrapper.appendChild(
        bubble
    );


    messagesList.appendChild(
        wrapper
    );


    scrollMessagesToBottom();
}


// ============================================================
// OCR RESULT MESSAGE
// ============================================================

function appendOCRResultMessage(
    result
) {

    if (!messagesList) {

        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "message-row assistant-message-row";


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message-bubble assistant-message ocr-result-message";


    // ========================================================
    // HEADING
    // ========================================================

    const heading =
        document.createElement(
            "div"
        );


    heading.className =
        "ocr-result-heading";


    heading.textContent =
        "📄 Extracted Text";


    bubble.appendChild(
        heading
    );


    // ========================================================
    // TEXT
    // ========================================================

    const text =
        document.createElement(
            "div"
        );


    text.className =
        "ocr-extracted-text";


    text.textContent =
        result?.text ||
        "";


    bubble.appendChild(
        text
    );


    // ========================================================
    // META
    // ========================================================

    const metadata =
        document.createElement(
            "div"
        );


    metadata.className =
        "message-metadata";


    if (
        result?.confidence !==
            undefined &&
        result?.confidence !==
            null
    ) {

        const confidence =
            document.createElement(
                "span"
            );


        confidence.className =
            "confidence-badge";


        confidence.textContent =
            `OCR confidence: ${formatOCRConfidence(
                result.confidence
            )}`;


        metadata.appendChild(
            confidence
        );
    }


    if (result?.language) {

        const language =
            document.createElement(
                "span"
            );


        language.className =
            "language-badge";


        language.textContent =
            `Language: ${result.language}`;


        metadata.appendChild(
            language
        );
    }


    if (
        metadata.children.length >
        0
    ) {

        bubble.appendChild(
            metadata
        );
    }


    wrapper.appendChild(
        bubble
    );


    messagesList.appendChild(
        wrapper
    );


    scrollMessagesToBottom();
}


// ============================================================
// FORMAT OCR CONFIDENCE
// ============================================================

function formatOCRConfidence(
    confidence
) {

    const value =
        Number(
            confidence
        );


    if (
        Number.isNaN(value)
    ) {

        return String(
            confidence
        );
    }


    // If OCR returns 0-1:
    if (
        value >= 0 &&
        value <= 1
    ) {

        return (
            `${Math.round(
                value * 100
            )}%`
        );
    }


    // If OCR already returns 0-100:
    return (
        `${Math.round(value)}%`
    );
}


// ============================================================
// OCR BUTTON STATE
// ============================================================

function setOCRProcessingUI(
    processing
) {

    if (!cameraButton) {

        return;
    }


    cameraButton.disabled =
        processing;


    cameraButton.classList.toggle(
        "processing",
        processing
    );


    cameraButton.setAttribute(
        "aria-busy",
        processing
            ? "true"
            : "false"
    );


    cameraButton.title =
        processing
            ? "Reading image..."
            : "Upload image";
}
// ============================================================
// PART 4 - FEEDBACK + NOTIFICATIONS
// ============================================================


// ============================================================
// API ENDPOINTS
// ============================================================

API.FEEDBACK =
    "/api/feedback/";

API.NOTIFICATIONS =
    "/api/notifications/";

API.NOTIFICATION_COUNT =
    "/api/notifications/unread-count/";

API.NOTIFICATION_READ_ALL =
    "/api/notifications/read-all/";


// ============================================================
// NOTIFICATION DOM ELEMENTS
// ============================================================

const notificationButton =
    document.getElementById(
        "notificationButton"
    );

const notificationBadge =
    document.getElementById(
        "notificationBadge"
    );

const notificationPanel =
    document.getElementById(
        "notificationPanel"
    );

const notificationList =
    document.getElementById(
        "notificationList"
    );

const markAllReadButton =
    document.getElementById(
        "markAllReadButton"
    );


// ============================================================
// NOTIFICATION STATE
// ============================================================

let isNotificationPanelOpen =
    false;

let isLoadingNotifications =
    false;


// ============================================================
// FEEDBACK EVENT DELEGATION
// ============================================================
//
// Feedback buttons are dynamically created when an AI
// response is rendered, so event delegation is used.
// ============================================================

if (messagesList) {

    messagesList.addEventListener(
        "click",
        async (event) => {

            const button =
                event.target.closest(
                    ".feedback-button"
                );


            if (!button) {
                return;
            }


            const container =
                button.closest(
                    ".feedback-controls"
                );


            if (!container) {
                return;
            }


            const messageId =
                container.dataset
                    .messageId;


            const rating =
                button.dataset
                    .rating;


            if (
                !messageId ||
                !rating
            ) {

                console.warn(
                    "Feedback button is missing message information."
                );

                return;
            }


            await submitFeedback(
                {
                    messageId,
                    rating,
                    button,
                    container,
                }
            );

        }
    );
}


// ============================================================
// SUBMIT FEEDBACK
// ============================================================

async function submitFeedback({
    messageId,
    rating,
    button,
    container,
}) {

    if (
        !messageId ||
        !rating ||
        !button
    ) {

        return;
    }


    // Prevent multiple requests while current feedback
    // request is running.

    const buttons =
        container
            ? container.querySelectorAll(
                ".feedback-button"
            )
            : [];


    buttons.forEach(
        (item) => {

            item.disabled =
                true;
        }
    );


    button.classList.add(
        "processing"
    );


    try {

        const response =
            await authenticatedFetch(
                API.FEEDBACK,
                {
                    method: "POST",

                    body: JSON.stringify({
                        message:
                            Number(
                                messageId
                            ),

                        rating:
                            rating,
                    }),
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                "Feedback server returned an invalid response."
            );
        }


        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        // ====================================================
        // UPDATE FEEDBACK UI
        // ====================================================

        buttons.forEach(
            (item) => {

                item.classList.remove(
                    "selected"
                );

                item.classList.remove(
                    "active"
                );
            }
        );


        button.classList.add(
            "selected"
        );


        button.classList.add(
            "active"
        );


        button.title =
            rating === "HELPFUL"
                ? "Marked helpful"
                : "Marked not helpful";


        showTemporaryStatus(
            rating === "HELPFUL"
                ? "Thanks for your feedback 👍"
                : "Thanks. Your feedback helps improve the assistant."
        );


    } catch (error) {

        console.error(
            "Feedback request failed:",
            error
        );


        appendSystemMessage(
            error?.message ||
            "Unable to save feedback."
        );


    } finally {

        button.classList.remove(
            "processing"
        );


        buttons.forEach(
            (item) => {

                item.disabled =
                    false;
            }
        );
    }
}


// ============================================================
// NOTIFICATION BUTTON
// ============================================================

if (notificationButton) {

    notificationButton.addEventListener(
        "click",
        async (event) => {

            event.stopPropagation();


            if (
                isNotificationPanelOpen
            ) {

                closeNotificationPanel();

                return;
            }


            await openNotificationPanel();

        }
    );
}


// ============================================================
// OPEN NOTIFICATION PANEL
// ============================================================

async function openNotificationPanel() {

    if (!notificationPanel) {

        // If the current HTML has no dropdown panel,
        // notification count still works without crashing.

        console.warn(
            "notificationPanel element was not found."
        );

        return;
    }


    isNotificationPanelOpen =
        true;


    notificationPanel.hidden =
        false;


    notificationPanel.style.display =
        "";


    notificationPanel.classList.add(
        "open"
    );


    if (notificationButton) {

        notificationButton.setAttribute(
            "aria-expanded",
            "true"
        );
    }


    await loadNotifications();
}


// ============================================================
// CLOSE NOTIFICATION PANEL
// ============================================================

function closeNotificationPanel() {

    if (!notificationPanel) {
        return;
    }


    isNotificationPanelOpen =
        false;


    notificationPanel.classList.remove(
        "open"
    );


    notificationPanel.hidden =
        true;


    notificationPanel.style.display =
        "none";


    if (notificationButton) {

        notificationButton.setAttribute(
            "aria-expanded",
            "false"
        );
    }
}


// ============================================================
// LOAD NOTIFICATIONS
// ============================================================

async function loadNotifications() {

    if (isLoadingNotifications) {
        return;
    }


    isLoadingNotifications =
        true;


    renderNotificationLoading();


    try {

        const response =
            await authenticatedFetch(
                API.NOTIFICATIONS,
                {
                    method: "GET",
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            throw new Error(
                "Notification server returned an invalid response."
            );
        }


        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        // Support:
        //
        // [...]
        //
        // or
        //
        // { data: [...] }
        //
        // or
        //
        // { results: [...] }

        let notifications = [];


        if (
            Array.isArray(result)
        ) {

            notifications =
                result;

        } else if (
            Array.isArray(
                result?.data
            )
        ) {

            notifications =
                result.data;

        } else if (
            Array.isArray(
                result?.results
            )
        ) {

            notifications =
                result.results;

        } else if (
            Array.isArray(
                result?.data?.results
            )
        ) {

            notifications =
                result.data.results;
        }


        renderNotifications(
            notifications
        );


        await loadUnreadNotificationCount();


    } catch (error) {

        console.error(
            "Unable to load notifications:",
            error
        );


        renderNotificationError(
            error?.message ||
            "Unable to load notifications."
        );


    } finally {

        isLoadingNotifications =
            false;
    }
}


// ============================================================
// LOAD UNREAD COUNT
// ============================================================

async function loadUnreadNotificationCount() {

    if (!notificationBadge) {
        return;
    }


    try {

        const response =
            await authenticatedFetch(
                API.NOTIFICATION_COUNT,
                {
                    method: "GET",
                }
            );


        if (!response.ok) {

            return;
        }


        const result =
            await response.json();


        const count =
            Number(
                result?.unread_count ??
                result?.count ??
                result?.data?.unread_count ??
                result?.data?.count ??
                0
            );


        updateNotificationBadge(
            Number.isFinite(count)
                ? count
                : 0
        );


    } catch (error) {

        console.warn(
            "Unable to load unread notification count:",
            error
        );
    }
}


// ============================================================
// UPDATE NOTIFICATION BADGE
// ============================================================

function updateNotificationBadge(
    count
) {

    if (!notificationBadge) {
        return;
    }


    const safeCount =
        Math.max(
            0,
            Number(count) || 0
        );


    notificationBadge.textContent =
        safeCount > 99
            ? "99+"
            : String(safeCount);


    notificationBadge.hidden =
        safeCount <= 0;


    notificationBadge.style.display =
        safeCount > 0
            ? ""
            : "none";


    if (notificationButton) {

        notificationButton.setAttribute(
            "aria-label",
            safeCount > 0
                ? `${safeCount} unread notifications`
                : "Notifications"
        );
    }
}


// ============================================================
// RENDER NOTIFICATIONS
// ============================================================

function renderNotifications(
    notifications
) {

    if (!notificationList) {
        return;
    }


    notificationList.innerHTML =
        "";


    if (
        !Array.isArray(
            notifications
        ) ||
        notifications.length === 0
    ) {

        const empty =
            document.createElement(
                "div"
            );


        empty.className =
            "notification-empty";


        empty.textContent =
            "No notifications yet.";


        notificationList.appendChild(
            empty
        );


        return;
    }


    notifications.forEach(
        (notification) => {

            const item =
                createNotificationElement(
                    notification
                );


            notificationList.appendChild(
                item
            );

        }
    );
}


// ============================================================
// CREATE NOTIFICATION ELEMENT
// ============================================================

function createNotificationElement(
    notification
) {

    const item =
        document.createElement(
            "button"
        );


    item.type =
        "button";


    item.className =
        "notification-item";


    const notificationId =
        notification?.id;


    if (
        notificationId !==
        undefined &&
        notificationId !==
        null
    ) {

        item.dataset.notificationId =
            String(
                notificationId
            );
    }


    const isRead =
        Boolean(
            notification?.is_read ??
            notification?.read ??
            false
        );


    if (!isRead) {

        item.classList.add(
            "unread"
        );
    }


    // ========================================================
    // TITLE
    // ========================================================

    const title =
        document.createElement(
            "div"
        );


    title.className =
        "notification-title";


    title.textContent =
        notification?.title ||
        "Farmer Voice AI";


    item.appendChild(
        title
    );


    // ========================================================
    // MESSAGE
    // ========================================================

    const message =
        document.createElement(
            "div"
        );


    message.className =
        "notification-message";


    message.textContent =
        notification?.message ||
        notification?.body ||
        notification?.text ||
        "";


    item.appendChild(
        message
    );


    // ========================================================
    // DATE
    // ========================================================

    const createdAt =
        notification?.created_at ||
        notification?.created ||
        notification?.timestamp;


    if (createdAt) {

        const time =
            document.createElement(
                "div"
            );


        time.className =
            "notification-time";


        time.textContent =
            formatNotificationTime(
                createdAt
            );


        item.appendChild(
            time
        );
    }


    // ========================================================
    // MARK READ ON CLICK
    // ========================================================

    item.addEventListener(
        "click",
        async () => {

            if (
                !notificationId ||
                isRead
            ) {

                return;
            }


            await markNotificationRead(
                notificationId,
                item
            );
        }
    );


    return item;
}


// ============================================================
// MARK ONE NOTIFICATION READ
// ============================================================

async function markNotificationRead(
    notificationId,
    element = null
) {

    if (!notificationId) {
        return;
    }


    try {

        const endpoint =
            `/api/notifications/${encodeURIComponent(
                notificationId
            )}/read/`;


        const response =
            await authenticatedFetch(
                endpoint,
                {
                    method: "POST",
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            result = null;
        }


        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        if (element) {

            element.classList.remove(
                "unread"
            );
        }


        await loadUnreadNotificationCount();


    } catch (error) {

        console.error(
            "Unable to mark notification as read:",
            error
        );
    }
}


// ============================================================
// MARK ALL READ BUTTON
// ============================================================

if (markAllReadButton) {

    markAllReadButton.addEventListener(
        "click",
        async (event) => {

            event.stopPropagation();

            await markAllNotificationsRead();

        }
    );
}


// ============================================================
// MARK ALL NOTIFICATIONS READ
// ============================================================

async function markAllNotificationsRead() {

    if (!markAllReadButton) {
        return;
    }


    markAllReadButton.disabled =
        true;


    try {

        const response =
            await authenticatedFetch(
                API.NOTIFICATION_READ_ALL,
                {
                    method: "POST",
                }
            );


        let result = null;


        try {

            result =
                await response.json();

        } catch (error) {

            result = null;
        }


        if (!response.ok) {

            throw new Error(
                extractErrorMessage(
                    result
                )
            );
        }


        if (notificationList) {

            notificationList
                .querySelectorAll(
                    ".notification-item.unread"
                )
                .forEach(
                    (item) => {

                        item.classList.remove(
                            "unread"
                        );

                    }
                );
        }


        updateNotificationBadge(
            0
        );


        showTemporaryStatus(
            "All notifications marked as read."
        );


    } catch (error) {

        console.error(
            "Unable to mark all notifications as read:",
            error
        );


        showTemporaryStatus(
            error?.message ||
            "Unable to update notifications."
        );


    } finally {

        markAllReadButton.disabled =
            false;
    }
}


// ============================================================
// NOTIFICATION LOADING
// ============================================================

function renderNotificationLoading() {

    if (!notificationList) {
        return;
    }


    notificationList.innerHTML =
        "";


    const loading =
        document.createElement(
            "div"
        );


    loading.className =
        "notification-loading";


    loading.textContent =
        "Loading notifications...";


    notificationList.appendChild(
        loading
    );
}


// ============================================================
// NOTIFICATION ERROR
// ============================================================

function renderNotificationError(
    message
) {

    if (!notificationList) {
        return;
    }


    notificationList.innerHTML =
        "";


    const error =
        document.createElement(
            "div"
        );


    error.className =
        "notification-error";


    error.textContent =
        message;


    notificationList.appendChild(
        error
    );
}


// ============================================================
// FORMAT NOTIFICATION TIME
// ============================================================

function formatNotificationTime(
    value
) {

    try {

        const date =
            new Date(
                value
            );


        if (
            Number.isNaN(
                date.getTime()
            )
        ) {

            return "";
        }


        return date.toLocaleString(
            undefined,
            {
                dateStyle:
                    "medium",

                timeStyle:
                    "short",
            }
        );


    } catch (error) {

        return "";
    }
}


// ============================================================
// CLICK OUTSIDE NOTIFICATION PANEL
// ============================================================

document.addEventListener(
    "click",
    (event) => {

        if (
            !isNotificationPanelOpen ||
            !notificationPanel
        ) {

            return;
        }


        const clickedInsidePanel =
            notificationPanel.contains(
                event.target
            );


        const clickedNotificationButton =
            notificationButton
                ? notificationButton.contains(
                    event.target
                )
                : false;


        if (
            !clickedInsidePanel &&
            !clickedNotificationButton
        ) {

            closeNotificationPanel();
        }

    }
);


// ============================================================
// ESCAPE CLOSES NOTIFICATION PANEL
// ============================================================

document.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Escape" &&
            isNotificationPanelOpen
        ) {

            closeNotificationPanel();
        }

    }
);


// ============================================================
// TEMPORARY STATUS MESSAGE
// ============================================================

let temporaryStatusTimer =
    null;


function showTemporaryStatus(
    message
) {

    if (!message) {
        return;
    }


    let statusElement =
        document.getElementById(
            "temporaryStatusMessage"
        );


    // If HTML does not already contain one,
    // create a lightweight status element.

    if (!statusElement) {

        statusElement =
            document.createElement(
                "div"
            );


        statusElement.id =
            "temporaryStatusMessage";


        statusElement.className =
            "temporary-status-message";


        statusElement.setAttribute(
            "role",
            "status"
        );


        statusElement.setAttribute(
            "aria-live",
            "polite"
        );


        document.body.appendChild(
            statusElement
        );
    }


    statusElement.textContent =
        message;


    statusElement.hidden =
        false;


    statusElement.classList.add(
        "show"
    );


    if (temporaryStatusTimer) {

        window.clearTimeout(
            temporaryStatusTimer
        );
    }


    temporaryStatusTimer =
        window.setTimeout(
            () => {

                statusElement.classList.remove(
                    "show"
                );


                statusElement.hidden =
                    true;


                temporaryStatusTimer =
                    null;

            },
            3000
        );
}


// ============================================================
// INITIAL NOTIFICATION COUNT
// ============================================================
//
// Actual initialization of the whole application is done
// in the final part. This function will be called there.
// ============================================================

async function initializeNotifications() {

    if (!notificationButton) {

        return;
    }


    await loadUnreadNotificationCount();
}

// ============================================================
// PART 5 - UI NAVIGATION + NEW CHAT + LOGOUT
// ============================================================


// ============================================================
// NEW CHAT
// ============================================================

if (newChatButton) {

    newChatButton.addEventListener(
        "click",
        () => {

            startNewChat();

        }
    );
}


function startNewChat() {

    // ========================================================
    // STOP ACTIVE VOICE RECORDING
    // ========================================================

    if (
        typeof isRecording !== "undefined" &&
        isRecording
    ) {

        stopVoiceRecording();
    }


    // ========================================================
    // STOP PLAYING AUDIO
    // ========================================================

    stopResponseAudio();


    // ========================================================
    // RESET CONVERSATION ID
    // ========================================================

    currentConversationId =
        null;


    // ========================================================
    // CLEAR MESSAGES
    // ========================================================

    if (messagesList) {

        messagesList.innerHTML =
            "";
    }


    // ========================================================
    // RESET INPUT
    // ========================================================

    if (messageInput) {

        messageInput.value =
            "";

        resizeTextarea();
    }


    // ========================================================
    // RESET IMAGE INPUT
    // ========================================================

    if (
        typeof imageInput !==
            "undefined" &&
        imageInput
    ) {

        imageInput.value =
            "";
    }


    // ========================================================
    // RESET INDICATORS
    // ========================================================

    hideTypingIndicator();


    if (
        typeof setRecordingUI ===
        "function"
    ) {

        setRecordingUI(
            false
        );
    }


    // ========================================================
    // SHOW WELCOME SCREEN
    // ========================================================

    showWelcomePanel();


    // ========================================================
    // CLOSE MOBILE SIDEBAR
    // ========================================================

    closeSidebar();


    // ========================================================
    // CLOSE NOTIFICATIONS
    // ========================================================

    if (
        typeof closeNotificationPanel ===
        "function"
    ) {

        closeNotificationPanel();
    }


    // ========================================================
    // FOCUS INPUT
    // ========================================================

    if (messageInput) {

        window.setTimeout(
            () => {

                messageInput.focus();

            },
            100
        );
    }


    if (
        typeof showTemporaryStatus ===
        "function"
    ) {

        showTemporaryStatus(
            "New chat started."
        );
    }
}


// ============================================================
// MOBILE SIDEBAR
// ============================================================

if (
    mobileMenuButton &&
    sidebar
) {

    mobileMenuButton.addEventListener(
        "click",
        (event) => {

            event.stopPropagation();


            const isOpen =
                sidebar.classList.contains(
                    "open"
                );


            if (isOpen) {

                closeSidebar();

            } else {

                openSidebar();
            }

        }
    );
}


// ============================================================
// OPEN SIDEBAR
// ============================================================

function openSidebar() {

    if (!sidebar) {
        return;
    }


    sidebar.classList.add(
        "open"
    );


    sidebar.classList.add(
        "mobile-open"
    );


    if (mobileMenuButton) {

        mobileMenuButton.setAttribute(
            "aria-expanded",
            "true"
        );
    }
}


// ============================================================
// CLOSE SIDEBAR
// ============================================================

function closeSidebar() {

    if (!sidebar) {
        return;
    }


    sidebar.classList.remove(
        "open"
    );


    sidebar.classList.remove(
        "mobile-open"
    );


    if (mobileMenuButton) {

        mobileMenuButton.setAttribute(
            "aria-expanded",
            "false"
        );
    }
}


// ============================================================
// CLICK OUTSIDE SIDEBAR
// ============================================================

document.addEventListener(
    "click",
    (event) => {

        if (
            !sidebar ||
            !mobileMenuButton
        ) {

            return;
        }


        const mobileView =
            window.matchMedia(
                "(max-width: 900px)"
            ).matches;


        if (!mobileView) {

            return;
        }


        const isOpen =
            sidebar.classList.contains(
                "open"
            ) ||
            sidebar.classList.contains(
                "mobile-open"
            );


        if (!isOpen) {

            return;
        }


        const clickedInsideSidebar =
            sidebar.contains(
                event.target
            );


        const clickedMenuButton =
            mobileMenuButton.contains(
                event.target
            );


        if (
            !clickedInsideSidebar &&
            !clickedMenuButton
        ) {

            closeSidebar();
        }

    }
);


// ============================================================
// ESCAPE KEY
// ============================================================

document.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key !==
            "Escape"
        ) {

            return;
        }


        closeSidebar();


        if (
            typeof closeNotificationPanel ===
            "function"
        ) {

            closeNotificationPanel();
        }


        if (
            typeof isRecording !== "undefined" &&
            isRecording
        ) {

            stopVoiceRecording();
        }

    }
);


// ============================================================
// LOGOUT BUTTON
// ============================================================

if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        () => {

            logoutFarmer();

        }
    );
}


// ============================================================
// LOGOUT
// ============================================================

function logoutFarmer() {

    // ========================================================
    // STOP MICROPHONE
    // ========================================================

    if (
        typeof isRecording !== "undefined" &&
        isRecording
    ) {

        try {

            stopVoiceRecording();

        } catch (error) {

            console.warn(
                "Unable to stop recording during logout:",
                error
            );
        }
    }


    // ========================================================
    // CLEAN MICROPHONE STREAM
    // ========================================================

    if (
        typeof cleanupMicrophoneStream ===
        "function"
    ) {

        cleanupMicrophoneStream();
    }


    // ========================================================
    // STOP TTS
    // ========================================================

    if (
        typeof stopResponseAudio ===
        "function"
    ) {

        stopResponseAudio();
    }


    // ========================================================
    // CLEAR AUTHENTICATION
    // ========================================================

    clearAuthentication();


    // ========================================================
    // REDIRECT
    // ========================================================

    window.location.replace(
        "/"
    );
}


// ============================================================
// LANGUAGE SELECT
// ============================================================

if (languageSelect) {

    // Restore user's last selection.

    const storedLanguage =
        localStorage.getItem(
            "farmer_language"
        );


    if (storedLanguage) {

        const optionExists =
            Array.from(
                languageSelect.options
            ).some(
                (option) =>
                    option.value ===
                    storedLanguage
            );


        if (optionExists) {

            languageSelect.value =
                storedLanguage;
        }
    }


    languageSelect.addEventListener(
        "change",
        () => {

            const language =
                languageSelect.value
                    .trim();


            if (language) {

                localStorage.setItem(
                    "farmer_language",
                    language
                );

            } else {

                localStorage.removeItem(
                    "farmer_language"
                );
            }

        }
    );
}


// ============================================================
// PAGE VISIBILITY
// ============================================================
//
// If user returns after keeping the page open for a long time,
// reload notification count. JWT refresh remains handled by
// authenticatedFetch.
// ============================================================

document.addEventListener(
    "visibilitychange",
    () => {

        if (
            document.visibilityState !==
            "visible"
        ) {

            return;
        }


        if (
            typeof loadUnreadNotificationCount ===
            "function"
        ) {

            loadUnreadNotificationCount()
                .catch(
                    (error) => {

                        console.warn(
                            "Notification refresh failed:",
                            error
                        );

                    }
                );
        }

    }
);


// ============================================================
// WINDOW RESIZE
// ============================================================

window.addEventListener(
    "resize",
    () => {

        const desktopView =
            window.matchMedia(
                "(min-width: 901px)"
            ).matches;


        if (desktopView) {

            closeSidebar();
        }

    }
);


// ============================================================
// AUTH CHECK
// ============================================================

function hasAuthentication() {

    return Boolean(
        getAccessToken()
    );
}


// ============================================================
// INITIAL UI STATE
// ============================================================

function initializeUIState() {

    // ========================================================
    // TYPING
    // ========================================================

    hideTypingIndicator();


    // ========================================================
    // RECORDING
    // ========================================================

    if (
        typeof setRecordingUI ===
        "function"
    ) {

        setRecordingUI(
            false
        );
    }


    // ========================================================
    // PROCESSING
    // ========================================================

    if (
        typeof setVoiceProcessingUI ===
        "function"
    ) {

        setVoiceProcessingUI(
            false
        );
    }


    if (
        typeof setOCRProcessingUI ===
        "function"
    ) {

        setOCRProcessingUI(
            false
        );
    }


    // ========================================================
    // NOTIFICATION PANEL
    // ========================================================

    if (
        typeof closeNotificationPanel ===
        "function"
    ) {

        closeNotificationPanel();
    }


    // ========================================================
    // SIDEBAR
    // ========================================================

    closeSidebar();


    // ========================================================
    // INPUT
    // ========================================================

    resizeTextarea();
}


// ============================================================
// APPLICATION INITIALIZATION
// ============================================================

let applicationInitialized =
    false;


async function initializeFarmerVoiceAI() {

    // Prevent accidental double initialization.

    if (applicationInitialized) {

        return;
    }


    applicationInitialized =
        true;


    console.log(
        "Farmer Voice AI: initializing..."
    );


    // ========================================================
    // 1. AUTH CHECK
    // ========================================================

    if (!hasAuthentication()) {

        console.warn(
            "Farmer Voice AI: access token missing."
        );


        redirectToLogin();

        return;
    }


    // ========================================================
    // 2. INITIAL UI
    // ========================================================

    initializeUIState();


    // ========================================================
    // 3. LOAD PROFILE
    // ========================================================

    try {

        await loadUserProfile();

    } catch (error) {

        console.error(
            "Profile initialization failed:",
            error
        );
    }


    // ========================================================
    // 4. NOTIFICATIONS
    // ========================================================

    try {

        if (
            typeof initializeNotifications ===
            "function"
        ) {

            await initializeNotifications();
        }

    } catch (error) {

        // Notification failure must NEVER stop chat.

        console.warn(
            "Notification initialization failed:",
            error
        );
    }


    // ========================================================
    // 5. READY
    // ========================================================

    console.log(
        "Farmer Voice AI: ready."
    );


    if (messageInput) {

        messageInput.focus();
    }
}


// ============================================================
// START APPLICATION
// ============================================================
//
// chat.js is loaded at the bottom of chat.html in the normal
// setup, but this also remains safe if script loading changes
// later.
// ============================================================

if (
    document.readyState ===
    "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        () => {

            initializeFarmerVoiceAI()
                .catch(
                    (error) => {

                        console.error(
                            "Farmer Voice AI initialization error:",
                            error
                        );

                    }
                );

        },
        {
            once: true,
        }
    );

} else {

    initializeFarmerVoiceAI()
        .catch(
            (error) => {

                console.error(
                    "Farmer Voice AI initialization error:",
                    error
                );

            }
        );
}
// ============================================================
// PART 6 - FINAL SAFETY + RUNTIME ERROR HANDLING
// ============================================================


// ============================================================
// SAFE ONLINE / OFFLINE STATUS
// ============================================================

window.addEventListener(
    "offline",
    () => {

        if (
            typeof showTemporaryStatus ===
            "function"
        ) {

            showTemporaryStatus(
                "Internet connection lost."
            );
        }

    }
);


window.addEventListener(
    "online",
    () => {

        if (
            typeof showTemporaryStatus ===
            "function"
        ) {

            showTemporaryStatus(
                "Internet connection restored."
            );
        }

    }
);


// ============================================================
// GLOBAL JAVASCRIPT ERROR LOGGING
// ============================================================
//
// Important:
// This does NOT hide errors.
// It prints useful information in DevTools so debugging is
// easier if any unexpected frontend problem occurs.
// ============================================================

window.addEventListener(
    "error",
    (event) => {

        console.error(
            "Farmer Voice AI frontend error:",
            {
                message:
                    event.message,

                filename:
                    event.filename,

                line:
                    event.lineno,

                column:
                    event.colno,

                error:
                    event.error,
            }
        );

    }
);


// ============================================================
// UNHANDLED PROMISE ERRORS
// ============================================================

window.addEventListener(
    "unhandledrejection",
    (event) => {

        console.error(
            "Farmer Voice AI unhandled promise rejection:",
            event.reason
        );

    }
);


// ============================================================
// SAFE MESSAGE INPUT PASTE
// ============================================================

if (messageInput) {

    messageInput.addEventListener(
        "paste",
        () => {

            window.setTimeout(
                resizeTextarea,
                0
            );

        }
    );
}


// ============================================================
// PREVENT EMPTY FORM SUBMISSION
// ============================================================
//
// If the composer happens to be inside a <form>, prevent the
// browser from refreshing the page.
// ============================================================

if (messageInput) {

    const composerForm =
        messageInput.closest(
            "form"
        );


    if (composerForm) {

        composerForm.addEventListener(
            "submit",
            (event) => {

                event.preventDefault();

                sendTextMessage();

            }
        );
    }
}


// ============================================================
// SAFE URL NORMALIZER
// ============================================================
//
// TTS backend normally returns an absolute URL because your
// Django VoiceChatView uses request.build_absolute_uri().
//
// This helper also supports relative URLs if that changes later.
// ============================================================

function normalizeMediaUrl(
    url
) {

    if (!url) {

        return "";
    }


    try {

        return new URL(
            String(url),
            window.location.origin
        ).href;

    } catch (error) {

        console.warn(
            "Invalid media URL:",
            url
        );


        return "";
    }
}


// ============================================================
// SAFE AUDIO SOURCE
// ============================================================
//
// Wrap the Part 2 audio player so relative/absolute URLs both
// work without changing the voice API.
// ============================================================

const originalPlayResponseAudio =
    playResponseAudio;


playResponseAudio =
    async function (
        audioUrl
    ) {

        const safeUrl =
            normalizeMediaUrl(
                audioUrl
            );


        if (!safeUrl) {

            console.warn(
                "TTS audio URL was empty or invalid."
            );

            return;
        }


        return originalPlayResponseAudio(
            safeUrl
        );
    };


// ============================================================
// MICROPHONE PERMISSION INFORMATION
// ============================================================

async function checkMicrophoneAvailability() {

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices
            .getUserMedia
    ) {

        if (voiceButton) {

            voiceButton.title =
                "Voice recording is not supported by this browser.";
        }


        return false;
    }


    return true;
}


// ============================================================
// IMAGE / CAMERA AVAILABILITY
// ============================================================

function checkImageUploadAvailability() {

    if (!cameraButton) {

        return false;
    }


    return true;
}


// ============================================================
// FRONTEND FEATURE CHECK
// ============================================================
//
// This reports missing HTML elements in Console but DOES NOT
// crash the application.
//
// Optional elements are allowed to be absent.
// ============================================================

function runFrontendFeatureCheck() {

    const requiredElements = {

        messagesList:
            messagesList,

        messageInput:
            messageInput,

        sendButton:
            sendButton,

    };


    const optionalElements = {

        messagesContainer:
            messagesContainer,

        welcomePanel:
            welcomePanel,

        typingIndicator:
            typingIndicator,

        languageSelect:
            languageSelect,

        newChatButton:
            newChatButton,

        logoutButton:
            logoutButton,

        voiceButton:
            voiceButton,

        cameraButton:
            cameraButton,

        notificationButton:
            notificationButton,

        notificationBadge:
            notificationBadge,

    };


    // ========================================================
    // REQUIRED
    // ========================================================

    Object.entries(
        requiredElements
    ).forEach(
        ([name, element]) => {

            if (!element) {

                console.error(
                    `Farmer Voice AI: required HTML element missing: ${name}`
                );
            }

        }
    );


    // ========================================================
    // OPTIONAL
    // ========================================================

    Object.entries(
        optionalElements
    ).forEach(
        ([name, element]) => {

            if (!element) {

                console.info(
                    `Farmer Voice AI: optional HTML element not present: ${name}`
                );
            }

        }
    );
}


// ============================================================
// SAFE BUTTON TYPE CHECK
// ============================================================
//
// Buttons placed inside forms default to type="submit".
// Setting type=button prevents accidental page refresh.
// ============================================================

[
    sendButton,
    voiceButton,
    cameraButton,
    newChatButton,
    logoutButton,
    mobileMenuButton,
    notificationButton,
    markAllReadButton,
    stopRecordingButton,

]
    .filter(Boolean)
    .forEach(
        (button) => {

            if (
                button.tagName ===
                "BUTTON"
            ) {

                button.type =
                    "button";
            }

        }
    );


// ============================================================
// INITIAL BUTTON ACCESSIBILITY
// ============================================================

if (sendButton) {

    sendButton.setAttribute(
        "aria-label",
        "Send message"
    );
}


if (voiceButton) {

    voiceButton.setAttribute(
        "aria-label",
        "Ask using voice"
    );
}


if (cameraButton) {

    cameraButton.setAttribute(
        "aria-label",
        "Upload image for text extraction"
    );
}


if (newChatButton) {

    newChatButton.setAttribute(
        "aria-label",
        "Start new chat"
    );
}


if (logoutButton) {

    logoutButton.setAttribute(
        "aria-label",
        "Logout"
    );
}


// ============================================================
// FINAL FEATURE VALIDATION
// ============================================================

runFrontendFeatureCheck();

checkMicrophoneAvailability();

checkImageUploadAvailability();


// ============================================================
// FINAL READY LOG
// ============================================================

console.log(
    "Farmer Voice AI frontend script loaded successfully."
);

// ============================================================
// UI ENHANCEMENTS: THEME TOGGLE & QUICK PROMPTS
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    // Theme Toggle
    const themeBtn = document.getElementById("themeToggleBtn");
    const savedTheme = localStorage.getItem("farmer_ui_theme") || "light";
    if (savedTheme === "dark") {
        document.body.setAttribute("data-theme", "dark");
        if (themeBtn) themeBtn.textContent = "☀️";
    }

    themeBtn?.addEventListener("click", () => {
        const isDark = document.body.getAttribute("data-theme") === "dark";
        if (isDark) {
            document.body.removeAttribute("data-theme");
            localStorage.setItem("farmer_ui_theme", "light");
            themeBtn.textContent = "🌙";
        } else {
            document.body.setAttribute("data-theme", "dark");
            localStorage.setItem("farmer_ui_theme", "dark");
            themeBtn.textContent = "☀️";
        }
    });

    // Quick Prompts / Cards Click
    document.querySelectorAll("[data-prompt]").forEach(elem => {
        elem.addEventListener("click", () => {
            const promptText = elem.getAttribute("data-prompt");
            const inputField = document.getElementById("messageInput");
            const form = document.getElementById("chatForm");
            if (inputField && promptText) {
                inputField.value = promptText;
                if (form) form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
            }
        });
    });

    // Mobile Menu Drawer
    const mobileBtn = document.getElementById("mobileMenuButton");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");

    const toggleSidebar = () => {
        sidebar?.classList.toggle("open");
        if (overlay) overlay.style.display = sidebar?.classList.contains("open") ? "block" : "none";
    };

    mobileBtn?.addEventListener("click", toggleSidebar);
    overlay?.addEventListener("click", toggleSidebar);

    // Close Voice Recording Modal
    const closeVoiceBtn = document.getElementById("closeVoiceModal");
    closeVoiceBtn?.addEventListener("click", () => {
        const vModal = document.getElementById("voiceModal");
        if (vModal) {
            vModal.hidden = true;
            vModal.classList.remove("active");
            vModal.style.display = "none";
        }
    });

    // Automatic Chatbot Greeting Upon Login
    setTimeout(() => {
        try {
            const rawUser = localStorage.getItem("farmer_user");
            let userNameStr = "Farmer";
            if (rawUser) {
                const uObj = JSON.parse(rawUser);
                userNameStr = uObj.name || uObj.full_name || uObj.first_name || "Farmer";
            }
            const welcomePan = document.getElementById("welcomePanel");
            if (welcomePan) welcomePan.style.display = "none";

            appendAssistantMessage({
                answer: `Namaste ${userNameStr}! 🌾 Welcome to Farmer Voice AI. How can I assist your farming today? Ask any question by text, voice, or crop image!`,
                isGreeting: true
            });
        } catch (greetErr) {
            console.warn("Greeting render error:", greetErr);
        }
    }, 300);
});

