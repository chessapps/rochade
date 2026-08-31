class TrfParseError(ValueError):
    """A TRF line could not be understood at all.

    Raised only for structural damage. Unknown line types are *not* an error --
    they are retained verbatim and re-emitted, which is the whole point.
    """

    def __init__(self, message: str, *, line_no: int, line: str) -> None:
        super().__init__(f"line {line_no}: {message}")
        self.line_no = line_no
        self.line = line
