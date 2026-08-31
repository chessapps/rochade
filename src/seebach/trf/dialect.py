from enum import StrEnum


class Dialect(StrEnum):
    """Which TRF flavour a serializer targets.

    Never serialize to "TRF" generically. Vega writes TRF16/UTF-8 and reads
    TRF06 within that format's limits, so the target is always named.
    """

    TRF06 = "trf06"
    TRF16 = "trf16"

    @property
    def encoding(self) -> str:
        return "utf-8" if self is Dialect.TRF16 else "cp1252"
