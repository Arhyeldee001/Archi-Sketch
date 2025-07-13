from fastapi import FastAPI, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
import os

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/templates"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def home():
    return RedirectResponse(url="/templates")

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    templates_list = os.listdir(UPLOAD_DIR)
    return templates.TemplateResponse("admin.html", {"request": request, "templates": templates_list})

@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/templates", response_class=HTMLResponse)
async def template_gallery(request: Request):
    templates_list = os.listdir(UPLOAD_DIR)
    return templates.TemplateResponse("templates.html", {"request": request, "templates": templates_list})
