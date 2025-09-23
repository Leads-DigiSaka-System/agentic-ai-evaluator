# file name: main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.router.upload import router as upload_router 
from src.router.search import router as search_router
from src.router.synthesizer import router as synthesize_router


import logging

app = FastAPI()
# Initialize FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(synthesize_router,prefix="/api", tags=["synthesize"])


# Health check endpoint

@app.get("/")
def root():
    return {"message": "Agentic AI Evaluation API is running 🚀"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
# Run the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("survey_app")
#  Run app with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)