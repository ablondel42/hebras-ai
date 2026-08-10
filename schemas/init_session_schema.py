init_session_schema = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "session_started"
            ]
        },
        "status": {
            "type": "string"
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
        "workspace": {
            "type": "string"
        },
        "context_window": {
            "type": "integer"
        },
        "input_tokens": {
            "type": "integer"
        },
        "output_tokens": {
            "type": "integer"
        },
        "context_usage_percent": {
            "type": "number"
        }
    },
    "required": [
        "action",
        "status",
        "conversation_id",
        "model",
        "mode",
        "workspace",
        "context_window",
        "input_tokens",
        "output_tokens",
        "context_usage_percent"
    ]
}