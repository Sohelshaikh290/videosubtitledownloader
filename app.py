import streamlit as st
import yt_dlp
import re
import io
import zipfile
import datetime
import os
import tempfile

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
st.markdown("Download `.srt` subtitles from any YouTube video utilizing **FFmpeg** for high-quality extraction.")

# --- Helper Functions ---
def get_video_info(url):
    """Fetches video metadata and available subtitles using yt-dlp"""
    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Parse available subtitles
            subs = {}
            if 'subtitles' in info and info['subtitles']:
                for lang, tracks in info['subtitles'].items():
                    name = tracks[0].get('name', lang)
                    subs["{} ({})".format(name, lang)] = lang
            
            if 'automatic_captions' in info and info['automatic_captions']:
                for lang, tracks in info['automatic_captions'].items():
                    name = tracks[0].get('name', lang)
                    label = "{} ({}) [Auto-generated]".format(name, lang)
                    # Prefer manual subs over auto-generated if both exist
                    if lang not in subs.values():
                        subs[label] = lang
                        
            return {
                'id': info.get('id'),
                'title': info.get('title', 'Unknown_Title'),
                'channel': info.get('uploader', 'Unknown Channel'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'available_subs': subs
            }
    except Exception as e:
        return None

def clean_filename(title):
    """Removes ONLY characters that break Windows/Mac file systems, keeps Emojis and Symbols intact."""
    return re.sub(r'[\\/*?:"<>|]', "", title)

def clear_processed_cache():
    """Clears generated files if user changes language selection."""
    st.session_state.processed_files = None

# --- Session State Management ---
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""
if "processed_files" not in st.session_state:
    st.session_state.processed_files = None

# --- UI Layout ---
url = st.text_input("🔗 Paste YouTube Video Link Here:")

# Reset state if user pastes a new URL
if url != st.session_state.last_url:
    st.session_state.video_info = None
    st.session_state.processed_files = None
    st.session_state.last_url = url

if st.button("🚀 Start", type="primary"):
    if url.strip() == "":
        st.warning("Please enter a valid YouTube URL first.")
    else:
        with st.spinner("Fetching video details and subtitles..."):
            info = get_video_info(url)
            if info:
                st.session_state.video_info = info
                st.session_state.processed_files = None
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
        st.write("**👤 Channel:** {}".format(info['channel']))
        # Convert seconds to HH:MM:SS
        duration_str = str(datetime.timedelta(seconds=info['duration']))
        st.write("**⏱️ Runtime:** {}".format(duration_str))

    st.markdown("### 📝 Available Subtitles")
    
    subs_map = info['available_subs']
    if not subs_map:
        st.warning("No subtitles found for this video.")
    else:
        all_langs = list(subs_map.keys())
        
        # Selection options
        select_all = st.checkbox("✅ Select All Available Languages", on_change=clear_processed_cache)
        
        if select_all:
            selected_langs = all_langs
            st.info("{} languages selected.".format(len(all_langs)))
        else:
            selected_langs = st.multiselect(
                "Or pick specific languages:", 
                options=all_langs, 
                default=[all_langs[0]] if all_langs else [],
                on_change=clear_processed_cache
            )

        # Download Logic using FFmpeg
        if selected_langs:
            if st.button("⚙️ Process Subtitles with FFmpeg", type="secondary"):
                with st.spinner("Downloading and converting using FFmpeg..."):
                    safe_title = clean_filename(info['title'])
                    selected_lang_codes = [subs_map[label] for label in selected_langs]
                    
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # yt-dlp config strictly designed to convert via ffmpeg
                        ydl_opts = {
                            'quiet': True,
                            'skip_download': True,
                            'writesubtitles': True,
                            'writeautomaticsub': True,
                            'subtitleslangs': selected_lang_codes,
                            'convertsubtitles': 'srt', # <--- Triggers FFmpeg
                            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                        }
                        
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])
                            
                            processed = []
                            # Read converted files back from temporary directory
                            for file in os.listdir(temp_dir):
                                if file.endswith('.srt') or file.endswith('.vtt'):
                                    with open(os.path.join(temp_dir, file), 'rb') as f:
                                        data = f.read()
                                    
                                    # Parse yt-dlp output names: videoID.lang.srt
                                    parts = file.split('.')
                                    if len(parts) >= 3:
                                        lang_code = parts[-2]
                                        ext = parts[-1]
                                    else:
                                        lang_code = "sub"
                                        ext = "srt" if file.endswith('.srt') else "vtt"
                                        
                                    final_name = "{} [{}].{}".format(safe_title, lang_code, ext)
                                    processed.append((final_name, data))
                            
                            if not processed:
                                st.error("No subtitles generated. Does your server have FFmpeg installed?")
                            else:
                                st.session_state.processed_files = processed
                                
                        except Exception as e:
                            st.error("Error processing with FFmpeg: {}".format(e))
            
            # Show standard Streamlit download buttons if processed successfully
            if st.session_state.processed_files:
                st.success("✅ Processed successfully!")
                processed_files = st.session_state.processed_files
                safe_title = clean_filename(info['title'])
                
                if len(processed_files) == 1:
                    file_name, data = processed_files[0]
                    st.download_button(
                        label="⬇️ Download Subtitle ({})".format(file_name),
                        data=data,
                        file_name=file_name,
                        mime="text/plain"
                    )
                else:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for file_name, data in processed_files:
                            zip_file.writestr(file_name, data)
                    
                    st.download_button(
                        label="⬇️ Download {} Subtitles (ZIP Folder)".format(len(processed_files)),
                        data=zip_buffer.getvalue(),
                        file_name="{}_Subtitles.zip".format(safe_title),
                        mime="application/zip"
                    )
