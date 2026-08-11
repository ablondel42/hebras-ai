"""ANSI escape sequence processing and text extraction for agy TUI output."""
import re
import logging

logger = logging.getLogger(__name__)

# Matches ANSI escape sequences (colors, cursor movements, CSI, OSC, mode queries, private modes, etc.)
ANSI_ESCAPE_RE = re.compile(
    r"\x1b"
    r"(?:"
    r"\[[\d;?><=]*[$]?[A-Za-z]"  # CSI sequences including private modes like \x1b[>4m, \x1b[=0;1u
    r"|\][^\x07]*(?:\x07|\x1b\\)"
    r"|[()][AB012]"
    r"|[>=<][^\n]*?[a-z]"
    r"|."
    r")"
)

# Braille spinner characters used by agy TUI animation
SPINNER_CHARS = frozenset("⣾⣷⣯⣟⡿⢿⣻⣽")

# Block drawing characters used by agy logo
BLOCK_CHARS = frozenset("▄▀▸")

# TUI chrome line prefixes to filter out
CHROME_PATTERNS = (
    "Generating...",
    "? for shortcuts",
    "esc to cancel",
    "────",
    "> Plan mode",
    "> Accept edits",
    "> Accept-edits",
    "Welcome to the",
    "Antigravity CLI",
    "Signing in...",
    "Thought Process",
    "for shortcuts",
    ">4m",
    "=0;1u",
)


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences and carriage returns.

    Args:
        text: Raw text containing escape sequences.

    Returns:
        Clean text with escape codes removed.
    """
    clean = ANSI_ESCAPE_RE.sub("", text)
    return clean.replace("\r", "")


def extract_response_text(raw_output: str) -> str:
    """Extract clean assistant response from raw agy TUI output.

    Strips ANSI escape codes, spinner frames, logo graphics, and UI chrome.

    Args:
        raw_output: Raw PTY output captured from agy TUI process.

    Returns:
        Clean extracted response text.
    """
    cleaned = strip_ansi(raw_output)
    lines = cleaned.split("\n")

    content_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip spinner animation lines
        if any(c in SPINNER_CHARS for c in stripped):
            continue
        # Skip block logo characters
        if any(c in BLOCK_CHARS for c in stripped):
            continue
        # Skip UI chrome and status indicators
        if any(stripped.startswith(pat) for pat in CHROME_PATTERNS):
            continue
        # Skip email status line in sign-in box
        if "@" in stripped and "." in stripped and len(stripped) < 50:
            continue
        content_lines.append(stripped)

    result = "\n".join(content_lines).strip()
    logger.debug(f"Extracted {len(result)} chars from {len(raw_output)} raw output chars")
    return result
