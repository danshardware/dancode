from dataclasses import dataclass
from typing import Callable
import boto3
from botocore.config import Config
import inspect
import json

_BEDROCK_CONFIG = Config(
    read_timeout=300,        # large model responses can be slow
    connect_timeout=10,
    retries={"max_attempts": 5, "mode": "adaptive"},
)

# Conversation class for interacting with various models via AWS Bedrock.

# TODO:
# - Add support for image files
class BedrockTool:
    """Wraps a function to make it compatible with AWS Bedrock's tool use API.
    
    This class converts a Python function into a Bedrock-compatible tool by generating
    the necessary tool specification (toolSpec) that describes the function's name,
    description, and input schema for the Bedrock API.
    
    Attributes:
        name (str): The name of the tool (from the function name).
        description (str): The description of the tool (from the function's docstring).
        func (Callable): The underlying Python function being wrapped.
        tool_spec (dict): The Bedrock tool specification containing name, description, and input schema.
    """
    def __init__(self, func: Callable, tool_spec: dict | None = None):
        """Initialize a BedrockTool wrapper for a function.
        
        Parameters:
            func (Callable): The function to wrap as a Bedrock tool.
            tool_spec (dict | None): Optional pre-defined tool specification. If not provided,
                                    it will be generated automatically from the function signature.
        """
        self.name = func.__name__
        self.description = func.__doc__ or ""
        self.func = func
        self.__name__ = func.__name__
        self.tool_spec = tool_spec if tool_spec else self.to_bedrock_spec()

    def __call__(self, *args, **kwargs):
        """Make the tool callable by delegating to the wrapped function.
        
        Returns:
            The result of calling the wrapped function with the provided arguments.
        """
        return self.func(*args, **kwargs)

    def to_bedrock_spec(self):
        """Generate the toolSpec for the Bedrock API.
        
        Inspects the wrapped function's signature and type annotations to generate
        a JSON schema that describes the function's input parameters. This schema
        is used by AWS Bedrock to understand how to invoke the tool.
        
        Returns:
            dict: A dictionary containing the tool specification with keys:
                - 'name': The tool name
                - 'description': The tool description from the function's docstring
                - 'inputSchema': JSON schema describing the input parameters.
        """
        signature = inspect.signature(self.func)
        parameters = signature.parameters
        input_schema = {
            "json": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

        for param_name, param in parameters.items():
            param_type = self.func.__annotations__.get(param_name, "string")
            param_description = f"Parameter '{param_name}'"
            if param.default is not inspect.Parameter.empty:
                param_description += f" (default: {param.default})"
            else:
                input_schema["json"]["required"].append(param_name)

            input_schema["json"]["properties"][param_name] = {
                "type": self._map_python_type_to_json(param_type),
                "description": param_description
            }

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema
        }

    def _map_python_type_to_json(self, python_type):
        """Map Python types to JSON schema types.
        
        Converts Python type annotations (str, int, float, bool, dict, list) to their
        corresponding JSON schema type strings for use in the Bedrock API.
        
        Parameters:
            python_type: A Python type annotation.
            
        Returns:
            str: The corresponding JSON schema type string. Defaults to 'string' if
                 the type is not in the mapping.
        """
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array"
        }
        return type_mapping.get(python_type, "string")

def bedrock_tool(tool_spec: dict | None = None, tool_list: list[BedrockTool] | None = None) -> Callable:
    """Decorator to register a function as a Bedrock tool.
    
    Converts a function into a BedrockTool instance and optionally adds it to a tool list.
    This decorator enables functions to be used as tools in Bedrock conversations.
    
    Parameters:
        tool_spec (dict | None): Optional pre-defined tool specification. If not provided,
                                it will be auto-generated from the function signature.
        tool_list (list[BedrockTool] | None): Optional list to accumulate registered tools.
                                              If provided, the tool will be appended to this list.
    
    Returns:
        Callable: A decorator function that wraps the target function and returns a BedrockTool.
        
    Raises:
        ValueError: If the decorated object is not callable.
        
    Example:
        >>> tools = []
        >>> @bedrock_tool(tool_list=tools)
        ... def multiply(a: float, b: float) -> float:
        ...     \"\"\"Multiply two numbers.\"\"\"
        ...     return a * b
        >>> len(tools)
        1
    """
    def bedrock_tool_wrapper(func: Callable) -> BedrockTool:
        if not callable(func):
            raise ValueError("Function must be callable")
        tool = BedrockTool(func, tool_spec=tool_spec)
        if tool_list is not None:
            tool_list.append(tool)
        return tool
    
    return bedrock_tool_wrapper

