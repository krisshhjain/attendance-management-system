from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import Notification


User = get_user_model()


class NotificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="password123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="password123",
        )
        self.older = Notification.objects.create(
            user=self.user,
            title="Older",
            message="Older message",
        )
        self.unread = Notification.objects.create(
            user=self.user,
            title="Unread",
            message="Unread message",
        )
        self.other_notification = Notification.objects.create(
            user=self.other_user,
            title="Private",
            message="Private message",
        )
        Notification.objects.filter(pk=self.older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

    def test_authenticated_user_can_list_own_notifications(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("notification-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.unread.id, self.older.id])

    def test_user_cannot_see_another_users_notifications(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("notification-list"))

        self.assertNotIn(self.other_notification.id, [item["id"] for item in response.data])

    def test_user_can_mark_own_notification_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("notification-read", args=[self.unread.pk]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.unread.refresh_from_db()
        self.assertTrue(self.unread.is_read)

    def test_user_cannot_mark_another_users_notification_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("notification-read", args=[self.other_notification.pk]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_user_can_delete_own_notification(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse("notification-delete", args=[self.unread.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(pk=self.unread.pk).exists())

    def test_user_cannot_delete_another_users_notification(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse("notification-delete", args=[self.other_notification.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Notification.objects.filter(pk=self.other_notification.pk).exists()
        )

    def test_unread_filter_works(self):
        self.older.is_read = True
        self.older.save(update_fields=["is_read"])
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("notification-list") + "?unread=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.unread.id])

    def test_unauthenticated_access_is_denied(self):
        list_response = self.client.get(reverse("notification-list"))
        read_response = self.client.patch(
            reverse("notification-read", args=[self.unread.pk]),
            {},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("notification-delete", args=[self.unread.pk])
        )

        self.assertEqual(list_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(read_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(delete_response.status_code, status.HTTP_401_UNAUTHORIZED)
