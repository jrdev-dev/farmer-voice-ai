from django.shortcuts import render


def login_page(request):
    """
    Farmer Voice AI login page.
    """
    return render(
        request,
        "chatbot_ui/login.html",
    )


def register_page(request):
    """
    Farmer Voice AI register/signup page.
    """
    return render(
        request,
        "chatbot_ui/signup.html",
    )


def chat_page(request):
    """
    Farmer Voice AI main chat interface.

    Authentication for API requests is handled
    through JWT on the frontend.
    """
    return render(
        request,
        "chatbot_ui/chat.html",
    )
