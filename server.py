import asyncio
import logging

from workflows.server import WorkflowServer

# Import workflow của bạn
from workflow import ComplexQuestionWorkflow

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Khởi tạo WorkflowServer và expose ComplexQuestionWorkflow
    """
    # Tạo server
    server = WorkflowServer()

    # Khởi tạo workflow
    workflow = ComplexQuestionWorkflow(timeout=300)

    # Đăng ký workflow với server
    server.add_workflow(
        name="chat",
        workflow=workflow,
    )

    # Chạy server
    await server.serve(
        host="0.0.0.0",
        port=4040,
    )


if __name__ == "__main__":
    asyncio.run(main())
