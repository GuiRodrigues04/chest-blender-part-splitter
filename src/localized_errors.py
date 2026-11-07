"""Structured, serializable geometry messages, localized at presentation time."""

MESSAGE_MARKER = "__splitter_message__"


def message_payload(key, **params):
    return {MESSAGE_MARKER: key, "params": params}


def error_payload(error):
    if isinstance(error, LocalizedGeometryError):
        return error.payload
    if isinstance(error, dict) and MESSAGE_MARKER in error:
        return error
    return str(error)


def render_message(value):
    from .translations import tr, localize_text
    value = decode_message(value)
    if isinstance(value, LocalizedGeometryError):
        value = value.payload
    if isinstance(value, dict) and MESSAGE_MARKER in value:
        return tr(value[MESSAGE_MARKER], **value.get("params", {}))
    return localize_text(str(value))


def decode_message(value):
    """Decode only our explicitly marked payloads; user text stays verbatim."""
    if isinstance(value, str) and value.startswith('{') and MESSAGE_MARKER in value:
        import json
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict) and MESSAGE_MARKER in parsed:
                return parsed
        except (ValueError, TypeError):
            pass
    return value


class LocalizedGeometryError(ValueError):
    """A failure whose parameters survive status storage and language changes."""

    def __init__(self, key, **params):
        self.payload = message_payload(key, **params)
        super().__init__(key)

    def __str__(self):
        return render_message(self.payload)
