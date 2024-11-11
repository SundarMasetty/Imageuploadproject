from flask import Flask, render_template, request, redirect, url_for, Response
from google.cloud import storage
import os
import io
import json
import google.generativeai as genai

app = Flask(__name__)
storage_client = storage.Client()
BUCKET_NAME = 'buckettttteyy'
genai.configure(api_key="AIzaSyAYFV96IdIyOqRyWn6ipxaQiSbn73eEZP8")
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

#New Additions
def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini."""
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def get_image_details(image_path):
    """Uploads the image and retrieves caption and description."""
    # Upload the image
    uploaded_file = upload_to_gemini(image_path, mime_type="image/jpeg")
    
    # Set up a simpler GenerativeModel configuration
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    # Start a chat session
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    uploaded_file,  # Ensure this is the correct format or URI needed by the API
                    "Please describe the image with a short caption and a brief description.",
                ],
            },
        ]
    )
    
    # Send the message to get the response
    try:
        response = chat_session.send_message("Describe the image with a short caption and description.")
        print("Raw response from API:", response.text)  # Log the response for debugging
        response_text = response.text.strip()

        # Attempt to parse the response as JSON (if applicable)
        try:
            details = json.loads(response_text)
            caption = details.get("caption", "Default Caption")
            description = details.get("description", "Default Description")
        except json.JSONDecodeError:
            caption, description = response_text, "Description unavailable"
        
        return {"caption": caption, "description": description}
    except Exception as e:
        print("Error in get_image_details:", e)
        return {"caption": "Default Caption", "description": "Default Description"}

    except json.JSONDecodeError:
        print("Failed to decode JSON response.")
        print("Response text:", response_text)  # Log the response text
        return {"caption": "Default Caption", "description": "Default Description"}

def save_full_output_to_gcs(image_path, details):
    text_filename = f"{image_path.split('/')[-1].split('.')[0]}.txt"
    blob = storage_client.bucket(BUCKET_NAME).blob(text_filename)
    # Saving both caption and description as JSON 
    blob.upload_from_string(json.dumps(details))
    print(f"Saved full output to {text_filename} in Google Cloud Storage.")

def parse_output_from_gcs(filename):
    from google.cloud import storage
    # Constructing the text file name
    text_filename = f"{filename.rsplit('.', 1)[0]}.txt"
    client = storage.Client()
    bucket = client.bucket('bucksfrbucks')
    blob = bucket.blob(text_filename)
    try:
        content = blob.download_as_text()
        # Parsing JSON content
        json_content = json.loads(content)
        caption = json_content.get('caption', 'Default Caption')
        description = json_content.get('description', 'Default Description')
        return caption, description
    except Exception as e:
        print(f"Error downloading {text_filename}: {str(e)}")
        return "Default Caption", "Default Description"

def list_blobs(bucket_name):
    """Lists all the blobs in the bucket."""
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)
    return blobs

def download_blob_into_memory(bucket_name, blob_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    file_obj = io.BytesIO()
    blob.download_to_file(file_obj)
    file_obj.seek(0)
    return file_obj.read()
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)  # Save the file locally
            destination_blob_name = filename
            upload_blob(BUCKET_NAME, filepath, destination_blob_name)  
            # Call get_image_details to generate caption and description
            details = get_image_details(filepath)  # Add this line
            return redirect(url_for('gallery'))  # Redirect to the gallery page after processing
    return render_template('upload.html')

@app.route('/gallery')
def gallery():
    blobs = list_blobs(BUCKET_NAME)
    blob_list = list(blobs)
    image_data = {}
    
    for blob in blob_list:
        # Check if the blob is an image file by checking its extension
        if blob.name.endswith(('.jpeg', '.jpg', '.png' , 'webp')):
            image_bytes = download_blob_into_memory(BUCKET_NAME, blob.name)
            image_data[blob.name] = image_bytes  # storing images only in the dictionary
    return render_template('gallery.html', image_data=image_data)
    # Fetch captions and descriptions
    captions = {}
    for filename in image_data.keys():
        text_filename = filename.rsplit('.', 1)[0] + '.txt'
        caption, description = parse_output_from_gcs(text_filename)  
        captions[filename] = {"caption": caption, "description": description}
    return render_template('gallery.html', image_data=image_data, captions=captions)

@app.route('/images/<filename>')
def serve_image(filename):
    image_bytes = download_blob_into_memory(BUCKET_NAME, filename)
    return Response(image_bytes, mimetype='image/jpeg') 

@app.route('/image_details/<filename>')
def image_details(filename):
    # Fetching the caption and description from the text file
    text_filename = filename.rsplit('.', 1)[0] + '.txt'
    caption, description = parse_output_from_gcs(text_filename)
    image_url = url_for('serve_image', filename=filename)
    return render_template('image_details.html', 
                           image_url=image_url,
                           caption=caption,
                           description=description)

if __name__ == '__main__':

    app.run(debug=True)
