import asyncio
import json
import logging
import os
import threading
from datetime import datetime
from flask import Flask, render_template, send_file, abort
from geminiprocess import analyze_lecture
from studentprofile import fetch_student_profile
from transcriber import listen_continuously
from voice import speak
import websockets

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Base directory for notes
NOTES_DIR = "notes"
if not os.path.exists(NOTES_DIR):
    try:
        os.makedirs(NOTES_DIR)
    except Exception as e:
        logging.error(f"Failed to create notes directory: {e}")

# Create student-specific directory
def ensure_student_dir(student_id):
    student_dir = os.path.join(NOTES_DIR, student_id)
    try:
        if not os.path.exists(student_dir):
            os.makedirs(student_dir)
        return student_dir
    except Exception as e:
        logging.error(f"Failed to create directory for student {student_id}: {e}")
        return None

# Save content to a file
def save_file(student_id, content_type, content, chunk_number):
    profile = fetch_student_profile(student_id)
    student_name = profile.get("name", "Unknown") if profile else "Unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    student_dir = ensure_student_dir(student_id)
    if not student_dir:
        return None
    filename = os.path.join(student_dir, f"{content_type}_{student_id}_{timestamp}_chunk{chunk_number}.txt")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Student: {student_name}\nLecture Date: {timestamp}\n\n{content_type.replace('_', ' ').title()}:\n{content}\n")
        logging.info(f"{content_type} saved to {filename}")
        return os.path.basename(filename)
    except Exception as e:
        logging.error(f"Failed to save {content_type} to {filename}: {e}")
        return None

# Save consolidated notes
def save_consolidated_notes(student_id, transcript, notes, weak_areas, gemini_notes, chunk_number):
    profile = fetch_student_profile(student_id)
    student_name = profile.get("name", "Unknown") if profile else "Unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    student_dir = ensure_student_dir(student_id)
    if not student_dir:
        return None
    filename = os.path.join(student_dir, f"lecture_notes_{student_id}_{timestamp}_chunk{chunk_number}.txt")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Student: {student_name}\nLecture Date: {timestamp}\n\n")
            f.write("=== Lecture Transcript ===\n")
            f.write(transcript + "\n\n")
            f.write("=== Summary ===\n")
            f.write(notes.get("summary", "") + "\n\n")
            f.write("=== Doubts ===\n")
            f.write(notes.get("doubts", "") + "\n\n")
            f.write("=== Weak Areas ===\n")
            f.write(weak_areas + "\n\n")
            f.write("=== Gemini Notes ===\n")
            f.write(gemini_notes + "\n")
        logging.info(f"Consolidated notes saved to {filename}")
        return os.path.basename(filename)
    except Exception as e:
        logging.error(f"Failed to save consolidated notes to {filename}: {e}")
        return None

# Analyze weak areas
def analyze_weak_areas(summary, weak_topics):
    try:
        weak_areas = "Identified Weak Areas:\n"
        weak_areas += f"- Topics: {', '.join(weak_topics) if weak_topics else 'None'}\n"
        weak_areas += "Recommendations:\n"
        for topic in weak_topics:
            weak_areas += f"  - {topic}: Review core concepts.\n"
        return weak_areas.strip()
    except Exception as e:
        logging.error(f"Failed to analyze weak areas: {e}")
        return "No weak areas identified"

# Generate Gemini notes (placeholder)
def generate_gemini_notes(transcript):
    try:
        return f"Gemini Notes:\n- Key Concept: {transcript[:50]}...\n- Tips: Review lecture topics."
    except Exception as e:
        logging.error(f"Failed to generate Gemini notes: {e}")
        return "No Gemini notes generated"

