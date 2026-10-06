import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB Max upload limit

# Local fallback directory just in case cloud storage has bad authorization tokens
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==================== MONGO CONNECTION GUARANTEE ====================
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')

# Added strict timeout rules. If connection fails, the app crashes explicitly instead of staying silent.
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000, 
    connectTimeoutMS=5000
)

db = client['sprites_db'] 
sprites_collection = db.sprites
# =====================================================================

@app.route('/')
def index():
    # Force a database read immediately to verify connectivity
    try:
        sprites = list(sprites_collection.find())
    except Exception as e:
        return f"🚨 Database Connection Error: {str(e)}", 500
    return render_template('index.html', sprites=sprites)

@app.route('/upload', methods=['POST'])
def upload_sprites():
    category = request.form.get('category', 'general').strip().lower()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    
    if 'sprites' not in request.files:
        return jsonify({"error": "No file field 'sprites' found"}), 400
        
    uploaded_files = request.files.getlist('sprites')
    
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ''):
        return jsonify({"error": "No files selected"}), 400

    inserted_count = 0

    for file in uploaded_files:
        if file and file.filename != '':
            # FIX: Properly split and extract strings without methods crashing the loop
            original_filename = secure_filename(file.filename)
            base_name = original_filename.rsplit('.', 1)[0]
            clean_name = base_name.replace('_', ' ').replace('-', ' ').title()
            
            # Save locally to ensure zero third-party upload API blocks
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(file_path)
            
            image_url = f"/static/uploads/{original_filename}"
            
            # Formulate document structure
            sprite_data = {
                "name": clean_name,
                "filename": original_filename,
                "image_url": image_url,
                "category": category,
                "tags": tags
            }
            
            # Direct insert command execution
            sprites_collection.insert_one(sprite_data)
            inserted_count += 1

    if request.headers.get('Accept') == 'application/json' or 'json' in request.headers.get('Content-Type', ''):
        return jsonify({"status": "success", "uploaded_count": inserted_count}), 200
        
    return redirect(url_for('index'))

# ==================== API ENDPOINTS ====================

@app.route('/api/sprites', methods=['GET'])
def get_all_sprites():
    category = request.args.get('category')
    tag = request.args.get('tag')
    
    query = {}
    if category:
        query['category'] = category.strip().lower()
    if tag:
        query['tags'] = tag.strip().lower()
        
    sprites = list(sprites_collection.find(query))
    
    output = []
    base_url = request.url_root.rstrip('/')
    for s in sprites:
        output.append({
            "id": str(s['_id']),
            "name": s['name'],
            "category": s['category'],
            "tags": s['tags'],
            "image_url": f"{base_url}{s['image_url']}" if s['image_url'].startswith('/') else s['image_url']
        })
        
    return jsonify({"count": len(output), "sprites": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
