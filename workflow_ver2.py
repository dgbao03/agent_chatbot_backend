from pydantic import BaseModel, Field
from typing import Literal, Optional
import json

class RouterOutput(BaseModel):
    intent: Literal["PPTX", "GENERAL"] = Field(
        description="Loại intent của người dùng: PPTX nếu muốn tạo slide/presentation, GENERAL cho các câu hỏi thông thường"
    )
    answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời cho câu hỏi của người dùng. Chỉ có giá trị khi intent là GENERAL, phải là null khi intent là PPTX"
    )

from dotenv import load_dotenv
load_dotenv()

from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer

llm = OpenAI(model="gpt-4o-mini")

from llama_index.core.tools import FunctionTool

def get_weather(city: str) -> str:
    return f"[WEATHER] {city}: 30°C, nắng nhẹ"

def get_stock_price(symbol: str) -> str:
    return f"[STOCK PRICE] {symbol}: 100$ (up 10%)"

tools = [
    FunctionTool.from_defaults(
        fn=get_weather,
        name="get_weather",
        description="Lấy thông tin thời tiết theo thành phố. Sử dụng khi người dùng hỏi về thời tiết của một thành phố cụ thể"
    ), 
    FunctionTool.from_defaults(
        fn=get_stock_price,
        name="get_stock_price",
        description="Lấy thông tin giá cổ phiếu theo mã cổ phiếu. Sử dụng khi người dùng hỏi về giá cổ phiếu của một công ty cụ thể"
    )
]

class RouterWorkflow(Workflow):

    @step
    async def route_and_answer(self, ctx: Context, ev: StartEvent) -> StopEvent:
        user_input = ev.input

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # Memory
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        if memory is None:
            memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
            await ctx.store.set("chat_history", memory)

        history = memory.get()

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "You are an AI router and answerer.\n\n"
                    "Decide intent and answer if needed.\n\n"
                    "INTENT RULES:\n"
                    "- If user wants slides / presentation / PPT → intent = PPTX\n"
                    "- Otherwise → intent = GENERAL\n\n"
                    "TOOL RULES:\n"
                    "- Use tools ONLY if intent is GENERAL and information is needed\n"
                    "- You may call multiple tools\n\n"
                    "FINAL RESPONSE RULES:\n"
                    "- When you are done, respond ONLY with valid JSON:\n"
                    "{\n"
                    '  "intent": "PPTX | GENERAL",\n'
                    '  "answer": "string | null"\n'
                    "}\n"
                    "- If intent is PPTX → answer MUST be null\n"
                    "- If intent is GENERAL → answer MUST be provided\n"
                    "- Do NOT include any extra text outside JSON"
                )
            )
        ]

        if history:
            messages.extend(history)

        messages.append(ChatMessage(role=MessageRole.USER, content=user_input))
        memory.put(ChatMessage(role=MessageRole.USER, content=user_input))

        # 🔁 Tool calling loop
        while True:
            resp = await llm.achat(messages, tools=openai_tools)

            # Append assistant message (tool_calls OR final)
            messages.append(resp.message)

            tool_calls = resp.message.additional_kwargs.get("tool_calls")
            if not tool_calls:
                break  # FINAL JSON expected

            # Execute ALL tool calls
            for call in tool_calls:
                name = call.function.name
                args_str = call.function.arguments
                
                # Parse arguments từ JSON string
                if isinstance(args_str, str):
                    args = json.loads(args_str)
                else:
                    args = args_str

                if name == "get_weather":
                    print(f"==== Calling get_weather with args: {args} ====")
                    result = get_weather(**args)
                elif name == "get_stock_price":
                    print(f"==== Calling get_stock_price with args: {args} ====")
                    result = get_stock_price(**args)
                else:
                    result = "Unknown tool"

                tool_msg = ChatMessage(
                    role=MessageRole.TOOL,
                    content=result,
                    additional_kwargs={"tool_call_id": call.id}
                )

                messages.append(tool_msg)

        await ctx.store.set("chat_history", memory)

        # 🔐 Parse + validate JSON output
        raw_text = resp.message.content.strip()

        print(f"==== Raw text: {raw_text} ====")

        try:
            output = RouterOutput.model_validate_json(raw_text)
        except Exception as e:
            raise ValueError(f"Invalid LLM JSON output:\n{raw_text}") from e

        if output.intent == "GENERAL":
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=output.answer
                )
            )
        else:
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="This is a PPTX Generation Mission"
                )
            )

        await ctx.store.set("chat_history", memory)

         # Log messages với format dễ đọc
        print("\n" + "="*60)
        print("MESSAGES:")
        print("="*60)
        for i, msg in enumerate(messages, 1):
            print(f"\n[{i}] {msg.role.value}:")
            if msg.content:
                # Truncate nếu quá dài
                content = msg.content
                if len(content) > 500:
                    content = content[:500] + "... [truncated]"
                print(f"    Content: {content}")
            if msg.additional_kwargs:
                tool_calls = msg.additional_kwargs.get("tool_calls")
                tool_call_id = msg.additional_kwargs.get("tool_call_id")
                if tool_calls:
                    print(f"    Tool Calls: {len(tool_calls)} call(s)")
                    for j, call in enumerate(tool_calls, 1):
                        print(f"      [{j}] {call.function.name}({call.function.arguments})")
                elif tool_call_id:
                    print(f"    Tool Call ID: {tool_call_id}")
        print("="*60 + "\n")

        # 🔀 Backend routing
        if output.intent == "PPTX":
            return StopEvent(result="This is a PPTX Generation Mission")
        else:
            return StopEvent(result=output.answer)


async def main():
    workflow = RouterWorkflow()
    ctx = Context(workflow)

    # Khởi tạo memory và set vào context
    memory = ChatMemoryBuffer.from_defaults(token_limit=10000)
    await ctx.store.set("chat_history", memory)

    # GENERAL
    result1 = await workflow.run(
        input="Thời tiết Hà Nội đang như nào?",
        ctx=ctx
    )
    print("\nResponse 1:", result1)

    result2 = await workflow.run(
        input="Giá cổ phiếu của Tesla đang như nào?",
        ctx=ctx
    )
    print("\nResponse 2:", result2)
    
    # chat_history
    chat_history: ChatMemoryBuffer = await ctx.store.get("chat_history")
    if chat_history:
        history_messages = chat_history.get()
        print("\n" + "="*60)
        print("CHAT HISTORY:")
        print("="*60)
        for i, msg in enumerate(history_messages, 1):
            print(f"\n[{i}] {msg.role.value}:")
            print(f"    {msg.content}")
        print("="*60 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
