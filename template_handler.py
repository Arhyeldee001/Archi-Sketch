from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "static/templates"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    templates_list = os.listdir(UPLOAD_DIR)
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "templates": templates_list
    })

@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
    return RedirectResponse(url="/admin", status_code=303)

@router.get("/templates", response_class=HTMLResponse)
async def template_gallery(request: Request):
    templates_list = os.listdir(UPLOAD_DIR)
    return templates.TemplateResponse("templates.html", {
        "request": request,
        "templates": templates_list
    })