# WebSocket server
async def process_lecture(websocket, path=None):
    student_id = path.split('/')[-1] if path and '/' in path else "student_123"
    logging.info(f"WebSocket connection established for student_id: {student_id}")
    full_transcript = ""
    chunk_count = 1
    word_count = 0
    words = []
    try:
        async def send_heartbeat():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send(json.dumps({"status": "heartbeat"}))
                    logging.debug("Sent heartbeat")
                except websockets.exceptions.ConnectionClosed:
                    logging.debug("WebSocket connection closed")
                    break
                except Exception as e:
                    logging.error(f"Failed to send heartbeat: {e}")
                    break

        asyncio.create_task(send_heartbeat())

        async for message in websocket:
            logging.info(f"Received message: {message}")
            try:
                data = json.loads(message)
                action = data.get("action", "")

                if action == "start_lecture":
                    transcript_chunk = data.get("transcript", "").strip()
                    if not transcript_chunk:
                        logging.warning("Empty transcript received")
                        await websocket.send(json.dumps({"status": "error", "message": "Empty transcript received"}))
                        continue

                    if "stop listening" in transcript_chunk.lower():
                        logging.info("Stop listening command received")
                        speak("Stopped listening.")
                        await websocket.send(json.dumps({"status": "stopped"}))
                        if full_transcript.strip():
                            await process_and_save(student_id, full_transcript, chunk_count, words, websocket)
                        break

                    full_transcript += f" {transcript_chunk}"
                    chunk_words = transcript_chunk.split()
                    words.extend(chunk_words)
                    word_count += len(chunk_words)
                    logging.info(f"Chunk {chunk_count}: {transcript_chunk} (Words: {word_count})")
                    await websocket.send(json.dumps({
                        "status": "chunk",
                        "chunk": transcript_chunk,
                        "chunk_number": chunk_count
                    }))
                    chunk_count += 1

                    if word_count >= 200:
                        chunk_transcript = ' '.join(words[-200:])
                        await process_and_save(student_id, chunk_transcript, chunk_count, words, websocket)
                        word_count = 0
                        words = []

                elif action == "process_lecture":
                    if full_transcript.strip():
                        logging.info("Processing lecture manually")
                        await process_and_save(student_id, full_transcript, chunk_count, words, websocket)
                    else:
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": "No transcript available to process"
                        }))

                elif action in ["voice_query", "keyword_query"]:
                    query = data.get("query", "").strip()
                    if query:
                        logging.info(f"Processing query: {query}")
                        try:
                            response = f"AI Response: {query}"  # Placeholder
                            speak(response)
                            await websocket.send(json.dumps({
                                "status": "query_response",
                                "response": response,
                                "query": query
                            }))
                        except Exception as e:
                            logging.error(f"Query failed: {e}")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "message": "Query processing failed"
                            }))
                    else:
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": "Invalid query"
                        }))

                elif action == "heartbeat":
                    logging.debug("Received heartbeat")
                    await websocket.send(json.dumps({"status": "heartbeat"}))

            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))
            except Exception as e:
                logging.error(f"Server error: {e}")
                await websocket.send(json.dumps({"status": "error", "message": str(e)}))

    except websockets.exceptions.ConnectionClosed:
        logging.info("Client disconnected")
    except Exception as e:
        logging.error(f"WebSocket handler error: {e}")

async def process_and_save(student_id, transcript, chunk_count, words, websocket):
    profile = fetch_student_profile(student_id)
    weak_topics = profile.get("weak_topics", "").split(";") if profile else []
    try:
        ai_output = analyze_lecture(transcript, weak_topics)
    except Exception as e:
        logging.error(f"analyze_lecture failed: {e}")
        await websocket.send(json.dumps({"status": "error", "message": "Analysis failed"}))
        return

    notes = {
        "summary": ai_output.split("Doubts")[0].strip() if "Doubts" in ai_output else ai_output,
        "doubts": ai_output.split("Doubts")[1].strip() if "Doubts" in ai_output else "",
        "keywords": [],
        "tags": []
    }
    weak_areas = analyze_weak_areas(notes["summary"], weak_topics)
    gemini_notes = generate_gemini_notes(transcript)

    # Save files individually, allow partial success
    transcript_filename = save_file(student_id, "transcript", transcript, chunk_count)
    summary_filename = save_file(student_id, "summary", notes["summary"], chunk_count)
    doubts_filename = save_file(student_id, "doubts", notes["doubts"], chunk_count)
    weak_areas_filename = save_file(student_id, "weak_areas", weak_areas, chunk_count)
    gemini_notes_filename = save_file(student_id, "gemini_notes", gemini_notes, chunk_count)
    consolidated_filename = save_consolidated_notes(student_id, transcript, notes, weak_areas, gemini_notes, chunk_count)

    try:
        await websocket.send(json.dumps({
            "status": "processed",
            "notes": notes,
            "weak_areas": weak_areas,
            "gemini_notes": gemini_notes,
            "transcript_filename": transcript_filename,
            "summary_filename": summary_filename,
            "doubts_filename": doubts_filename,
            "weak_areas_filename": weak_areas_filename,
            "gemini_notes_filename": gemini_notes_filename,
            "consolidated_filename": consolidated_filename
        }))
        logging.info("Sent processed message")
    except Exception as e:
        logging.error(f"Failed to send processed message: {e}")
        await websocket.send(json.dumps({"status": "error", "message": "Failed to send results"}))

# Flask route to download files
@app.route('/download/<student_id>/<path:filename>')
def download_file(student_id, filename):
    try:
        file_path = os.path.join(NOTES_DIR, student_id, filename)
        if os.path.exists(file_path):
            logging.info(f"Serving file: {file_path}")
            return send_file(file_path, as_attachment=True)
        else:
            logging.error(f"File not found: {file_path}")
            abort(404, description="File not found")
    except Exception as e:
        logging.error(f"Download failed for {filename}: {e}")
        abort(500, description="Server error")

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

# Start WebSocket server
def start_websocket_server():
    asyncio.run(main())

async def main():
    try:
        server = await websockets.serve(process_lecture, "localhost", 8767)
        logging.info("WebSocket server running on ws://localhost:8767")
        await server.wait_closed()
    except Exception as e:
        logging.error(f"WebSocket server failed: {e}")

if __name__ == "__main__":
    try:
        websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
        websocket_thread.start()
        app.run(host="0.0.0.0", port=8000, debug=False)
    except Exception as e:
        logging.error(f"Server startup failed: {e}")