from __future__ import annotations

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from langchain_core.messages.ai import AIMessage, AIMessageChunk
from langchain_core.messages.base import BaseMessage, BaseMessageChunk
from langchain_core.messages.chat import ChatMessage, ChatMessageChunk
from langchain_core.messages.function import FunctionMessage, FunctionMessageChunk
from langchain_core.messages.human import HumanMessage, HumanMessageChunk
from langchain_core.messages.system import SystemMessage, SystemMessageChunk
from langchain_core.messages.tool import ToolMessage, ToolMessageChunk

AnyMessage = Union[
    AIMessage, HumanMessage, ChatMessage, SystemMessage, FunctionMessage, ToolMessage
]


def get_buffer_string(
    messages: Sequence[BaseMessage], human_prefix: str = "Human", ai_prefix: str = "AI"
) -> str:
    """Convert a sequence of Messages to strings and concatenate them into one string.

    Args:
        messages: Messages to be converted to strings.
        human_prefix: The prefix to prepend to contents of HumanMessages.
        ai_prefix: THe prefix to prepend to contents of AIMessages.

    Returns:
        A single string concatenation of all input messages.

    Example:
        .. code-block:: python

            from langchain_core import AIMessage, HumanMessage

            messages = [
                HumanMessage(content="Hi, how are you?"),
                AIMessage(content="Good, how are you?"),
            ]
            get_buffer_string(messages)
            # -> "Human: Hi, how are you?\nAI: Good, how are you?"
    """
    string_messages = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = human_prefix
        elif isinstance(m, AIMessage):
            role = ai_prefix
        elif isinstance(m, SystemMessage):
            role = "System"
        elif isinstance(m, FunctionMessage):
            role = "Function"
        elif isinstance(m, ToolMessage):
            role = "Tool"
        elif isinstance(m, ChatMessage):
            role = m.role
        else:
            raise ValueError(f"Got unsupported message type: {m}")
        message = f"{role}: {m.content}"
        if isinstance(m, AIMessage) and "function_call" in m.additional_kwargs:
            message += f"{m.additional_kwargs['function_call']}"
        string_messages.append(message)

    return "\n".join(string_messages)


def _message_from_dict(message: dict) -> BaseMessage:
    _type = message["type"]
    if _type == "human":
        return HumanMessage(**message["data"])
    elif _type == "ai":
        return AIMessage(**message["data"])
    elif _type == "system":
        return SystemMessage(**message["data"])
    elif _type == "chat":
        return ChatMessage(**message["data"])
    elif _type == "function":
        return FunctionMessage(**message["data"])
    elif _type == "tool":
        return ToolMessage(**message["data"])
    elif _type == "AIMessageChunk":
        return AIMessageChunk(**message["data"])
    elif _type == "HumanMessageChunk":
        return HumanMessageChunk(**message["data"])
    elif _type == "FunctionMessageChunk":
        return FunctionMessageChunk(**message["data"])
    elif _type == "ToolMessageChunk":
        return ToolMessageChunk(**message["data"])
    elif _type == "SystemMessageChunk":
        return SystemMessageChunk(**message["data"])
    elif _type == "ChatMessageChunk":
        return ChatMessageChunk(**message["data"])
    else:
        raise ValueError(f"Got unexpected message type: {_type}")


def messages_from_dict(messages: Sequence[dict]) -> List[BaseMessage]:
    """Convert a sequence of messages from dicts to Message objects.

    Args:
        messages: Sequence of messages (as dicts) to convert.

    Returns:
        List of messages (BaseMessages).
    """
    return [_message_from_dict(m) for m in messages]


