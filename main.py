import bot, extract
from flask import Flask, request, jsonify
import logging
from flask_cors import CORS
from werkzeug.utils import secure_filename
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Dict, List
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {
    "origins": [
        "https://dh-van.github.io",
        "https://orionsoftware.systems"
    ],
    "methods": ["POST", "OPTIONS", "GET"],
    "allow_headers": ["Content-Type"]
}})

# In-memory job storage (you could also use SQLite for persistence)
jobs: Dict[str, dict] = {}
job_lock = threading.Lock()

# Thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=5)

def create_job(job_type: str, status: str = "pending") -> str:
    """Create a new job entry"""
    job_id = str(uuid.uuid4())
    with job_lock:
        jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
    return job_id

def update_job(job_id: str, status: str, result=None, error=None):
    """Update job status"""
    with job_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = status
            if result:
                jobs[job_id]["result"] = result
            if error:
                jobs[job_id]["error"] = error

async def async_add_to_cart(job_id: str, csv_data):
    """Async wrapper for bot.add_to_cart"""
    try:
        update_job(job_id, "processing")
        # If bot.add_to_cart is synchronous, run it in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, bot.add_to_cart, csv_data)
        update_job(job_id, "completed", result=result)
    except Exception as e:
        update_job(job_id, "failed", error=str(e))

async def async_extract(job_id: str, vendor: str, filename: str, html_content: str):
    """Async wrapper for extract functions"""
    try:
        update_job(job_id, "processing")
        loop = asyncio.get_event_loop()
        
        if vendor == "MetalSupermarkets":
            result = await loop.run_in_executor(
                executor, 
                extract.metal_supermarkets, 
                filename, 
                html_content
            )
        elif vendor == "McMaster":
            result = await loop.run_in_executor(
                executor,
                extract.mcmaster,
                filename,
                html_content
            )
        else:
            raise ValueError(f"Unsupported vendor: {vendor}")
            
        update_job(job_id, "completed", result=result)
    except Exception as e:
        update_job(job_id, "failed", error=str(e))

def run_async_task(coro):
    """Run async task in background"""
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    
    thread = threading.Thread(target=run_in_thread)
    thread.start()

@app.route('/add', methods=['POST'])
def get_information():
    file = request.files['file']
    csv_data = file.stream.read().decode("utf-8").splitlines()
    
    # Create job and run async
    job_id = create_job("add_to_cart")
    run_async_task(async_add_to_cart(job_id, csv_data))
    
    return jsonify({
        "message": "Items are being added to cart",
        "job_id": job_id
    }), 200  # 200 Accepted for async processing

@app.route('/request', methods=['POST'])
def request_parts():
    print('method called')
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    files = request.files.getlist('file')
    vendor = request.form.get('vendor')

    if not vendor:
        return jsonify({"error": "Vendor is required"}), 400

    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "No file selected"}), 400

    job_ids = []
    errors = []

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)

        if not filename.lower().endswith(('.html', '.htm')):
            errors.append(f"Invalid extension: {filename}")
            continue

        if file.mimetype != 'text/html':
            errors.append(f"Invalid MIME type for {filename}: {file.mimetype}")
            continue

        try:
            html_content = file.read().decode("utf-8")
            
            # Create job and run async
            job_id = create_job(f"extract_{vendor}")
            run_async_task(async_extract(job_id, vendor, filename, html_content))
            job_ids.append({"file": filename, "job_id": job_id})

        except Exception as e:
            errors.append(f"Failed to read {filename}: {str(e)}")
    
    return jsonify({
        "message": f"{len(job_ids)} file(s) queued for processing",
        "jobs": job_ids,
        "errors": errors
    }), 200

@app.route('/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Check job status"""
    with job_lock:
        if job_id not in jobs:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(jobs[job_id])

@app.route('/jobs', methods=['GET'])
def get_all_jobs():
    """Get all jobs (optional, for monitoring)"""
    with job_lock:
        return jsonify(list(jobs.values()))

if __name__ == '__main__':
    app.run(debug=True, threaded=True)  # Enable threading