---
description: Always format artifact markdown links using host-friendly tilde paths (~/.gemini/antigravity-cli/brain/<conversation_id>/<file>.md) for Cmd+Click editor navigation.
globs: ["**/*"]
always_on: true
---

# Artifact Link Formatting Rule

When referencing artifacts (plans, walkthroughs, task summaries, or evaluation reports) in chat responses or documentation:

1. **Use Tilde Paths**:
   - ALWAYS format markdown links using the tilde path:
     `[Link Text](~/.gemini/antigravity-cli/brain/<conversation_id>/<filename>.md)`
   - NEVER use the container-specific `file:///home/vscode/...` prefix.

2. **Cmd+Click Navigation**:
   - This ensures links resolve directly on the user's host machine and open cleanly in the editor when clicking with `Cmd+Click` (macOS) or `Ctrl+Click` (Linux/Windows).