def message_chunk_to_message(chunk: BaseMessageChunk) -> BaseMessage:
    """Convert a message chunk to a message.

    Args:
        chunk: Message chunk to convert.

    Returns:
        Message.
    """
    if not isinstance(chunk, BaseMessageChunk):
        return chunk
    # chunk classes always have the equivalent non-chunk class as their first parent
    ignore_keys = ["type"]
    if isinstance(chunk, AIMessageChunk):
        ignore_keys.append("tool_call_chunks")
    return chunk.__class__.__mro__[1](
        **{k: v for k, v in chunk.__dict__.items() if k not in ignore_keys}
    )


MessageLikeRepresentation = Union[
    BaseMessage, List[str], Tuple[str, str], str, Dict[str, Any]
]


def _create_message_from_message_type(
    message_type: str,
    content: str,
    name: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    id: Optional[str] = None,
    **additional_kwargs: Any,
) -> BaseMessage:
    """Create a message from a message type and content string.

    Args:
        message_type: str the type of the message (e.g., "human", "ai", etc.)
        content: str the content string.

    Returns:
        a message of the appropriate type.
    """
    kwargs: Dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if tool_call_id is not None:
        kwargs["tool_call_id"] = tool_call_id
    if additional_kwargs:
        kwargs["additional_kwargs"] = additional_kwargs  # type: ignore[assignment]
    if id is not None:
        kwargs["id"] = id
    if tool_calls is not None:
        kwargs["tool_calls"] = tool_calls
    if message_type in ("human", "user"):
        message: BaseMessage = HumanMessage(content=content, **kwargs)
    elif message_type in ("ai", "assistant"):
        message = AIMessage(content=content, **kwargs)
    elif message_type == "system":
        message = SystemMessage(content=content, **kwargs)
    elif message_type == "function":
        message = FunctionMessage(content=content, **kwargs)
    elif message_type == "tool":
        message = ToolMessage(content=content, **kwargs)
    else:
        raise ValueError(
            f"Unexpected message type: {message_type}. Use one of 'human',"
            f" 'user', 'ai', 'assistant', or 'system'."
        )
    return message


def _convert_to_message(message: MessageLikeRepresentation) -> BaseMessage:
    """Instantiate a message from a variety of message formats.

    The message format can be one of the following:

    - BaseMessagePromptTemplate
    - BaseMessage
    - 2-tuple of (role string, template); e.g., ("human", "{user_input}")
    - dict: a message dict with role and content keys
    - string: shorthand for ("human", template); e.g., "{user_input}"

    Args:
        message: a representation of a message in one of the supported formats

    Returns:
        an instance of a message or a message template
    """
    if isinstance(message, BaseMessage):
        _message = message
    elif isinstance(message, str):
        _message = _create_message_from_message_type("human", message)
    elif isinstance(message, Sequence) and len(message) == 2:
        # mypy doesn't realise this can't be a string given the previous branch
        message_type_str, template = message  # type: ignore[misc]
        _message = _create_message_from_message_type(message_type_str, template)
    elif isinstance(message, dict):
        msg_kwargs = message.copy()
        try:
            try:
                msg_type = msg_kwargs.pop("role")
            except KeyError:
                msg_type = msg_kwargs.pop("type")
            msg_content = msg_kwargs.pop("content")
        except KeyError:
            raise ValueError(
                f"Message dict must contain 'role' and 'content' keys, got {message}"
            )
        _message = _create_message_from_message_type(
            msg_type, msg_content, **msg_kwargs
        )
    else:
        raise NotImplementedError(f"Unsupported message type: {type(message)}")

    return _message


def convert_to_messages(
    messages: Sequence[MessageLikeRepresentation],
) -> List[BaseMessage]:
    """Convert a sequence of messages to a list of messages.

    Args:
        messages: Sequence of messages to convert.

    Returns:
        List of messages (BaseMessages).
    """
    return [_convert_to_message(m) for m in messages]


