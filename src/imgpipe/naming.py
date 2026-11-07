"""The rename section: output file names built from a pattern.

Not a pipeline step: the name is made for every image after the steps (see ``Pipeline.run``).
The pattern follows the conventions of Java's ``DateTimeFormatter`` and file managers: a token
is a run of the same letter, text in 'single quotes' is literal.
"""

import random
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Token letter -> allowed counts (None: any count of at least 1).
COUNTS: dict[str, tuple[int, ...] | None] = {
    "N": (1,), "E": (1,), "U": (1,),
    "Y": (2, 4), "M": (1, 2),
    "d": (1, 2), "H": (1, 2), "h": (1, 2), "m": (1, 2), "s": (1, 2),
    "S": (1, 2, 3),
    "C": None, "R": None, "A": None, "a": None, "L": None, "B": None,
}
RANDOM_ALPHABETS = {
    "R": string.digits,
    "A": string.ascii_uppercase,
    "a": string.ascii_lowercase,
    "L": string.ascii_letters,
    "B": string.ascii_letters + string.digits,
}
FORBIDDEN = '/\\:*?"<>|'


@dataclass(frozen=True)
class Literal:
    text: str


@dataclass(frozen=True)
class Token:
    letter: str
    count: int


def parse_pattern(pattern: str) -> list[Literal | Token]:
    """Split a pattern into literal text and tokens; raises ``ValueError`` if it is invalid."""
    if not pattern:
        raise ValueError("'pattern' must not be empty")
    parts: list[Literal | Token] = []
    text: list[str] = []

    def flush() -> None:
        if text:
            parts.append(Literal("".join(text)))
            text.clear()

    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "'":
            if pattern[i + 1 : i + 2] == "'":  # '' is a single quote
                text.append("'")
                i += 2
                continue
            end = i + 1
            while end < len(pattern):
                if pattern[end] == "'":
                    if pattern[end + 1 : end + 2] != "'":
                        break
                    text.append("'")  # '' inside quotes
                    end += 2
                    continue
                text.append(pattern[end])
                end += 1
            else:
                raise ValueError(f"'pattern': the quote at position {i + 1} is never closed")
            i = end + 1
        elif char in COUNTS:
            end = i
            while end < len(pattern) and pattern[end] == char:
                end += 1
            count = end - i
            allowed = COUNTS[char]
            if allowed is not None and count not in allowed:
                wanted = " or ".join(str(n) for n in allowed)
                raise ValueError(
                    f"'pattern': '{char * count}' is not valid; "
                    f"'{char}' must be repeated {wanted} time(s)"
                )
            flush()
            parts.append(Token(char, count))
            i = end
        else:
            text.append(char)
            i += 1
    flush()

    for part in parts:
        if isinstance(part, Literal):
            bad = sorted({c for c in part.text if c in FORBIDDEN})
            if bad:
                raise ValueError(
                    f"'pattern': {' '.join(bad)} cannot be used in a file name"
                )
    return parts


@dataclass
class RenameSettings:
    pattern: str
    counter_start: int = 1

    def __post_init__(self):
        if self.counter_start < 0:
            raise ValueError(f"'counter_start' must not be negative, got {self.counter_start}")
        self._parts = parse_pattern(self.pattern)

    def name(self, source: Path, counter: int, now: datetime, rng: random.Random) -> str:
        """The new file name without extension for ``source`` (a path from the input folder)."""
        return "".join(self._render(part, source, counter, now, rng) for part in self._parts)

    @staticmethod
    def _render(part, source: Path, counter: int, now: datetime, rng: random.Random) -> str:
        if isinstance(part, Literal):
            return part.text
        letter, count = part.letter, part.count
        if letter == "N":
            return source.stem
        if letter == "E":
            return source.suffix.removeprefix(".")
        if letter == "U":
            return str(uuid.UUID(int=rng.getrandbits(128), version=4))
        if letter in RANDOM_ALPHABETS:
            alphabet = RANDOM_ALPHABETS[letter]
            return "".join(rng.choice(alphabet) for _ in range(count))
        if letter == "Y":
            return f"{now.year:04d}" if count == 4 else f"{now.year % 100:02d}"
        if letter == "S":
            return f"{now.microsecond:06d}"[:count]
        value = {
            "M": now.month, "d": now.day, "H": now.hour, "h": now.hour % 12 or 12,
            "m": now.minute, "s": now.second, "C": counter,
        }[letter]
        return f"{value:0{count}d}"
