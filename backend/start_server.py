import uvicorn
from app.main import app
from app.services.feature_extract import _load_model

# Preload DINOv2 before starting server
_load_model()
print("DINOv2 loaded, starting server...")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8321)
