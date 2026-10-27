import pytest

pytest.importorskip("langchain_core")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from evals.judge import judge_answer


def judge_with_reply(text):
    llm = GenericFakeChatModel(messages=iter([AIMessage(content=text)]))
    return judge_answer(llm, "q", ['{"price_eur": 4650}'], "It costs 4650")


def test_plain_json():
    v = judge_with_reply('{"supported": true, "unsupported_claims": [], "reason": "ok"}')
    assert v.supported


def test_fenced_json_with_chatter():
    reply = 'Sure!\n```json\n{"supported": false, "unsupported_claims": ["€3,990"]}\n```'
    v = judge_with_reply(reply)
    assert not v.supported
    assert v.unsupported_claims == ["€3,990"]


def test_garbage_reply_is_a_judge_error_not_a_verdict():
    v = judge_with_reply("I think it's fine")
    assert v.error
