import os
import json
import sys

def stream_file_content(file_path, chunk_size=4096):
    """
    Streams file content in chunks to avoid memory issues with large files.
    Emits JSON chunks to stdout.
    """
    try:
        if not os.path.exists(file_path):
            print(json.dumps({"status": "error", "message": f"File not found: {file_path}"}))
            return

        file_size = os.path.getsize(file_path)
        bytes_read = 0

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                bytes_read += len(chunk)
                print(json.dumps({
                    "status": "streaming",
                    "chunk": chunk,
                    "progress": round((bytes_read / file_size) * 100, 2) if file_size > 0 else 100
                }, ensure_ascii=False))
        
        print(json.dumps({"status": "completed", "total_bytes": bytes_read}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    # Example usage: 
    # python streaming_utils.py <file_path>
    if len(sys.argv) > 1:
        stream_file_content(sys.argv[1])
