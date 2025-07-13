from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'templates_uploaded'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return redirect(url_for('admin'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        files = request.files.getlist('templates')
        for file in files:
            if file and allowed_file(file.filename):
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        return redirect(url_for('admin'))
    
    # List existing templates
    templates = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('admin.html', templates=templates)

@app.route('/templates')
def templates():
    templates = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('templates.html', templates=templates)

@app.route('/templates/<filename>')
def get_template(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
