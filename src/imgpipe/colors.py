from PIL import ImageColor

TRANSPARENT = (0, 0, 0, 0)


def parse_color(value: str, what: str = "color") -> tuple[int, int, int, int]:
    """``'transparent'``, a name such as ``'white'`` or hex such as ``'#ffffff'`` -> RGBA tuple.

    Raises ``ValueError`` (naming ``what``, e.g. "fill color") for anything else.
    """
    if value == "transparent":
        return TRANSPARENT
    try:
        return ImageColor.getcolor(value, "RGBA")
    except ValueError:
        raise ValueError(
            f"invalid {what} {value!r}; use 'transparent', a name like 'white', "
            "or hex like '#ffffff'"
        ) from None
