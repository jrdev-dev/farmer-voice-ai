from django.shortcuts import render


def login_page(request):
    """
    Farmer Voice AI login page.
    """
    return render(
        request,
        "chatbot_ui/login.html",
    )


def chat_page(request):
    """
    Farmer Voice AI main chatbot page.
    """
    return render(
        request,
        "chatbot_ui/chat.html",
    )