def filter_messages(
    messages: Sequence[MessageLikeRepresentation],
    *,
    incl_names: Optional[Sequence[str]] = None,
    excl_names: Optional[Sequence[str]] = None,
    incl_types: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
    excl_types: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
    incl_ids: Optional[Sequence[str]] = None,
    excl_ids: Optional[Sequence[str]] = None,
) -> List[BaseMessage]:
    """Filter messages based on name, type or id.

    Args:
        messages: Sequence Message-like objects to filter.
        incl_names: Message names to include.
        excl_names: Messages names to exclude.
        incl_types: Message types to include. Can be specified as string names (e.g.
            "system", "human", "ai", ...) or as BaseMessage classes (e.g.
            SystemMessage, HumanMessage, AIMessage, ...).
        excl_types: Message types to exclude. Can be specified as string names (e.g.
            "system", "human", "ai", ...) or as BaseMessage classes (e.g.
            SystemMessage, HumanMessage, AIMessage, ...).
        incl_ids: Message IDs to include.
        excl_ids: Message IDs to exclude.

    Returns:
        A list of Messages that meets at least one of the incl_* conditions and none
            of the excl_* conditions.

    Raises:
        ValueError if two incompatible arguments are provided.

    Example:
        .. code-block:: python

            from langchain_core.messages import filter_messages

            messages = [
                SystemMessage("you're a good assistant."),
                HumanMessage("what's your name", id="foo", name="example_user"),
                AIMessage("steve-o", id="bar", name="example_assistant"),
                HumanMessage("what's your favorite color", id="baz",),
                AIMessage("silicon blue", id="blah",),
            ]

            filter_messages(
                messages
                incl_names=("example_user", "example_assistant"),
                incl_type=("system"),
                excl_ids=("bar"),
            )

        .. code-block:: python

                [
                    SystemMessage("you're a good assistant."),
                    HumanMessage("what's your name", id="foo", name="example_user"),
                ]

    """
    messages = convert_to_messages(messages)
    incl_types_str = [t for t in (incl_types or ()) if isinstance(t, str)]
    incl_types_types = tuple(t for t in (incl_types or ()) if isinstance(t, type))
    excl_types_str = [t for t in (excl_types or ()) if isinstance(t, str)]
    excl_types_types = tuple(t for t in (excl_types or ()) if isinstance(t, type))

    filtered: List[BaseMessage] = []
    for msg in messages:
        if excl_names and msg.name in excl_names:
            continue
        elif excl_types_str and msg.type in excl_types_str:
            continue
        elif excl_types_types and isinstance(msg.type, excl_types_types):
            continue
        elif excl_ids and msg.id in excl_ids:
            continue
        else:
            pass

        if incl_names and msg.name in incl_names:
            filtered.append(msg)
            continue
        elif incl_types_str and msg.type in incl_types_str:
            filtered.append(msg)
            continue
        elif incl_types_types and isinstance(msg, incl_types_types):
            filtered.append(msg)
            continue
        elif incl_ids and msg.id in incl_ids:
            filtered.append(msg)
            continue
        else:
            pass

    return filtered


def merge_message_runs(
    messages: Sequence[MessageLikeRepresentation],
) -> List[BaseMessage]:
    """Merge runs of Messages of the same type.

    Args:
        messages: Sequence Message-like objects to merge.

    Returns:
        List of BaseMessages with consecutive runs of message types merged into single
        messages.

    Example:
        .. code-block:: python

            ...
    """
    if not messages:
        return []
    messages = convert_to_messages(messages)
    merged = [messages[0].copy(deep=True)]
    for msg in messages[1:]:
        curr = msg.copy(deep=True)
        last = merged.pop()
        if not isinstance(curr, last.__class__):
            merged.extend([last, curr])
        else:
            merged.append(_chunk_to_msg(_msg_to_chunk(last) + _msg_to_chunk(curr)))
    return merged


