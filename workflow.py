import logging
from pydantic import BaseModel, Field
from typing import List, Literal
from dotenv import load_dotenv
from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    step,
    Event,
    Workflow,
    Context
)
from llama_index.core.prompts.base import PromptTemplate
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.agent.workflow.workflow_events import ToolCall, ToolCallResult
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from memory import MemoryManager

# Import tools
from tools.web_search_tool import web_search_tool
from tools.weather_tool import get_weather
from tools.stock_price_tool import get_stock_price

# Load environment variables trước khi khởi tạo LLM
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize memory manager
memory_manager = MemoryManager()


class AtomicTask(BaseModel):
    """
    Một task đơn lẻ trong kế hoạch
    
    Attributes:
        task_id: ID duy nhất của task
        task_rationale: Giải thích ngắn gọn vì sao task này liên quan đến mục tiêu
        status: Trạng thái của task (created, completed, failed)
        task_output: Kết quả của task sau khi thực hiện
    """
    task_id: str = Field(description="ID của task")
    task_rationale: str = Field(
        description="Giải thích ngắn gọn vì sao task lại liên quan đến mục tiêu của câu hỏi"
    )
    status: Literal["created", "completed", "failed"] = Field(
        default="created",
        description="Trạng thái của task"
    )
    task_output: str = Field(
        default="",
        description="Kết quả của task sau khi thực hiện"
    )


class TaskPlan(BaseModel):
    """
    Kế hoạch bao gồm danh sách các task để giải quyết câu hỏi của người dùng
    
    Attributes:
        question: Câu hỏi gốc của người dùng
        tasks: Danh sách các task cần thực hiện theo thứ tự
    """
    question: str = Field(description="Câu hỏi của người dùng")
    tasks: List[AtomicTask] = Field(
        description="Danh sách các task cần thực hiện để trả lời câu hỏi"
    )


# Prompt Templates
PLAN_GENERATION_TMPL = """
Phân tích câu hỏi của người dùng và tạo ra một kế hoạch gồm các task để trả lời câu hỏi đó.

Câu hỏi của người dùng: {question}

CÁC TOOLS CÓ SẴN:
- web_search_tool(query): Tìm kiếm thông tin trên web. Input: query (câu truy vấn tìm kiếm). Output: Kết quả tìm kiếm từ nhiều nguồn.
- get_weather(location, units): Lấy thông tin thời tiết. Input: location (địa điểm, ví dụ "Hanoi, Vietnam"), units (đơn vị: "metric" hoặc "imperial", mặc định "metric"). Output: Thông tin thời tiết chi tiết.
- get_stock_price(symbol): Lấy giá cổ phiếu hiện tại. Input: symbol (mã chứng khoán, ví dụ "AAPL", "GOOGL", "MSFT"). Output: Thông tin giá cổ phiếu bao gồm giá hiện tại, thay đổi, phần trăm thay đổi, giá cao/thấp trong ngày.

Các nguyên tắc khi tạo Plan:
- Số lượng Task để giải quyết vấn đề trong 1 Plan là tối ưu nhất. Tối thiểu là 1 Task
- Plan không chứa các vòng lặp
- Các task nên được thực hiện theo thứ tự tuần tự

Các nguyên tắc khi tạo Task:
- Task có mục tiêu cụ thể và rõ ràng
- Task có độ độc lập cao nhất có thể
- Mỗi task cần có task_id duy nhất (ví dụ: task_1, task_2, ...)
- Khi mới tạo, Task sẽ có status là "created"
- task_rationale phải giải thích rõ ràng tại sao task này cần thiết để trả lời câu hỏi
"""

SYSTEM_PROMPT_TMPL = """Bạn là một AI Assistant thông minh và hữu ích. Hãy trả lời các câu hỏi một cách chi tiết và chính xác."""

SUMMARY_PROMPT_TMPL = """
Dựa trên toàn bộ cuộc trò chuyện và kết quả của các task đã thực hiện, hãy tóm tắt và đưa ra câu trả lời cuối cùng cho câu hỏi gần nhất được đặt ra: {question}

QUAN TRỌNG:
- Bạn đã có thông tin từ các task đã thực hiện trong chat history
- Hãy sử dụng thông tin đó để trả lời câu hỏi

CONSTRAINT RULES:
- Tập trung vào câu hỏi để đưa ra câu trả lời ngắn gọn và đầy đủ
- Không trả lời những thông tin không liên quan hoặc bịa đặt
- Tổng hợp thông tin từ các task đã thực hiện
"""

# Initialize prompts
PLAN_GENERATION_PROMPT = PromptTemplate(
    template=PLAN_GENERATION_TMPL, 
    prompt_type="plan_generation"
)

SYSTEM_PROMPT = PromptTemplate(
    template=SYSTEM_PROMPT_TMPL, 
    prompt_type="system_prompt"
)