@dataclass
class Message:
    """Represents a message in a Bedrock conversation.
    
    Messages can contain either text content or complex content structures (e.g., tool use,
    tool results) as required by the Bedrock API. This class provides a convenient wrapper
    for both simple text messages and complex content structures.
    
    Attributes:
        role (str): The role of the message sender ('user' or 'assistant').
        content (list[dict[str, object]]): List of content dictionaries following Bedrock's message format.
        text (str | None): Optional convenience field for simple text-only messages.
    """
    role: str
    content: list[dict[str, object]]  # List of content dicts
    text: str | None = None  # Optional text field for convenience
    def __init__(self, role: str, text: str | None = None, content: list[dict[str, object]] | None = None):
        """Initialize a Message instance.
        
        Parameters:
            role (str): The role of the message sender ('user' or 'assistant').
            text (str | None): Simple text content. Either text or content must be provided.
            content (list[dict[str, object]] | None): Complex content structure. Either text or content must be provided.
            
        Raises:
            ValueError: If neither text nor content is provided.
        """
        self.role = role
        if content is None and text is None:
            raise ValueError("Either text or content must be provided")
        if content is None:
            self.content = [{"text": text}]
        else:
            self.content = content
        self.text = text
    def __str__(self):
        """Return a human-readable string representation of the message.
        
        Returns:
            str: Formatted message showing the role and content (text or JSON).
        """
        if not self.content[-1].get('text') is None:
            return f"{self.role}: {self.content[-1]['text']}"
        return f"{self.role}: {json.dumps(self.content[-1], indent=2)}"
    def to_dict(self):  # Renamed from __dict__
        """Convert the message to a dictionary format compatible with Bedrock API.
        
        Returns:
            dict: Dictionary with 'role' and 'content' keys for Bedrock API compatibility.
        """
        return {
            "role": self.role,
            "content": self.content
        }


# ---------------------------------------------------------------------------
# Conversation-slicing helpers (used by call_model)
# ---------------------------------------------------------------------------

# Bedrock requires toolConfig to be present whenever the conversation contains
# toolUse or toolResult blocks.  When a block has no real tools we still need
# to satisfy this constraint.  We include a sentinel no-op tool so the API
# call succeeds; the model will not call it because the system prompt never
# mentions it.
_SENTINEL_TOOL_CONFIG = {
    "tools": [{
        "toolSpec": {
            "name": "_noop",
            "description": "Internal placeholder tool. Do not call this tool.",
            "inputSchema": {
                "json": {"type": "object", "properties": {}, "required": []},
            },
        }
    }]
}


def _conversation_has_tool_blocks(conversation: list[dict]) -> bool:
    """Return True if any message dict contains a toolUse or toolResult block."""
    for msg in conversation:
        for item in msg.get("content", []):
            if "toolUse" in item or "toolResult" in item:
                return True
    return False

def _find_tool_free_boundary(turns: list, gap: int = 4) -> int:
    """Return the first index of a run of `gap` consecutive turns with no
    toolUse or toolResult content.  Falls back to 0 (keep everything) when
    no such run exists."""
    def _has_tool(msg) -> bool:
        return any(
            "toolUse" in item or "toolResult" in item
            for item in (msg.content or [])
        )
    for i in range(max(0, len(turns) - gap + 1)):
        if not any(_has_tool(turns[i + j]) for j in range(gap)):
            return i
    return 0


def _align_tail(turns: list, n: int) -> list:
    """Return the last n turns, advancing the start index forward past any
    leading toolResult turns to avoid sending an orphaned tool-result to
    Bedrock without its paired toolUse."""
    start = max(0, len(turns) - n)
    while start < len(turns) and any(
        "toolResult" in item for item in turns[start].content
    ):
        start += 1
    return turns[start:]


