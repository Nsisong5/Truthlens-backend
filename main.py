from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes import users, verify_article

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TruthLens API",
    description="Backend API for TruthLens application",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:5173"],  # React default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(verify_article.router, prefix="/api/verify", tags=["verify"])

@app.get("/")
async def root():
    return {"message": "Welcome to TruthLens API"}
