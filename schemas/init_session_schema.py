init_session_schema = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "session_started"
            ]
        },
        "conversation_id": {
            "type": "string"
        },
        "model": {
            "type": "string"
        },
        "mode": {
            "type": "string",
            "enum": [
                "plan",
                "default",
                "accept-edits"
            ]
        },
        "agent": {
            "type": "string",
        },
        "workspace": {
            "type": "string"
        },
        "context_usage_percent": {
            "type": "number"
        }
    },
    "required": [
        "action",
        "conversation_id",
        "model",
        "mode",
        "agent",
        "workspace",
        "context_usage_percent"
    ]
}