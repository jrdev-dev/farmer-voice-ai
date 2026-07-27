from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class EndToEndPipelineTestCase(APITestCase):
    """
    End-to-End integration test covering text chat pipeline and user authentication.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="farmer_e2e@example.com",
            password="Password123!",
        )

    def test_text_chat_flow(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/chat/",
            {
                "message": "सोयाबीन की फसल में कौन सी खाद डालें?",
                "language": "hi",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)
        self.assertIn("answer", response.data)
