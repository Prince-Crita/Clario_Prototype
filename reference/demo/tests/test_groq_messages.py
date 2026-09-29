from clario.agent.agent import _strip_groq_unsupported_message_fields


def test_strip_groq_reasoning_fields_from_assistant_history():
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "hello",
            "reasoning_content": "thinking",
            "reasoning": "also thinking",
            "tool_calls": [{"id": "1"}],
        },
        {"role": "user", "content": "again"},
    ]
    cleaned = _strip_groq_unsupported_message_fields(messages)
    assert cleaned[1] == {
        "role": "assistant",
        "content": "hello",
        "tool_calls": [{"id": "1"}],
    }
    assert cleaned[0]["role"] == "user"
