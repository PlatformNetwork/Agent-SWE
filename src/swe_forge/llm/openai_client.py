"""OpenAI direct provider implementation using the official SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from swe_forge.llm.client import (
    Choice,
    FunctionCall,
    GenerationRequest,
    GenerationResponse,
    LLMClient,
    Message,
    ToolCall,
    Usage,
)


class OpenAIClient(LLMClient):
    """OpenAI provider using the official async SDK."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
            base_url: Optional base URL for API requests (e.g., for proxies).
        """
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a response for the given request.

        Args:
            request: The generation request containing model, messages, and params.

        Returns:
            GenerationResponse with the model's output.
        """
        messages = self._convert_messages(request.messages)

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p

        response = await self._client.chat.completions.create(**kwargs)

        return self._convert_response(response)

    async def complete_with_tools(
        self, request: GenerationRequest
    ) -> GenerationResponse:
        """Generate a response with tool calling support.

        Args:
            request: The generation request, potentially containing tool definitions.

        Returns:
            GenerationResponse, potentially with tool calls in the message.
        """
        messages = self._convert_messages(request.messages)

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p

        # Convert tools to OpenAI format
        if request.tools:
            kwargs["tools"] = self._convert_tools(request.tools)

        # Handle tool_choice
        if request.tool_choice is not None:
            kwargs["tool_choice"] = self._convert_tool_choice(request.tool_choice)

        response = await self._client.chat.completions.create(**kwargs)

        return self._convert_response(response)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Stream a response for the given request.

        Args:
            request: The generation request containing model, messages, and params.

        Yields:
            Chunks of the response content as they arrive.
        """
        messages = self._convert_messages(request.messages)

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": True,
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p

        stream = await self._client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert internal Message objects to OpenAI format.

        Args:
            messages: List of Message objects.

        Returns:
            List of dicts in OpenAI message format.
        """
        converted = []
        for msg in messages:
            item: dict[str, Any] = {"role": msg.role, "content": msg.content}

            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id

            converted.append(item)

        return converted

    def _convert_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """Convert internal ToolDefinition objects to OpenAI format.

        Args:
            tools: List of ToolDefinition objects.

        Returns:
            List of dicts in OpenAI tool format.
        """
        return [
            {
                "type": tool.type,
                "function": {
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "parameters": tool.function.parameters,
                },
            }
            for tool in tools
        ]

    def _convert_tool_choice(self, choice: Any) -> Any:
        """Convert internal ToolChoice to OpenAI format.

        Args:
            choice: ToolChoice object or string like "auto" or "none".

        Returns:
            OpenAI-compatible tool_choice value.
        """
        if isinstance(choice, str):
            return choice
        # ToolChoice is a pydantic model
        return {
            "type": choice.type,
            "function": {"name": choice.function.name},
        }

    def _convert_response(self, response: Any) -> GenerationResponse:
        """Convert OpenAI response to internal GenerationResponse.

        Args:
            response: OpenAI ChatCompletion response object.

        Returns:
            GenerationResponse with converted data.
        """
        choices = []
        for idx, choice in enumerate(response.choices):
            msg = choice.message

            # Convert tool calls if present
            tool_calls = None
            if msg.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in msg.tool_calls
                ]

            message = Message(
                role=msg.role,
                content=msg.content or "",
                tool_calls=tool_calls,
            )

            choices.append(
                Choice(
                    index=idx,
                    message=message,
                    finish_reason=choice.finish_reason or "stop",
                )
            )

        usage = Usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )

        return GenerationResponse(
            id=response.id,
            model=response.model,
            choices=choices,
            usage=usage,
        )

    async def close(self) -> None:
        """Close the underlying client."""
        await self._client.close()
