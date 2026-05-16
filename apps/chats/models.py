from django.conf import settings
from django.db import models


class Chat(models.Model):
    class Type(models.TextChoices):
        PRIVATE = "PRIVATE", "Prive"
        GROUP = "GROUP", "Groupe"
        EVENT = "EVENT", "Evenement"

    type = models.CharField(max_length=20, choices=Type.choices, default=Type.GROUP)
    name = models.CharField(max_length=120, blank=True)
    event_id = models.PositiveIntegerField(null=True, blank=True)
    sortie_id = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_chats",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chats_chat"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name or f"Chat {self.id}"


class ChatParticipant(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_participations")
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chats_participant"
        unique_together = [["chat", "user"]]


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chats_message"
        ordering = ["created_at"]