def trim_messages(
    messages: Sequence[MessageLikeRepresentation],
    *,
    n_tokens: int,
    token_counter: Union[
        Callable[[List[BaseMessage]], int], Callable[[BaseMessage], int]
    ],
    strategy: Literal["first", "last"] = "last",
    allow_partial: bool = False,
    end_on: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
    start_on: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
    keep_system: bool = False,
) -> List[BaseMessage]:
    """Trim messages to be below a token count.

    Args:
        messages: Sequence of Message-like objects to trim.
        n_tokens: Max token count of trimmed messages.
        token_counter: Function for counting tokens of a BaseMessage or a list of
            BaseMessage.
        strategy: Strategy for trimming.
            - "first": Keep the first <= n_count tokens of the messages.
            - "last": Keep the last <= n_count tokens of the messages.
        allow_partial: Whether to split a message if only part of the message can be
            included.
        end_on: The message type to end on. Can be specified as string names (e.g.
            "system", "human", "ai", ...) or as BaseMessage classes (e.g.
            SystemMessage, HumanMessage, AIMessage, ...). Should only be specified if
            ``strategy="first"``.
        start_on: The message type to start on. Can be specified as string names (e.g.
            "system", "human", "ai", ...) or as BaseMessage classes (e.g.
            SystemMessage, HumanMessage, AIMessage, ...). Should only be specified if
            ``strategy="last"``. Ignores a SystemMessage at index 0 if
            ``keep_system=True``.
        keep_system: Whether to keep the SystemMessage if there is one at index 0.
            Should only be specified if ``strategy="last"``.

    Returns:
        List of trimmed BaseMessages.

    Raises:
        ValueError: if two incompatible arguments are specified or an unrecognized
            ``strategy`` is specified.

    Example:
        .. code-block:: python

            ...

    """
    if end_on and strategy == "last":
        raise ValueError
    if start_on and strategy == "first":
        raise ValueError
    if keep_system and strategy == "first":
        raise ValueError
    messages = convert_to_messages(messages)
    if (
        list(inspect.signature(token_counter).parameters.values())[0].annotation
        is BaseMessage
    ):

        def list_token_counter(messages: Sequence[BaseMessage]) -> int:
            return sum(token_counter(msg) for msg in messages)  # type: ignore[arg-type, misc]
    else:
        list_token_counter = token_counter  # type: ignore[assignment]

    if strategy == "first":
        return _first_n_tokens(
            messages,
            n_tokens=n_tokens,
            token_counter=list_token_counter,
            allow_partial=allow_partial,
            end_on=end_on,
        )
    elif strategy == "last":
        return _last_n_tokens(
            messages,
            n_tokens=n_tokens,
            token_counter=list_token_counter,
            allow_partial=allow_partial,
            keep_system=keep_system,
            start_on=start_on,
        )
    else:
        raise ValueError(
            f"Unrecognized {strategy=}. Supported strategies are 'last' and 'first'."
        )


def _first_n_tokens(
    messages: Sequence[BaseMessage],
    *,
    n_tokens: int,
    token_counter: Callable[[Sequence[BaseMessage]], int],
    allow_partial: bool = False,
    end_on: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
    text_splitter: Optional[Callable[[str], List[str]]] = None,
) -> List[BaseMessage]:
    text_splitter = text_splitter or _default_text_splitter
    idx = 0
    messages = list(messages)
    for i in range(len(messages)):
        if token_counter(messages[:-i] if i else messages) <= n_tokens:
            idx = len(messages) - i
            break

    if idx < len(messages) - 1 and allow_partial:
        included_partial = False
        if isinstance(messages[idx].content, list):
            excluded = messages[idx].copy(deep=True)
            num_block = len(excluded.content)
            for _ in range(1, num_block):
                excluded.content = excluded.content[:-1]
                if token_counter(messages[:idx] + [excluded]) <= n_tokens:
                    messages = messages[:idx] + [excluded]
                    idx += 1
                    included_partial = True
                    break
        if not included_partial:
            excluded = messages[idx].copy(deep=True)
            if isinstance(messages[idx].content, list) and any(
                isinstance(block, str) or block["type"] == "text"
                for block in messages[idx].content
            ):
                text_block = next(
                    block
                    for block in messages[idx].content
                    if isinstance(block, str) or block["type"] == "text"
                )
                text = (
                    text_block["text"] if isinstance(text_block, dict) else text_block
                )
            elif isinstance(messages[idx].content, str):
                text = messages[idx].content
            else:
                text = None
            if text:
                split_texts = text_splitter(text)
                excluded.content = [{"type": "text", "text": t} for t in split_texts]
                for _ in range(1, len(split_texts)):
                    excluded.content = excluded.content[:-1]
                    if token_counter(messages[:idx] + [excluded]) <= n_tokens:
                        messages = messages[:idx] + [excluded]
                        idx += 1
                        break

    if isinstance(end_on, str):
        while messages[idx - 1].type != end_on and idx > 0:
            idx = idx - 1
    elif isinstance(end_on, type):
        while not isinstance(messages[idx - 1], end_on) and idx > 0:
            idx = idx - 1
    else:
        pass

    return messages[:idx]


