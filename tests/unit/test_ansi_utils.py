"""Tests for ANSI sequence stripping and TUI text extraction."""
from backend.ansi_utils import extract_response_text, strip_ansi


class TestStripAnsi:
    def test_strips_color_codes(self):
        assert strip_ansi("\x1b[31mred text\x1b[m") == "red text"

    def test_strips_cursor_movement(self):
        assert strip_ansi("\x1b[2A\x1b[K") == ""

    def test_strips_kitty_keyboard_protocol(self):
        assert strip_ansi("\x1b[?2026$p\x1b[?2027$p") == ""

    def test_preserves_plain_text(self):
        assert strip_ansi("hello world") == "hello world"

    def test_strips_complex_mix(self):
        raw = "\x1b[38;2;66;133;244mAntigravity CLI\x1b[m"
        assert strip_ansi(raw) == "Antigravity CLI"


class TestExtractResponseText:
    def test_filters_spinner(self):
        raw = "⣾  Generating...\nHello world\n⣷  Generating..."
        assert extract_response_text(raw) == "Hello world"

    def test_filters_ui_chrome(self):
        raw = "────────\n> Plan mode: research\nActual response text\n? for shortcuts"
        assert extract_response_text(raw) == "Actual response text"

    def test_extracts_multiline_response(self):
        raw = "Line one\nLine two\nLine three"
        assert extract_response_text(raw) == "Line one\nLine two\nLine three"

    def test_handles_empty(self):
        assert extract_response_text("") == ""

    def test_filters_welcome_banner(self):
        raw = "Welcome to the Antigravity CLI\nHello there!"
        assert extract_response_text(raw) == "Hello there!"
