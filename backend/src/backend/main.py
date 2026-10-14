from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import uvicorn
import shutil
import os

from . import models, database

app = FastAPI(title="Buy you Before - Room Simulator")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "Welcome to Buy you Before Room Simulator API"}

@app.post("/simulate")
async def create_simulation(
    file: Optional[UploadFile] = File(None),
    link: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    if not file and not link:
        raise HTTPException(status_code=400, detail="Either file or link must be provided")
    
    file_path = None
    if file:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    # Create record in DB
    new_sim = models.RoomSimulation(
        file_path=file_path,
        external_link=link,
        status="processing"
    )
    db.add(new_sim)
    db.commit()
    db.refresh(new_sim)
    
    # Placeholder for vLLM and Shapely processing
    # In a real microservice, this would trigger a background task or Dapr pub/sub
    print(f"Processing simulation {new_sim.id} with vLLM and Shapely...")
    
    return {
        "id": new_sim.id,
        "status": new_sim.status,
        "message": "Simulation started"
    }

def start():
    """Launched with `poetry run start` at root level"""
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()
