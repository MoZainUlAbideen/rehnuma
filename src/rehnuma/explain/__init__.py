"""Plain-language bill summaries (Urdu by default) built on the verified engine."""

from rehnuma.explain.faithfulness import check_faithfulness
from rehnuma.explain.render import summarize
from rehnuma.explain.story import BillStory, build_story

__all__ = ["BillStory", "build_story", "check_faithfulness", "summarize"]
