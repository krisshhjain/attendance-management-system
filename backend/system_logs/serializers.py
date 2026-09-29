from rest_framework import serializers

from .models import SystemLog
from .services import _sanitize_json, _sanitize_string


class SystemLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()
    user_agent = serializers.SerializerMethodField()
    before_state = serializers.SerializerMethodField()
    after_state = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()

    class Meta:
        model = SystemLog
        fields = [
            "id",
            "timestamp",
            "created_at",
            "severity",
            "category",
            "event_type",
            "status",
            "actor",
            "actor_role",
            "target_type",
            "target_id",
            "target_label",
            "message",
            "source",
            "ip_address",
            "user_agent",
            "request_id",
            "before_state",
            "after_state",
            "metadata",
        ]
        read_only_fields = fields

    def get_actor(self, obj):
        if obj.actor_id is None:
            return None
        name = obj.actor.get_full_name().strip() or obj.actor.email
        return {
            "id": obj.actor_id,
            "email": _sanitize_string(obj.actor.email),
            "name": _sanitize_string(name),
        }

    def get_message(self, obj):
        return _sanitize_string(obj.message)

    def get_target_label(self, obj):
        return _sanitize_string(obj.target_label)

    def get_user_agent(self, obj):
        return _sanitize_string(obj.user_agent)

    def get_before_state(self, obj):
        return _sanitize_json(obj.before_state)

    def get_after_state(self, obj):
        return _sanitize_json(obj.after_state)

    def get_metadata(self, obj):
        return _sanitize_json(obj.metadata)