class Conversation:
    """Manages a multi-turn conversation with AWS Bedrock LLM models.
    
    This class handles the full lifecycle of a conversation with an LLM including:
    - Maintaining conversation history
    - Configuring system prompts and model parameters
    - Managing tool registration and invocation
    - Calling the Bedrock API and handling tool use responses
    - Tracking token usage
    
    Attributes:
        model_id (str): The ID of the Bedrock model to use.
        system_prompts (list[dict]): List of system prompt dictionaries.
        conversation (list[Message]): History of messages in the conversation.
        tools (dict): Dictionary mapping tool names to BedrockTool instances.
        inference_config (dict): Model inference configuration (temperature, maxTokens, etc.).
        input_tokens (int): Total input tokens used in the conversation.
        output_tokens (int): Total output tokens used in the conversation.
        total_tokens (int): Total tokens used in the conversation.
    """
    def __init__ (self, model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
                  system_prompts: str | list[str] = [], 
                  user_prompt: str | None = None, 
                  model_config: dict = {},
                  tools: list[BedrockTool] | None = None):
        """Initialize a Conversation instance.
        
        Parameters:
            model_id (str): The ID of the Bedrock model to use. Defaults to Claude 3.7 Sonnet.
            system_prompts (str | list[str]): System prompt(s) to guide the model's behavior.
                                              Can be a single string or list of strings.
            user_prompt (str | None): Initial user message to start the conversation.
            model_config (dict): Configuration dictionary for the model. Supports keys like
                                'temperature', 'maxTokens', and other model-specific settings.
            tools (list[BedrockTool] | None): List of tools to make available to the model.
        """
        if system_prompts is None:
            self.system_prompts = [{ "text": "You are a helpful assistant." }]
        else :
            self.system_prompts = self.system_prompt(system_prompts)
        
        self.conversation: list[Message] = []
        if not user_prompt is None:
            self.add_conversation_turn("user", user_prompt)
        self.model_id = model_id
        
        self.additional_model_fields  = model_config if model_config else {}
        self.inference_config = {}
        for field in ["temperature", "maxTokens", ]:
            if field in self.additional_model_fields:
                self.inference_config[field] = self.additional_model_fields[field]
                del self.additional_model_fields[field]
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.tools = {tool.name: tool for tool in (tools or [])}
    
    def system_prompt(self, system_prompt: str | list[str]):
        """Convert system prompt string(s) to the Bedrock API format.
        
        Parameters:
            system_prompt (str | list[str]): One or more system prompts as strings.
            
        Returns:
            list[dict]: List of prompt dictionaries in Bedrock format (each with a 'text' key).
            
        Raises:
            ValueError: If system_prompt is not a string or list of strings.
        """
        if isinstance(system_prompt, str):
            return [{"text": system_prompt}]
        elif isinstance(system_prompt, list):
            return [{"text": p} for p in system_prompt]
        else:
            raise ValueError("System prompt must be a string or a list of strings.")
    
    def add_conversation_turn(self, role, text):
        """Add a new message to the conversation.
        
        Parameters:
            role (str): The role of the message sender ('user' or 'assistant').
            text (str): The text content of the message.
            
        Returns:
            list[Message]: The updated conversation history.
        """
        message = Message(role, text)
        self.conversation.append(message)
        return self.conversation
    
    def generate(self, text) -> str:
        """Generate a response from the model based on the conversation history.
        
        Adds the user's text to the conversation, calls the model, handles any tool use
        requests, and returns the model's response.
        
        Parameters:
            text (str): The user's message to send to the model.
            
        Returns:
            str: The model's response text.
        """
        self.add_conversation_turn("user", text)
        # Here you would typically call the model to get a response based on the conversation history.
        # This is a placeholder for the actual model call.
        role, reply = self.call_model()
        self.add_conversation_turn(role, reply)
        return reply

    def register_tool(self, tool: BedrockTool):
        """Register a new tool with the conversation.
        
        Parameters:
            tool (BedrockTool): The tool to register, making it available for the model to use.
        """
        self.tools[tool.name] = tool

    def invoke_tool(self, tool_name: str, *args, **kwargs):
        """Invoke a registered tool by name.
        
        Parameters:
            tool_name (str): The name of the tool to invoke.
            *args: Positional arguments to pass to the tool.
            **kwargs: Keyword arguments to pass to the tool.
            
        Returns:
            The result of executing the tool.
            
        Raises:
            ValueError: If the tool is not registered.
        """
        if tool_name not in self.tools:
            available = list(self.tools.keys()) if self.tools else []
            raise ValueError(
                f"Tool '{tool_name}' is not available in the current phase. "
                f"Available tools: {available}. "
                "If you need write_file or replace_in_file, respond with action: apply to enter the apply phase."
            )
        return self.tools[tool_name](*args, **kwargs)

    _MAX_TOOL_CALLS_PER_TURN = 40

    def call_model(self, messages: list[Message] | None = None, 
                   tool_event_log: list | None = None,
                   tool_callback=None, _tool_call_count: list[int] | None = None,
                   context_window: int | None = None, include_tools: bool = True) -> tuple[str, str]:
        """Call the AWS Bedrock API with the current conversation.
        
        Makes an API call to the configured Bedrock model, handling tool use if the model
        requests it. Automatically retries without tool configuration if the model doesn't
        support it, and recursively handles tool invocation until the model provides a
        final response.
        
        Parameters:
            messages (list[Message] | None): Optional specific messages to use instead of
                                             the conversation history. Used internally for
                                             recursive tool handling.
        
        Returns:
            tuple[str, str]: A tuple of (role, response_text) from the model's final response.
            
        Raises:
            Various AWS Bedrock exceptions if the API call fails.
        """
        _is_top_level = _tool_call_count is None
        if _tool_call_count is None:
            _tool_call_count = [0]
        bedrock_client = boto3.client(service_name='bedrock-runtime', config=_BEDROCK_CONFIG)
        if messages is None:
            turns = self.conversation
            if _is_top_level:
                if not include_tools:
                    boundary = _find_tool_free_boundary(turns)
                    turns = turns[boundary:]
                if context_window is not None and context_window < len(turns):
                    turns = _align_tail(turns, context_window)
            conversation = [m.to_dict() for m in turns]
        else:
            conversation = [m.to_dict() for m in messages]
        
        # Prepare tool configuration.
        # If this block has real tools, use them.  If it has none but the
        # conversation already contains toolUse/toolResult blocks, Bedrock
        # still requires toolConfig to be present — supply the sentinel so
        # the call succeeds without stripping valuable conversation history.
        if self.tools:
            effective_tool_config = {
                "tools": [{"toolSpec": tool.tool_spec} for tool in self.tools.values()]
            }
        elif _conversation_has_tool_blocks(conversation):
            effective_tool_config = _SENTINEL_TOOL_CONFIG
        else:
            effective_tool_config = None

        # Make the API call
        try:
            # Make the API call with toolConfig
            response = bedrock_client.converse(
                modelId=self.model_id,
                messages=conversation,
                system=self.system_prompts,
                inferenceConfig=self.inference_config,
                **({"toolConfig": effective_tool_config} if effective_tool_config else {}),
                additionalModelRequestFields={
                    **self.additional_model_fields,
                }
            )
        except bedrock_client.exceptions.ValidationException as e:
            if "toolConfig" in str(e):
                print(f"Tool use not supported by model {self.model_id}. Retrying without toolConfig.")
                # Retry without toolConfig if the model does not support it
                response = bedrock_client.converse(
                    modelId=self.model_id,
                    messages=conversation,
                    system=self.system_prompts,
                    inferenceConfig=self.inference_config,
                    additionalModelRequestFields=self.additional_model_fields
                )
            else:
                raise

        # Handle tool use
        if response.get('stopReason') == 'tool_use':
            tool_requests = response['output']['message']['content']
            for tool_request in tool_requests:
                if 'toolUse' in tool_request:
                    tool = tool_request['toolUse']
                    tool_name = tool['name']
                    tool_input = tool['input']
                    from rich.console import Console as _RC
                    _RC().print(f"  [dim]🔧 tool use → {tool_name}[/dim]")
                    tool_use_id = tool['toolUseId']

                    # Call the tool
                    try:
                        tool_result = self.invoke_tool(tool_name, **tool_input)
                    except Exception as e:
                        print(f"Error invoking tool {tool_name}: {e}")
                        tool_result = f"Error: {e}"

                    _tool_call_count[0] += 1
                    if _tool_call_count[0] > self._MAX_TOOL_CALLS_PER_TURN:
                        return ("assistant", f"[SYSTEM] Tool call limit ({self._MAX_TOOL_CALLS_PER_TURN}) exceeded in one turn. Stopping tool use and returning.")

                    tc_record = {
                        "tool": tool_name,
                        "input": tool_input,
                        "result": str(tool_result)[:500],
                    }
                    if tool_event_log is not None:
                        tool_event_log.append(tc_record)
                    if tool_callback is not None:
                        tool_callback(tc_record)

                    # Bedrock requires json content to be a dict; use text for strings
                    if isinstance(tool_result, dict):
                        result_content = [{"json": tool_result}]
                    else:
                        result_content = [{"text": str(tool_result)}]
                    tool_use_message = Message(
                        role="assistant",
                        content=[{"toolUse": tool}]
                    )
                    if not messages is None:
                        messages.append(tool_use_message)
                    else:
                        self.conversation.append(tool_use_message)
                    
                    # Send the tool result back to the model
                    tool_result_message = {
                        "role": "user",
                        "content": [{
                            "toolResult": {
                                "toolUseId": tool_use_id,
                                "content": result_content
                            }
                        }]
                    }
                    # Convert tool result message to a Message object
                    tool_result_message_obj = Message(
                        role="user",
                        content=tool_result_message["content"]
                    )
                    if not messages is None:
                        messages.append(tool_result_message_obj)
                    else:
                        self.conversation.append(tool_result_message_obj)

                    # call ourselves again with the updated conversation
                    return self.call_model(tool_event_log=tool_event_log, tool_callback=tool_callback, _tool_call_count=_tool_call_count)

        # Continue the conversation
        token_usage = response['usage']
        self.input_tokens += token_usage['inputTokens']
        self.output_tokens += token_usage['outputTokens']
        self.total_tokens += token_usage['totalTokens']
        content = response['output']['message'].get('content', [])
        text_parts = [item['text'] for item in content if isinstance(item, dict) and 'text' in item]
        return (response['output']['message']['role'], '\n'.join(text_parts))
    def get_last_message(self) -> Message | None:
        """Get the last message in the conversation.
        
        Returns:
            Message | None: The last message if the conversation is not empty, None otherwise.
        """
        if self.conversation:
            return self.conversation[-1]
        else:
            return None
    def get_last_message_text(self) -> str | None:
        """Get the text content of the last message in the conversation.
        
        Returns:
            str | None: The text of the last message if available, None if the conversation
                       is empty, or a JSON representation if the message contains non-text content.
        """
        last_message = self.get_last_message()
        if last_message:
            return str(last_message.content[0]['text']) if 'text' in last_message.content[0] else json.dumps(last_message.content)
        else:
            return None
        
    def __str__(self):
        """Return a human-readable string representation of the entire conversation.
        
        Returns:
            str: Formatted conversation showing the model ID and all messages.
        """
        return f"Conversation with model {self.model_id}:\n  " +\
            "\n  ".join([f"{msg.role}: {msg}" for msg in self.conversation])
    
if __name__ == "__main__":
    conversation = Conversation()
    print("Starting conversation...")
    response = conversation.generate("Hello, how are you?")
    print(f"Input tokens: {conversation.input_tokens}")
    print(f"Output tokens: {conversation.output_tokens}")
    print(f"Total tokens: {conversation.total_tokens}")
    print(conversation)
    
    all_tools: list[BedrockTool] = []
    @bedrock_tool(tool_list=all_tools)
    def multiply(a: float, b: float) -> dict[str, float]:
        """Multiply two numbers."""
        print(f"Multiplying {a} and {b}")
        return {"result": a * b}

    conv2 = Conversation(tools=all_tools)
    response = conv2.generate("What is 6.5 multiplied by 4?")
    print(conv2)
    print("Response:", response)