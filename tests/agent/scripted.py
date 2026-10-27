"""A fake chat model that plays back a script. Use it for every test that needs a model."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ScriptedModel(GenericFakeChatModel):
    """Plays back AIMessages in order. bind_tools is a no-op."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, args, call_id="call_1", usage=None):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id}],
        usage_metadata=usage,
    )


def reply(text, usage=None):
    return AIMessage(content=text, usage_metadata=usage)


def scripted(*messages):
    return ScriptedModel(messages=iter(messages))
