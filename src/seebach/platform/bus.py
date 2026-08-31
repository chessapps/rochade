"""The application-wide mediator instance.

Kept apart from `mediator.py` so that the machinery stays importable without
dragging in the pipeline, which is what lets tests assemble their own.
"""

from seebach.platform.mediator import Mediator
from seebach.platform.pipeline import DEFAULT_PIPELINE

bus = Mediator(DEFAULT_PIPELINE)
