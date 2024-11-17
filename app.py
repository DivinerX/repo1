from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uuid
import subprocess
import glob

app = FastAPI()

# Enable CORS (Adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for specific domains in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated files
app.mount("/generated", StaticFiles(directory="generated"), name="generated")


@app.post("/generate")
def generate_music_api():
    try:
        # Generate a unique output directory for each request
        output_dir = f"generated/{uuid.uuid4()}"
        os.makedirs(output_dir, exist_ok=True)

        # Call the function to generate the music
        midi_files = generate_music(output_dir)

        # Convert .mid files to .mp3
        converted_files = convert_midi_to_mp3(midi_files, output_dir)

        # Return the list of files as URLs
        file_urls = [f"/generated/{os.path.basename(output_dir)}/{os.path.basename(file)}" for file in converted_files]
        return {"message": "Music generated!", "files": file_urls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Function to generate music using Melody RNN
def generate_music(output_dir, num_outputs=2):
    config = "cat-mel_2bar_big"
    checkpoint_file = "cat-mel_2bar_big.tar"
    mode = "sample"

    command = [
        "music_vae_generate",
        "--config",
        config,
        "--checkpoint_file",
        checkpoint_file,
        "--output_dir",
        output_dir,
        "--num_outputs",
        str(num_outputs),
        "--mode",
        mode
    ]

    subprocess.run(command, check=True)
    return glob.glob(os.path.join(output_dir, "*.mid"))


# Function to convert MIDI to MP3
def convert_midi_to_mp3(midi_files, output_dir):
    converted_files = []
    for midi_file in midi_files:
        try:
            # Convert MIDI to WAV using timidity
            wav_file = midi_file.replace(".mid", ".wav")
            subprocess.run(["timidity", midi_file, "-Ow", "-o", wav_file], check=True)

            # Convert WAV to MP3 using FFmpeg
            mp3_file = wav_file.replace(".wav", ".mp3")
            subprocess.run(["ffmpeg", "-i", wav_file, "-acodec", "libmp3lame", "-q:a", "2", mp3_file], check=True)

            converted_files.append(mp3_file)

            # Cleanup intermediate WAV file
            os.remove(wav_file)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Error in MIDI to MP3 conversion: {e}")

    return converted_files


@app.get("/")
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Music Player</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 20px;
            }
            button {
                padding: 10px 20px;
                font-size: 16px;
                margin: 10px 0;
                cursor: pointer;
            }
            #music-list button {
                margin: 5px;
            }
            #loading-message {
                font-size: 18px;
                color: #555;
            }
            .spinner {
                margin: 10px auto;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                0% {
                    transform: rotate(0deg);
                }
                100% {
                    transform: rotate(360deg);
                }
            }
        </style>
    </head>
    <body>
        <h1>Generated Music Player</h1>
        <button id="generate-music">Generate Music</button>
        <div id="music-list"></div>
        <audio id="audio-player" controls>
            Your browser does not support the audio element.
        </audio>

        <script>
            document.getElementById("generate-music").addEventListener("click", async () => {
                try {
                    // Show loading message and spinner
                    const generateButton = document.getElementById("generate-music");
                    const musicList = document.getElementById("music-list");
                    const loadingMessage = document.createElement("div");
                    loadingMessage.id = "loading-message";
                    loadingMessage.innerHTML = `
                        <div class="spinner"></div>
                        <div>Generating music, please wait...</div>
                    `;
                    musicList.innerHTML = ""; // Clear previous files
                    musicList.appendChild(loadingMessage);

                    // Disable the button to prevent multiple clicks
                    generateButton.disabled = true;

                    // Make the API call
                    const response = await fetch("/generate", { method: "POST" });
                    const data = await response.json();
                    const files = data.files;

                    // Remove loading message and re-enable the button
                    musicList.removeChild(loadingMessage);
                    generateButton.disabled = false;

                    // Populate the music list with buttons to play files
                    files.forEach((file) => {
                        const fileItem = document.createElement("button");
                        fileItem.textContent = `Play ${file.split('/').pop()}`;
                        fileItem.addEventListener("click", () => {
                            const audioPlayer = document.getElementById("audio-player");
                            audioPlayer.src = file;
                            audioPlayer.play();
                        });
                        musicList.appendChild(fileItem);
                    });
                } catch (error) {
                    console.error("Error generating music:", error);

                    // Handle errors
                    const musicList = document.getElementById("music-list");
                    musicList.innerHTML = `<div style="color: red;">Error generating music. Please try again later.</div>`;

                    // Re-enable the button
                    const generateButton = document.getElementById("generate-music");
                    generateButton.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, media_type="text/html")
