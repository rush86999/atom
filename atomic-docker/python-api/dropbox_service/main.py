from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

@app.route('/save-file', methods=['POST'])
def save_file():
    data = request.get_json()
    folder_path = data.get('folderPath')
    file_name = data.get('fileName')
    file_content = data.get('fileContent')

    if not all([folder_path, file_name, file_content]):
        return jsonify({'error': 'Missing parameters'}), 400

    # This is a placeholder for the actual Dropbox API call.
    # In a real implementation, we would use the Dropbox SDK here.
    print(f"Saving file '{file_name}' to Dropbox folder '{folder_path}'")
    print(f"Content: {file_content}")

    # Placeholder response
    response_data = {
        'fileId': 'placeholder_file_id',
        'filePath': os.path.join(folder_path, file_name)
    }

    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
