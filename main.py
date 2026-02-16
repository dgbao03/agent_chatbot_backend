"""
FastAPI Application Entry Point
TODO: Implement FastAPI app with routers and middleware
"""
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# import uvicorn

# # Import routers (when implemented)
# # from app.routers import auth, chat, conversations, presentations, user_facts

# app = FastAPI(
#     title="Agent Chat API",
#     description="AI Chat application with presentation generation",
#     version="2.0.0"
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5173",
#         "http://localhost:5174"
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Register routers (when implemented)
# # app.include_router(auth.router)
# # app.include_router(chat.router)
# # app.include_router(conversations.router)
# # app.include_router(presentations.router)
# # app.include_router(user_facts.router)

# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {"status": "ok", "version": "2.0.0"}

# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=4040,
#         reload=True
#     )
