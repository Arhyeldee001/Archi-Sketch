from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()

# Use absolute path for Render compatibility
current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "../../templates"))
UPLOAD_DIR = os.path.join(current_dir, "../../static/templates")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/upload")  # This will become /templates/upload
async def upload_ui(request: Request):
    return templates.TemplateResponse("template_admin.html", {
        "request": request,
        "templates": os.listdir(UPLOAD_DIR)
    })

@router.post("/upload")
async def handle_upload(files: list[UploadFile] = File(...)):
    for file in files:
        if file.filename:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
    return RedirectResponse(url="/templates/upload", status_code=303)
