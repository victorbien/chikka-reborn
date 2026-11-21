"""Mock AI provider: nothing external is called and nothing costs money.

Used for development, demos and every automated test. Outputs are clearly generic. Tests can
queue exact replies or errors with `script` and inspect what the service sent in `calls`.
"""

import json
import re
from collections import deque
from collections.abc import Callable, Iterable

from app.integrations.ai.base import AiCompletion, AiProvider, AiProviderError, AiRequest

Scripted = str | AiProviderError
Responder = Callable[[AiRequest], str]

_FILLER = re.compile(r"\b(just|really|very|actually|basically|kindly)\s+", re.IGNORECASE)


def _default_reply(request: AiRequest) -> str:
    data = json.loads(request.user_content)
    feature = request.feature
    if feature == "suggest_replies":
        options = ["Okay, sounds good!", "Thanks, talk to you soon.", "Can you tell me more?"]
        return json.dumps({"suggestions": options[: int(data.get("count", 3))]})
    if feature == "translate":
        return json.dumps({"text": f"[{data['target_language']}] {data['text']}"})
    if feature in ("rewrite", "tone_adjust"):
        return json.dumps({"text": f"{str(data['text']).strip()} (demo rewrite)"})
    if feature == "summarise":
        return json.dumps({"text": f"Demo summary of {len(data['messages'])} messages."})
    if feature == "compose":
        return json.dumps({"text": "Hi! I will be about 15 minutes late. See you soon."})
    shortened = _FILLER.sub("", " ".join(str(data["text"]).split()))
    return json.dumps({"text": shortened, "meaning_preserved": True})


class MockAiProvider(AiProvider):
    name = "mock"
    model_id = "mock-ai-1"

    def __init__(
        self, *, script: Iterable[Scripted] = (), responder: Responder | None = None
    ) -> None:
        self._script: deque[Scripted] = deque(script)
        self._responder = responder or _default_reply
        self.calls: list[AiRequest] = []

    def queue(self, *replies: Scripted) -> None:
        self._script.extend(replies)

    async def complete(self, request: AiRequest) -> AiCompletion:
        self.calls.append(request)
        reply = self._script.popleft() if self._script else self._responder(request)
        if isinstance(reply, AiProviderError):
            raise reply
        return AiCompletion(
            text=reply,
            model_id=self.model_id,
            input_tokens=len(request.user_content) // 4,
            output_tokens=len(reply) // 4,
        )
