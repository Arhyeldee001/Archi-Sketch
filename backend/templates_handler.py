from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="../templates")  # ← Critical path fix!
UPLOAD_DIR = "../static/templates"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/upload")  # Changed from /admin
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
    return RedirectResponse(url="/upload", status_code=303)