# Initialize LLM instances
llm = OpenAI(model="gpt-4o-mini")
plan_agent = llm.as_structured_llm(output_cls=TaskPlan)

system_messages = [
    ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT.format())
]

# Tạo execution tools list
execution_tools = [
    web_search_tool,
    get_weather,
    get_stock_price,
]

# Tạo execution agent với tools (AgentWorkflow)
execution_agent = AgentWorkflow.from_tools_or_functions(
    tools_or_functions=execution_tools,
    llm=llm,
    system_prompt=SYSTEM_PROMPT_TMPL,
    verbose=True,
    timeout=300,
)

# Helper function để chat với LLM (dùng cho finalize step)
async def chat_with_llm(message: str, chat_history: List[ChatMessage] = None) -> str:
    """
    Chat với LLM trực tiếp
    
    Args:
        message: User message
        chat_history: Chat history (optional)
        
    Returns:
        str: LLM response content (không có prefix)
    """
    if chat_history is None:
        chat_history = []
    
    # Tạo messages list với system prompt và chat history
    messages = system_messages + chat_history + [
        ChatMessage(role=MessageRole.USER, content=message)
    ]
    
    # Chat với LLM
    response = await llm.achat(messages)
    
    # Lấy content từ response, không convert toàn bộ object
    if hasattr(response, 'message') and hasattr(response.message, 'content'):
        result = str(response.message.content)
    elif hasattr(response, 'content'):
        result = str(response.content)
    else:
        # Fallback: convert to string và loại bỏ prefix nếu có
        result = str(response)
    
    # Loại bỏ prefix "assistant: " nếu có
    if result.startswith("assistant: "):
        result = result[len("assistant: "):].strip()
    
    return result


# Helper function để execute task với FunctionAgent có tools
async def execute_task_with_agent(
    task_rationale: str,
    chat_history: List[ChatMessage]
) -> str:
    """
    Chạy task với FunctionAgent có tools
    
    Args:
        task_rationale: Task rationale từ plan
        chat_history: Chat history hiện tại
        
    Returns:
        str: Final response từ agent
    """
    try:
        # Tạo memory từ chat_history
        memory = ChatMemoryBuffer.from_defaults()
        for msg in chat_history:
            memory.put(msg)
        
        # Chạy agent với task rationale
        # AgentWorkflow.run() trả về WorkflowHandler (là awaitable)
        handler = execution_agent.run(
            user_msg=task_rationale,
            memory=memory,
            max_iterations=5,  # Giới hạn 5 lần gọi tool
        )
        
        # Stream events để log tool calls
        tool_call_count = 0
        async for event in handler.stream_events():
            if isinstance(event, ToolCall):
                tool_call_count += 1
                logger.info(f"Tool Call #{tool_call_count}: {event.tool_name}")
                logger.info(f"Arguments: {event.tool_kwargs}")
            elif isinstance(event, ToolCallResult):
                tool_output = event.tool_output.content
                # Truncate nếu quá dài
                if len(tool_output) > 1000:
                    tool_output_preview = tool_output[:1000] + "..."
                else:
                    tool_output_preview = tool_output
                logger.info(f"Tool Result: {event.tool_name}")
                logger.info(f"Output: {tool_output_preview}")
                if event.tool_output.is_error:
                    logger.warning(f"Tool returned error!")
        
        # Await handler để lấy final response
        result = await handler
        
        if tool_call_count > 0:
            logger.info(f"  📊 Total tool calls: {tool_call_count}")
        
        # Xử lý result và loại bỏ prefix nếu có
        if isinstance(result, str):
            # Loại bỏ prefix "assistant: " nếu có
            if result.startswith("assistant: "):
                result = result[len("assistant: "):].strip()
            return result
        elif hasattr(result, 'content'):
            # Nếu là ChatMessage object
            content = str(result.content)
            if content.startswith("assistant: "):
                content = content[len("assistant: "):].strip()
            return content
        else:
            # Fallback
            result_str = str(result)
            if result_str.startswith("assistant: "):
                result_str = result_str[len("assistant: "):].strip()
            return result_str
            
    except Exception as e:
        error_msg = f"Lỗi khi chạy agent: {str(e)}"
        logger.error(error_msg, exc_info=True)  # Thêm exc_info để debug
        return error_msg


# Events
class PlanGeneratedEvent(Event):
    """Event khi plan đã được tạo"""
    plan: TaskPlan


class PlanExecutedEvent(Event):
    """Event khi tất cả tasks đã được thực hiện"""
    plan: TaskPlan


