"""The pipeline every message passes through.

Order matters. Logging wraps everything so a rejection is still recorded;
authorization runs before validation so an unauthorized caller learns nothing
about the shape of the data; the transaction opens before idempotency so that a
command and its dedupe record commit together.
"""

from rochade.platform.pipeline.authorize import authorize
from rochade.platform.pipeline.idempotency import idempotency
from rochade.platform.pipeline.log import log
from rochade.platform.pipeline.transaction import transaction
from rochade.platform.pipeline.validate import validate

DEFAULT_PIPELINE = (log, authorize, validate, transaction, idempotency)

__all__ = ["DEFAULT_PIPELINE", "authorize", "idempotency", "log", "transaction", "validate"]
