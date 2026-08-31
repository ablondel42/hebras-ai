"""Tests for AgySession."""
import time

from backend.session import AgySession


class TestAgySession:
    """Tests for the AgySession dataclass."""

    def test_default_creation(self):
        """Verify session creates with defaults."""
        session = AgySession()
        assert session.session_id is not None
        assert len(session.session_id) == 32  # hex UUID
        assert session.agent == "default"
        assert session.model == "Gemini 3.6 Flash (High)"
        assert session.conversation_id is None
        assert session.workspace is None
        assert session.turn_count == 0

    def test_custom_creation(self):
        """Verify session creates with custom values."""
        session = AgySession(
            agent="custom-agent",
            model="Claude 3.7 Sonnet",
            workspace="/tmp/project",
        )
        assert session.agent == "custom-agent"
        assert session.model == "Claude 3.7 Sonnet"
        assert session.workspace == "/tmp/project"

    def test_touch_increments_turn(self):
        """Verify touch() updates last_active and increments turn_count."""
        session = AgySession()
        original_active = session.last_active
        time.sleep(0.01)  # Ensure time passes
        session.touch()
        assert session.turn_count == 1
        assert session.last_active >= original_active

    def test_agent_and_model_ids(self):
        """Verify agent_id and model_id properties."""
        session = AgySession(agent="code_reviewer", model="Gemini 3.5 Pro")
        assert session.agent_id == "code_reviewer"
        assert session.model_id == "Gemini 3.5 Pro"

    def test_expiry_not_expired(self):
        """Verify session is not expired when idle_timeout is large."""
        session = AgySession()
        assert not session.is_expired(idle_timeout=600)

    def test_expiry_expired(self):
        """Verify session is expired when idle_timeout is 0."""
        session = AgySession()
        assert session.is_expired(idle_timeout=0)
