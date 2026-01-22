import asyncio
import logging

from workflows.server import WorkflowServer

# Import workflow của bạn
from workflow import RouterWorkflow

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress CancelledError từ asyncio logs (khi cancel workflow)
class CancelledErrorFilter(logging.Filter):
    def filter(self, record):
        # Bỏ qua log nếu có CancelledError trong exception info
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type is asyncio.CancelledError:
                return False
        # Bỏ qua log nếu message chứa "CancelledError" hoặc "cancelled"
        if record.getMessage().find('CancelledError') != -1 or \
           record.getMessage().find('cancelled') != -1:
            return False
        return True

# Áp dụng filter cho asyncio logger
logging.getLogger('asyncio').addFilter(CancelledErrorFilter())
# Áp dụng filter cho root logger để catch tất cả
logging.getLogger().addFilter(CancelledErrorFilter())


async def main():
    """
    Khởi tạo WorkflowServer và expose RouterWorkflow
    """
    # Tạo server
    server = WorkflowServer()

    # Khởi tạo workflow
    workflow = RouterWorkflow()

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

