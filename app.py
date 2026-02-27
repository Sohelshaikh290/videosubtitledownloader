import streamlit as st
import yt_dlp
import re
import io
import zipfile
import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

# --- Theme Toggle (Day / Night Mode) ---
st.set_page_config(page_title="YT Subtitle Downloader", page_icon="🎬", layout="centered")

mode = st.sidebar.radio("🌓 Appearance Mode", ["Auto (Streamlit Default)", "Day ☀️", "Night 🌙"])
if mode == "Day ☀️":
    st.markdown("""
        <style>
            [data-testid="stAppViewContainer"] { background-color: #F0F2F6; color: #111111; }
            [data-testid="stHeader"] { background-color: #F0F2F6; }
            p, h1, h2, h3, h4, h5, h6, label, span { color: #111111 !important; }
        </style>
    """, unsafe_allow_html=True)
elif mode == "Night 🌙":
    st.markdown("""
        <style>
            [data-testid="stAppViewContainer"] { background-color: #0E1117; color: #FAFAFA; }
            [data-testid="stHeader"] { background-color: #0E1117; }
            p, h1, h2, h3, h4, h5, h6, label, span { color: #FAFAFA !important; }
            .stCheckbox label { color: #FAFAFA !important; }
        </style>
    """, unsafe_allow_html=True)

st.title("🎬 YouTube Subtitle Downloader")
st.markdown("Download `.srt` subtitles from any YouTube video with exact video titles (emojis included!).")

# --- Helper Functions ---
def get_video_info(url):
    """Fetches video metadata using yt-dlp"""
    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'id': info.get('id'),
                'title': info.get('title', 'Unknown_Title'),
                'channel': info.get('uploader', 'Unknown Channel'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail')
            }
    except Exception as e:
        return None

def extract_video_id(url, info_id):
    """Extracts the exact 11-character YouTube video ID robustly."""
    match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else info_id

def get_transcripts(video_id):
    """Fetches available subtitles using youtube-transcript-api"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcripts = {}
        for t in transcript_list:
            # Mark auto-generated ones
            label = f"{t.language} ({t.language_code})"
            if t.is_generated:
                label += " [Auto-generated]"
            transcripts[label] = t
        return transcripts, None
    except Exception as e:
        return None, str(e)

def clean_filename(title):
    """Removes ONLY characters that break Windows/Mac file systems, keeps Emojis and Symbols intact."""
    return re.sub(r'[\\/*?:"<>|]', "", title)

# --- Session State Management ---
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""
if "transcripts" not in st.session_state:
    st.session_state.transcripts = None
if "transcript_error" not in st.session_state:
    st.session_state.transcript_error = None

# --- UI Layout ---
url = st.text_input("🔗 Paste YouTube Video Link Here:")

# Reset state if user pastes a new URL
if url != st.session_state.last_url:
    st.session_state.video_info = None
    st.session_state.transcripts = None
    st.session_state.transcript_error = None
    st.session_state.last_url = url

if st.button("🚀 Start", type="primary"):
    if url.strip() == "":
        st.warning("Please enter a valid YouTube URL first.")
    else:
        with st.spinner("Fetching video details and subtitles..."):
            info = get_video_info(url)
            if info:
                st.session_state.video_info = info
                vid_id = extract_video_id(url, info['id'])
                subs, err = get_transcripts(vid_id)
                st.session_state.transcripts = subs
                st.session_state.transcript_error = err
            else:
                st.error("Failed to fetch video details. Please check the link.")

# --- Display Metadata and Subtitles ---
if st.session_state.video_info:
    info = st.session_state.video_info
    
    st.markdown("---")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(info['thumbnail'], use_container_width=True)
    with col2:
        st.subheader(info['title'])
        st.write(f"**👤 Channel:** {info['channel']}")
        # Convert seconds to HH:MM:SS
        duration_str = str(datetime.timedelta(seconds=info['duration']))
        st.write(f"**⏱️ Runtime:** {duration_str}")

    st.markdown("### 📝 Available Subtitles")
    
    if st.session_state.transcripts is None and st.session_state.transcript_error:
        st.error(f"⚠️ Could not load subtitles. YouTube might have blocked the request, or subtitles are disabled for this video.\n\n**Error details:** `{st.session_state.transcript_error}`")
    elif not st.session_state.transcripts:
        st.warning("No subtitles found for this video.")
    else:
        transcripts = st.session_state.transcripts
        all_langs = list(transcripts.keys())
        
        # Selection options
        select_all = st.checkbox("✅ Select All Available Languages")
        
        if select_all:
            selected_langs = all_langs
            st.info(f"{len(all_langs)} languages selected.")
        else:
            selected_langs = st.multiselect(
                "Or pick specific languages:", 
                options=all_langs, 
                default=[all_langs[0]] if all_langs else []
            )

        # Download Logic
        if selected_langs:
            formatter = SRTFormatter()
            safe_title = clean_filename(info['title'])
            
            if len(selected_langs) == 1:
                # Single file download
                lang_key = selected_langs[0]
                t = transcripts[lang_key]
                try:
                    srt_data = formatter.format_transcript(t.fetch())
                    file_name = f"{safe_title} [{t.language_code}].srt"
                    
                    st.download_button(
                        label=f"⬇️ Download Subtitle ({t.language_code})",
                        data=srt_data,
                        file_name=file_name,
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Could not fetch transcript for {lang_key}.")
            
            else:
                # Multiple files - Zip them together
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for lang_key in selected_langs:
                        t = transcripts[lang_key]
                        try:
                            srt_data = formatter.format_transcript(t.fetch())
                            file_name = f"{safe_title} [{t.language_code}].srt"
                            zip_file.writestr(file_name, srt_data)
                        except Exception:
                            continue # Skip if a specific language fails to fetch
                
                st.download_button(
                    label=f"⬇️ Download {len(selected_langs)} Subtitles (ZIP Folder)",
                    data=zip_buffer.getvalue(),
                    file_name=f"{safe_title}_Subtitles.zip",
                    mime="application/zip"
                )