class ComplexQuestionWorkflow(Workflow):
    """Workflow xử lý câu hỏi phức tạp với pattern Plan-and-Execute"""
    
    @step
    async def plan_step(self, ctx: Context, event: StartEvent) -> PlanGeneratedEvent:
        """
        Bước 1: Planning - Phân tích câu hỏi và tạo kế hoạch
        
        Args:
            ctx: Workflow context
            event: StartEvent chứa user_input
            
        Returns:
            PlanGeneratedEvent: Event chứa TaskPlan đã được tạo
        """
        logger.info("Step 1: Generating plan...")
        
        # Lấy user input
        question = event.user_input
        logger.info(f"Question: {question}")
        
        # Load chat history từ file và inject vào Context
        chat_history = memory_manager.load_history()
        await ctx.store.set("chat_history", chat_history)
        await ctx.store.set("question", question)
        
        # Tạo prompt cho planning
        prompt = PLAN_GENERATION_PROMPT.format(question=question)
        
        # Generate plan bằng Structured LLM
        messages = [
            ChatMessage(role=MessageRole.USER, content=prompt)
        ]
        response = plan_agent.chat(messages)
        plan_obj = response.raw
        
        # Log plan information
        logger.info(f"Plan generated with {len(plan_obj.tasks)} tasks:")
        for task in plan_obj.tasks:
            logger.info(f"Task {task.task_id}: {task.task_rationale}")
        
        # Lưu plan vào Context
        await ctx.store.set("plan", plan_obj)
        
        return PlanGeneratedEvent(plan=plan_obj)
    
    @step
    async def execute_step(self, ctx: Context, event: PlanGeneratedEvent) -> PlanExecutedEvent:
        """
        Bước 2: Execute - Thực hiện từng task trong plan
        
        Args:
            ctx: Workflow context
            event: PlanGeneratedEvent chứa TaskPlan
            
        Returns:
            PlanExecutedEvent: Event chứa TaskPlan đã được thực hiện xong
        """
        logger.info("Step 2: Executing the plan...")
        
        plan = event.plan
        chat_history = await ctx.store.get("chat_history", default=[])
        
        # Thực thi từng task trong plan
        for task in plan.tasks:
            logger.info(f"Đang thực hiện task: {task.task_id}")
            logger.info(f"Task rationale: {task.task_rationale}")
            
            try:
                # Thực thi task bằng FunctionAgent với tools
                task_output = await execute_task_with_agent(
                    task_rationale=task.task_rationale,
                    chat_history=chat_history
                )
                
                # Cập nhật task output và status
                task.task_output = str(task_output)
                task.status = "completed"
                
                # Append messages vào chat_history
                chat_history.append(
                    ChatMessage(role=MessageRole.USER, content=task.task_rationale)
                )
                chat_history.append(
                    ChatMessage(role=MessageRole.ASSISTANT, content=task.task_output)
                )
                
                logger.info(f"Task {task.task_id} completed")
                
            except Exception as e:
                logger.error(f"  Task {task.task_id} failed: {e}")
                task.status = "failed"
                task.task_output = f"Error: {str(e)}"
        
        # Lưu updated chat_history và plan vào Context
        await ctx.store.set("chat_history", chat_history)
        await ctx.store.set("plan", plan)
        
        return PlanExecutedEvent(plan=plan)
    
    @step
    async def finalize_step(self, ctx: Context, event: PlanExecutedEvent) -> StopEvent:
        """
        Bước 3: Finalize - Tổng hợp kết quả và tạo câu trả lời cuối cùng
        
        Args:
            ctx: Workflow context
            event: PlanExecutedEvent chứa TaskPlan đã completed
            
        Returns:
            StopEvent: Event chứa final response
        """
        logger.info("Step 3: Finalizing response...")
        
        # Lấy thông tin từ Context
        question = await ctx.store.get("question", default="")
        chat_history = await ctx.store.get("chat_history", default=[])
        plan = event.plan
        
        # Tạo prompt cho summarization
        summary_message = SUMMARY_PROMPT_TMPL.format(question=question)
        
        # Generate final response
        final_response = await chat_with_llm(
            message=summary_message,
            chat_history=chat_history
        )
        
        # Append final response vào chat_history
        chat_history.append(
            ChatMessage(role=MessageRole.USER, content=summary_message)
        )
        chat_history.append(
            ChatMessage(role=MessageRole.ASSISTANT, content=str(final_response))
        )
        
        # Lưu updated chat_history vào Context và file
        await ctx.store.set("chat_history", chat_history)
        memory_manager.save_history(chat_history)
        
        logger.info(f"Final response generated: {final_response}")
        
        return StopEvent(result=str(final_response))


async def main():
    """
    Hàm main để test workflow trực tiếp, không cần qua API
    """
    import asyncio
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Tạo workflow instance
    workflow = ComplexQuestionWorkflow(timeout=300)
    
    # Test question
    question = "CR7 là ai?"
    
    logger.info("=" * 50)
    logger.info("Starting workflow test...")
    logger.info(f"Question: {question}")
    logger.info("=" * 50)
    
    # Run workflow
    result = await workflow.run(user_input=question)
    
    # Print result
    logger.info("=" * 50)
    logger.info("Workflow completed!")
    logger.info(f"Final response: {result}")
    logger.info("=" * 50)
    
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