def _last_n_tokens(
    messages: Sequence[BaseMessage],
    *,
    n_tokens: int,
    token_counter: Callable[[Sequence[BaseMessage]], int],
    allow_partial: bool = False,
    keep_system: bool = False,
    start_on: Optional[Sequence[Union[str, Type[BaseMessage]]]] = None,
) -> List[BaseMessage]:
    messages = list(messages)
    swapped_system = keep_system and isinstance(messages[0], SystemMessage)
    if swapped_system:
        reversed_ = messages[:1] + messages[1::-1]
    else:
        reversed_ = messages[::-1]

    reversed_ = _first_n_tokens(
        reversed_,
        n_tokens=n_tokens,
        token_counter=token_counter,
        allow_partial=allow_partial,
        end_on=start_on,
    )
    if swapped_system:
        return reversed_[:1] + reversed_[1::-1]
    else:
        return reversed_[::-1]


_MSG_CHUNK_MAP: Dict[Type[BaseMessage], Type[BaseMessageChunk]] = {
    HumanMessage: HumanMessageChunk,
    AIMessage: AIMessageChunk,
    SystemMessage: SystemMessageChunk,
    ToolMessage: ToolMessageChunk,
    FunctionMessage: FunctionMessageChunk,
    ChatMessage: ChatMessageChunk,
}
_CHUNK_MSG_MAP = {v: k for k, v in _MSG_CHUNK_MAP.items()}


def _msg_to_chunk(message: BaseMessage) -> BaseMessageChunk:
    if message.__class__ in _MSG_CHUNK_MAP:
        return _MSG_CHUNK_MAP[message.__class__](**message.dict(exclude={"type"}))

    for msg_cls, chunk_cls in _MSG_CHUNK_MAP.items():
        if isinstance(message, msg_cls):
            return chunk_cls(**message.dict(exclude={"type"}))

    raise ValueError(
        f"Unrecognized message class {message.__class__}. Supported classes are "
        f"{list(_MSG_CHUNK_MAP.keys())}"
    )


def _chunk_to_msg(chunk: BaseMessageChunk) -> BaseMessage:
    # TODO: does this break when there are extra fields in chunk.
    if chunk.__class__ in _CHUNK_MSG_MAP:
        return _CHUNK_MSG_MAP[chunk.__class__](
            **chunk.dict(exclude={"type", "tool_call_chunks"})
        )
    for chunk_cls, msg_cls in _CHUNK_MSG_MAP.items():
        if isinstance(chunk, chunk_cls):
            return msg_cls(**chunk.dict(exclude={"type", "tool_call_chunks"}))

    raise ValueError(
        f"Unrecognized message chunk class {chunk.__class__}. Supported classes are "
        f"{list(_CHUNK_MSG_MAP.keys())}"
    )


def _default_text_splitter(text: str) -> List[str]:
    return text.split("\n")
