import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB Max upload size

# ==================== CLOUD ENVIRONMENT CONFIGURATION ====================
# MongoDB Cloud Cluster Connection
# ==================== CLOUD ENVIRONMENT CONFIGURATION ====================
# MongoDB Cloud Cluster Connection
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)

# Fallback gracefully if Vercel's MONGO_URI lacks a trailing /database_name
try:
    db = client['sprites_db1']
    if db is None:
        db = client['sprites_db']
        sprites_collection = db.sprites
        print("MongoDB database and 'sprites' collection     initialized successfully.")
    if sprites_collection.count_documents({}) == 0:
        	sprites_collection.insert_one({"_init": True, "name": "System Init Stub"})
        	sprites_collection.delete_many({"_init": True})
        	print("MongoDB database and 'sprites' collection initialized successfully.")

except Exception:
    db = client['sprites_db']

    
except Exception as e:
    print(f"Database connection initialization failed: {str(e)}")




# Cloudinary Infinite Storage Configuration
# You will get this URL from your free Cloudinary dashboard settings page
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
else:
    # Fallback configuration parameters if needed
    cloudinary.config(
        cloud_name = os.environ.get("CLOUD_NAME"),
        api_key = os.environ.get("CLOUD_API_KEY"),
        api_secret = os.environ.get("CLOUD_API_SECRET")
    )
# =========================================================================

@app.route('/')
def index():
    try:
        raw_sprites = list(sprites_collection.find())
        sprites = []
        
        for s in raw_sprites:
            # Convert the ObjectId to a standard string format safely
            s['_id'] = str(s['_id'])
            sprites.append(s)
            
        return render_template('index.html', sprites=sprites)
    except Exception as e:
        # This prevents a total crash and prints the exact issue to your Render logs
        return f"Database Fetch Error: {str(e)}", 500

@app.route('/upload', methods=['POST'])
def upload_sprites():
    category = request.form.get('category', 'general').strip().lower()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    
    # Gracefully check for both standard forms and script multi-part uploads
    if 'sprites' not in request.files:
        return jsonify({"error": "No file field 'sprites' found in request"}), 400
        
    uploaded_files = request.files.getlist('sprites')
    
    # If the list is empty or contains an unselected empty file wrapper
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ''):
        return jsonify({"error": "No actual files were selected for upload"}), 400

    inserted_count = 0

    for file in uploaded_files:
        if file and file.filename != '':
            try:
                # Direct stream transmission to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder="sprite_vault"
                )
                
                image_url = upload_result.get('secure_url')
                filename = file.filename
                
                # Human-readable name generation
                clean_name = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()
                
                # Push object to MongoDB
                sprite_data = {
                    "name": clean_name,
                    "filename": filename,
                    "image_url": image_url,
                    "category": category,
                    "tags": tags
                }
                sprites_collection.insert_one(sprite_data)
                inserted_count += 1
                
            except Exception as e:
                print(f"❌ Failed uploading document {file.filename}: {str(e)}")
                continue

    # Return a clean message if it's an API client, otherwise redirect the browser
    if request.headers.get('Accept') == 'application/json' or 'json' in request.headers.get('Content-Type', ''):
        return jsonify({"status": "success", "uploaded_count": inserted_count}), 200
        
    return redirect(url_for('index'))



# ==================== REST API ENDPOINTS ====================

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
    for s in sprites:
        output.append({
            "id": str(s['_id']),
            "name": s['name'],
            "category": s['category'],
            "tags": s['tags'],
            "image_url": s['image_url'] # This displays the direct global cloud URL instantly
        })

    return jsonify({"count": len(output), "sprites": output})

@app.route('/api/sprites/<id>', methods=['GET'])
def get_sprite_by_id(id):
    try:
        sprite = sprites_collection.find_one({"_id": ObjectId(id)})
        if not sprite:
            return jsonify({"error": "Sprite not found"}), 404

        return jsonify({
            "id": str(sprite['_id']),
            "name": sprite['name'],
            "category": sprite['category'],
            "tags": sprite['tags'],
            "image_url": sprite['image_url']
        })
    except Exception:
        return jsonify({"error": "Invalid ID format"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)