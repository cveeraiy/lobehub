from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ConnectionMode = Literal["polling", "webhook", "websocket"]
FieldSchema = dict[str, Any]


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationError] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"valid": self.valid}
        if self.errors:
            data["errors"] = [error.to_dict() for error in self.errors]
        return data


class PlatformDefinition:
    id: str
    name: str
    connection_mode: ConnectionMode
    schema: list[FieldSchema]
    description: str | None = None
    documentation: dict[str, str] | None = None
    show_webhook_url: bool | None = None
    supports_markdown: bool | None = None
    supports_message_edit: bool | None = None

    def serialize(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "connectionMode": self.connection_mode,
            "schema": self.schema,
        }
        if self.description is not None:
            data["description"] = self.description
        if self.documentation is not None:
            data["documentation"] = self.documentation
        if self.show_webhook_url is not None:
            data["showWebhookUrl"] = self.show_webhook_url
        if self.supports_markdown is not None:
            data["supportsMarkdown"] = self.supports_markdown
        if self.supports_message_edit is not None:
            data["supportsMessageEdit"] = self.supports_message_edit
        return data

    async def validate_credentials(
        self,
        credentials: dict[str, str],
        settings: dict[str, Any] | None = None,
        application_id: str | None = None,
    ) -> ValidationResult:
        return ValidationResult(valid=True)

    def merge_settings(self, settings: dict[str, Any] | None) -> dict[str, Any]:
        from app.services.bot.platforms.common import merge_settings_with_defaults

        return merge_settings_with_defaults(self.schema, settings)

