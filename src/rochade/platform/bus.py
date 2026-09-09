"""The application-wide mediator instance.

Kept apart from `mediator.py` so that the machinery stays importable without
dragging in the pipeline, which is what lets tests assemble their own.
"""

from rochade.platform.mediator import Mediator
from rochade.platform.pipeline import DEFAULT_PIPELINE

bus = Mediator(DEFAULT_PIPELINE)
