from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/templates'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('templates')
        for file in uploaded_files:
            if file.filename != '':
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        return redirect(url_for('admin'))
    
    templates = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('admin.html', templates=templates)

@app.route('/templates')
def template_gallery():
    templates = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('templates.html', templates=templates)

@app.route('/templates/<filename>')
def serve_template(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
