import streamlit as st
import googleapiclient.discovery
import yt_dlp
import tempfile
import os
import base64
import time
from pathlib import Path
from googleapiclient.errors import HttpError

# Configuração da página
st.set_page_config(
    page_title="YouTube Downloader HD",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado com animações de loading
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        margin-top: 10px;
    }
    .video-card {
        padding: 15px;
        border-radius: 10px;
        background-color: #1e1e1e;
        margin-bottom: 20px;
        border: 1px solid #333;
    }
    .title {
        font-size: 16px;
        font-weight: bold;
        color: white;
        margin: 10px 0;
        height: 60px;
        overflow: hidden;
    }
    .channel {
        font-size: 14px;
        color: #3ACDD5;
        margin-bottom: 10px;
    }
    .download-section {
        background-color: #2d2d2d;
        padding: 15px;
        border-radius: 10px;
        margin-top: 20px;
        border: 1px solid #444;
    }
    .quality-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        background-color: #3ACDD5;
        color: black;
        font-size: 12px;
        font-weight: bold;
        margin-right: 5px;
    }
    
    /* Loading spinner customizado */
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
        background: rgba(30, 30, 30, 0.9);
        border-radius: 10px;
        border: 2px solid #3ACDD5;
        position: relative;
        min-height: 200px;
    }
    
    .spinner {
        width: 50px;
        height: 50px;
        border: 5px solid rgba(58, 205, 213, 0.3);
        border-radius: 50%;
        border-top-color: #3ACDD5;
        animation: spin 1s ease-in-out infinite;
        margin-bottom: 15px;
    }
    
    .spinner-small {
        width: 20px;
        height: 20px;
        border: 3px solid rgba(58, 205, 213, 0.3);
        border-radius: 50%;
        border-top-color: #3ACDD5;
        animation: spin 1s ease-in-out infinite;
        display: inline-block;
        margin-right: 10px;
        vertical-align: middle;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    .loading-text {
        color: #3ACDD5;
        font-size: 16px;
        font-weight: bold;
        text-align: center;
        margin-top: 10px;
    }
    
    .progress-bar {
        width: 100%;
        height: 6px;
        background: #333;
        border-radius: 3px;
        margin: 15px 0;
        overflow: hidden;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #3ACDD5, #00FFAA);
        border-radius: 3px;
        animation: progress-animation 2s ease-in-out infinite;
    }
    
    @keyframes progress-animation {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .download-info {
        font-size: 12px;
        color: #888;
        margin-top: 10px;
        text-align: center;
    }
    
    /* Estilo para botões desabilitados durante download */
    button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    
    .download-active {
        position: relative;
        overflow: hidden;
    }
    
    .download-active::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(58, 205, 213, 0.2), transparent);
        animation: shimmer 2s infinite;
    }
    
    @keyframes shimmer {
        100% { left: 100%; }
    }
    
    /* Ajuste para alinhar busca e botões */
    div[data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
    }
</style>
""", unsafe_allow_html=True)

YOUTUBE_API_KEY = "AIzaSyCgVJBwukJ4eaDTa3yxCSwYVf22VRVF1lU"

def search_youtube(query):
    """Faz a busca de vídeos no YouTube e retorna uma lista de resultados."""
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=25,
            regionCode="BR"
        )
        response = request.execute()
        
        videos = []
        for item in response.get("items", []):
            video_id = None
            
            if "id" in item:
                if isinstance(item["id"], dict):
                    if "videoId" in item["id"]:
                        video_id = item["id"]["videoId"]
                elif isinstance(item["id"], str):
                    video_id = item["id"]
            
            if not video_id:
                continue
                
            thumbnails = item["snippet"]["thumbnails"]
            thumbnail_url = thumbnails.get("high", {}).get("url") or \
                           thumbnails.get("medium", {}).get("url") or \
                           thumbnails.get("default", {}).get("url")
            
            videos.append({
                "title": item["snippet"]["title"],
                "video_id": video_id,
                "thumbnail": thumbnail_url,
                "channel": item["snippet"]["channelTitle"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description": item["snippet"]["description"][:100] + "..." if item["snippet"]["description"] else ""
            })
        return videos
    except HttpError as e:
        if e.resp.status == 403:
            st.error("Erro de autenticação da API. Verifique sua chave da API do YouTube.")
        else:
            st.error(f"Erro na API do YouTube: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Erro na busca: {str(e)}")
        return []

def sanitize_filename(filename):
    """Remove caracteres inválidos do nome do arquivo."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:100]

def show_loading_overlay(message="Processando...", type="video"):
    """Mostra um overlay de loading com animação."""
    if type == "video":
        icon = "🎬"
        color = "#3ACDD5"
    else:
        icon = "🎵"
        color = "#00FFAA"
    
    html = f"""
    <div class="loading-container">
        <div class="spinner" style="border-top-color: {color};"></div>
        <div class="loading-text">
            {icon} {message}
        </div>
        <div class="progress-bar">
            <div class="progress-fill"></div>
        </div>
        <div class="download-info">
            Isso pode levar alguns minutos dependendo do tamanho e qualidade...
        </div>
    </div>
    """
    return st.markdown(html, unsafe_allow_html=True)

def show_inline_loading(message=""):
    """Mostra um spinner inline pequeno."""
    html = f"""
    <span class="spinner-small"></span>
    <span style="color: #3ACDD5; font-size: 14px;">{message}</span>
    """
    return st.markdown(html, unsafe_allow_html=True)

def download_video_hd(video_url, video_title, quality_option="best", callback=None):
    """Baixa o vídeo do YouTube na melhor qualidade possível."""
    try:
        if not video_url or not video_url.startswith("http"):
            raise ValueError("URL do vídeo inválida!")

        temp_dir = tempfile.mkdtemp()
        safe_title = sanitize_filename(video_title)
        
        # Configurações para a melhor qualidade possível
        if quality_option == "best":
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [callback] if callback else [lambda d: None],
                'postprocessor_args': [
                    '-strict', '-2',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '320k'
                ],
                'ffmpeg_location': None,
            }
        elif quality_option == "4k":
            ydl_opts = {
                'format': 'bestvideo[height>=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height>=1440][ext=mp4]+bestaudio[ext=m4a]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}_4K.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [callback] if callback else [lambda d: None],
            }
        elif quality_option == "1080p":
            ydl_opts = {
                'format': 'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}_1080p.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [callback] if callback else [lambda d: None],
            }
        else:
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [callback] if callback else [lambda d: None],
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                base_name = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.avi']:
                    if os.path.exists(base_name + ext):
                        filename = base_name + ext
                        break
        
        return filename, safe_title
    except Exception as e:
        raise Exception(f"Erro ao baixar vídeo: {str(e)}")

def download_audio_hq(video_url, video_title, bitrate="320", callback=None):
    """Baixa o áudio do YouTube na melhor qualidade possível."""
    try:
        if not video_url or not video_url.startswith("http"):
            raise ValueError("URL do vídeo inválida!")

        temp_dir = tempfile.mkdtemp()
        safe_title = sanitize_filename(video_title)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [callback] if callback else [lambda d: None],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate,
            }],
            'postprocessor_args': [
                '-ar', '44100',
                '-ac', '2',
                '-b:a', f'{bitrate}k',
                '-vn',
            ],
            'extractaudio': True,
            'audioformat': 'mp3',
            'keepvideo': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_file = os.path.splitext(filename)[0] + ".mp3"
            
        return mp3_file, safe_title
    except Exception as e:
        raise Exception(f"Erro ao baixar áudio: {str(e)}")

def create_download_button(file_path, filename, button_text, file_type="video"):
    """Cria um botão de download para o arquivo."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        
        file_ext = os.path.splitext(filename)[1][1:] if '.' in filename else "bin"
        
        mime_types = {
            "mp4": "video/mp4",
            "mkv": "video/x-matroska",
            "webm": "video/webm",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
            "aac": "audio/aac",
        }
        
        mime_type = mime_types.get(file_ext.lower(), "application/octet-stream")
        
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size // (1024*1024)} MB" if file_size > 1024*1024 else f"{file_size // 1024} KB"
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            quality_badge = "🎬 HD" if file_type == "video" else "🎵 HQ"
            st.info(f"**{filename}** | {size_str} | {quality_badge}")
        
        with col2:
            st.download_button(
                label=button_text,
                data=data,
                file_name=filename,
                mime=mime_type,
                width='stretch'  # CORREÇÃO AQUI: substituído use_container_width=True
            )
            
    except Exception as e:
        st.error(f"Erro ao criar botão de download: {str(e)}")
        return None

def main():
    # Título e busca
    st.title("🎬 YouTube Downloader HD")
    st.markdown("---")
    
    # Inicializar estado da sessão para controle de loading
    if 'is_downloading' not in st.session_state:
        st.session_state.is_downloading = False
    if 'download_type' not in st.session_state:
        st.session_state.download_type = None
    if 'download_title' not in st.session_state:
        st.session_state.download_title = None
    if 'pending_download' not in st.session_state:
        st.session_state.pending_download = None
    
    # Executar download pendente no thread principal (evita que st.rerun() em thread falhe)
    if st.session_state.pending_download is not None:
        job = st.session_state.pending_download
        st.session_state.pending_download = None
        st.session_state.is_downloading = True
        st.session_state.download_type = job["type"]
        st.session_state.download_title = job["title"]
        
        # Container de progresso: ícone/barra + texto de status
        st.markdown("### ⏳ Progresso do download")
        progress_bar = st.progress(0, text="Preparando...")
        status_text = st.empty()
        status_text.caption("Conectando e obtendo informações do vídeo...")
        
        def progress_hook(d):
            """Callback do yt_dlp para atualizar barra e status em tempo real."""
            status = d.get("status", "")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total and total > 0:
                    pct = min(1.0, downloaded / total)
                    progress_bar.progress(pct, text=f"Baixando... {pct*100:.1f}%")
                    # Formatar tamanho e velocidade
                    mb_d = downloaded / (1024 * 1024)
                    mb_t = total / (1024 * 1024)
                    speed = d.get("speed")
                    eta = d.get("eta")
                    speed_str = f" | {speed/1024/1024:.1f} MB/s" if speed else ""
                    eta_str = f" | ETA: {eta}s" if eta is not None else ""
                    status_text.caption(f"📥 {mb_d:.1f} / {mb_t:.1f} MB{speed_str}{eta_str}")
                else:
                    progress_bar.progress(0.5, text="Baixando...")
                    status_text.caption(f"📥 {downloaded / (1024*1024):.1f} MB recebidos...")
            elif status == "finished":
                progress_bar.progress(1.0, text="Processando arquivo...")
                status_text.caption("Convertendo / finalizando arquivo...")
        
        try:
            if job["type"] == "video":
                file_path, safe_title = download_video_hd(
                    job["url"], job["title"],
                    quality_option=job["quality_option"],
                    callback=progress_hook
                )
            else:
                file_path, safe_title = download_audio_hq(
                    job["url"], job["title"],
                    bitrate=job["bitrate"],
                    callback=progress_hook
                )
            if file_path and os.path.exists(file_path):
                progress_bar.progress(1.0, text="Concluído!")
                status_text.caption("✅ Download finalizado.")
                filename = os.path.basename(file_path)
                qual = job.get("quality_label", "HD") if job["type"] == "video" else job.get("bitrate", "320") + "kbps"
                st.session_state.downloads.append({
                    "path": file_path,
                    "filename": filename,
                    "type": job["type"],
                    "title": job["title"],
                    "quality": qual,
                })
                st.session_state.download_count += 1
                st.success("Download concluído! Role até a seção de downloads.")
        except Exception as e:
            progress_bar.progress(0, text="Erro")
            status_text.caption("")
            st.error(f"Erro no download: {str(e)}")
        finally:
            st.session_state.is_downloading = False
            st.session_state.download_type = None
            st.session_state.download_title = None
        st.rerun()
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações de Qualidade")
        
        st.subheader("🎬 Qualidade do Vídeo")
        video_quality = st.radio(
            "Selecione a qualidade:",
            ["Melhor Disponível", "1080p", "4K (se disponível)", "720p"],
            index=0,
            key="video_quality"
        )
        
        st.subheader("🎵 Qualidade do Áudio")
        audio_bitrate = st.select_slider(
            "Bitrate do MP3:",
            options=["128", "192", "256", "320"],
            value="320",
            key="audio_bitrate"
        )
        st.caption(f"Áudio será baixado em {audio_bitrate}kbps (qualidade máxima)")
        
        st.markdown("---")
        st.header("📊 Estatísticas")
        if 'search_count' not in st.session_state:
            st.session_state.search_count = 0
        if 'download_count' not in st.session_state:
            st.session_state.download_count = 0
            
        st.metric("Buscas realizadas", st.session_state.search_count)
        st.metric("Downloads", st.session_state.download_count)
        
        # Mostrar status atual do download
        if st.session_state.is_downloading:
            st.markdown("---")
            st.subheader("⏳ Status do Download")
            if st.session_state.download_type == "video":
                st.markdown(f"**Baixando vídeo:**")
                st.markdown(f"`{st.session_state.download_title[:30]}...`")
                show_inline_loading("Processando...")
            else:
                st.markdown(f"**Baixando áudio:**")
                st.markdown(f"`{st.session_state.download_title[:30]}...`")
                show_inline_loading("Convertendo...")
        
        st.markdown("---")
        st.info("""
        **Dicas:**
        - 4K só está disponível em vídeos originais
        - 320kbps é a qualidade máxima de áudio
        - Download pode ser mais lento em qualidades altas
        """)
    
    # Mostrar loading overlay se estiver baixando
    if st.session_state.is_downloading:
        if st.session_state.download_type == "video":
            message = f"Baixando vídeo: {st.session_state.download_title[:40]}..."
        else:
            message = f"Baixando áudio: {st.session_state.download_title[:40]}..."
        
        show_loading_overlay(message, st.session_state.download_type)
        st.markdown("---")
    
    # Área principal de busca
    col1, col2, col3 = st.columns([3, 1, 1], vertical_alignment="bottom")
    
    with col1:
        query = st.text_input(
            "Buscar vídeos:",
            placeholder="Digite sua busca (ex: música, tutorial, etc)...", 
            key="search_input", 
            label_visibility="collapsed",
            disabled=st.session_state.is_downloading
        )
    
    with col2:
        if st.button("🔍 **Buscar**", 
                    type="primary",
                    disabled=st.session_state.is_downloading,
                    width='stretch'):  # CORREÇÃO AQUI
            if query:
                st.session_state.search_count += 1
                with st.spinner("Buscando vídeos..."):
                    st.session_state.videos = search_youtube(query)
                    st.session_state.last_query = query
                    st.rerun()
            else:
                st.warning("Digite algo para buscar!")
    
    with col3:
        if st.button("🗑️ **Limpar**", 
                    disabled=st.session_state.is_downloading,
                    width='stretch'):  # CORREÇÃO AQUI
            for key in list(st.session_state.keys()):
                if key not in ['search_count', 'download_count', 'video_quality', 
                              'audio_bitrate', 'is_downloading', 'download_type', 'download_title']:
                    del st.session_state[key]
            st.rerun()
    
    # Inicializar estado da sessão
    if 'videos' not in st.session_state:
        st.session_state.videos = []
    
    if 'downloads' not in st.session_state:
        st.session_state.downloads = []
    
    # Mostrar última busca
    if 'last_query' in st.session_state:
        st.caption(f"Última busca: **{st.session_state.last_query}**")
    
    # Mostrar resultados (apenas se não estiver baixando)
    if st.session_state.videos and not st.session_state.is_downloading:
        st.subheader(f"📺 Resultados encontrados ({len(st.session_state.videos)} vídeos)")
        st.caption(f"🔧 Configurações atuais: Vídeo → {video_quality} | Áudio → {audio_bitrate}kbps")
        
        # Organizar em colunas
        cols = st.columns(3)
        
        for idx, video in enumerate(st.session_state.videos):
            with cols[idx % 3]:
                with st.container():
                    st.markdown(f'<div class="video-card">', unsafe_allow_html=True)
                    
                    # Thumbnail - CORREÇÃO AQUI
                    st.image(video["thumbnail"], width='content')  # width=None substitui use_container_width=True
                    
                    # Título
                    st.markdown(f'<div class="title">{video["title"]}</div>', unsafe_allow_html=True)
                    
                    # Canal
                    st.markdown(f'<div class="channel">📺 {video["channel"]}</div>', unsafe_allow_html=True)
                    
                    # Botões de ação
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button("▶️ Assistir", key=f"watch_{video['video_id']}", 
                                    disabled=st.session_state.is_downloading,
                                    width='stretch'):  # CORREÇÃO AQUI
                            st.markdown(f'[Abrir no YouTube]({video["url"]})', unsafe_allow_html=True)
                    
                    with col_btn2:
                        quality_map = {
                            "Melhor Disponível": "best",
                            "1080p": "1080p",
                            "4K (se disponível)": "4k",
                            "720p": "best"
                        }
                        video_quality_option = quality_map[video_quality]
                        
                        if st.button("📥 Vídeo HD", key=f"video_{video['video_id']}", 
                                    disabled=st.session_state.is_downloading,
                                    width='stretch'):
                            st.session_state.pending_download = {
                                "url": video["url"],
                                "title": video["title"],
                                "type": "video",
                                "quality_option": video_quality_option,
                                "quality_label": video_quality,
                            }
                            st.rerun()
                    
                    # Botão para baixar MP3 HQ
                    if st.button("🎵 MP3 HQ", key=f"audio_{video['video_id']}", 
                                disabled=st.session_state.is_downloading,
                                width='stretch'):
                        st.session_state.pending_download = {
                            "url": video["url"],
                            "title": video["title"],
                            "type": "audio",
                            "bitrate": audio_bitrate,
                        }
                        st.rerun()
                    
                    # Botão para verificar qualidades disponíveis
                    if st.button("📊 Qualidades", key=f"quality_{video['video_id']}", 
                                disabled=st.session_state.is_downloading,
                                width='stretch'):  # CORREÇÃO AQUI
                        with st.spinner("Verificando qualidades disponíveis..."):
                            # Esta função precisa ser implementada
                            st.info("Funcionalidade em desenvolvimento")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mostrar downloads disponíveis (apenas se não estiver baixando)
    if st.session_state.downloads and not st.session_state.is_downloading:
        st.markdown("---")
        st.subheader("📂 Downloads Disponíveis (Alta Qualidade)")
        st.markdown('<div class="download-section">', unsafe_allow_html=True)
        
        video_downloads = [d for d in st.session_state.downloads if d["type"] == "video"]
        audio_downloads = [d for d in st.session_state.downloads if d["type"] == "audio"]
        
        if video_downloads:
            st.markdown("### 🎬 Vídeos")
            for idx, download in enumerate(video_downloads):
                if os.path.exists(download["path"]):
                    st.markdown(f"**{idx+1}. {download['title'][:50]}**")
                    st.markdown(f"<span class='quality-badge'>{download.get('quality', 'HD')}</span>", unsafe_allow_html=True)
                    create_download_button(
                        download["path"],
                        download["filename"],
                        f"💾 Salvar Vídeo ({download.get('quality', 'HD')})",
                        "video"
                    )
                    st.markdown("---")
        
        if audio_downloads:
            st.markdown("### 🎵 Áudios")
            for idx, download in enumerate(audio_downloads):
                if os.path.exists(download["path"]):
                    st.markdown(f"**{idx+1}. {download['title'][:50]}**")
                    st.markdown(f"<span class='quality-badge'>{download.get('quality', 'HQ')}</span>", unsafe_allow_html=True)
                    create_download_button(
                        download["path"],
                        download["filename"],
                        f"💾 Salvar MP3 ({download.get('quality', 'HQ')})",
                        "audio"
                    )
                    st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Botão para limpar todos os downloads
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🗑️ Limpar Todos",
                        disabled=st.session_state.is_downloading,
                        width='stretch'):  # CORREÇÃO AQUI
                for download in st.session_state.downloads:
                    try:
                        if os.path.exists(download["path"]):
                            os.remove(download["path"])
                    except:
                        pass
                st.session_state.downloads = []
                st.success("Todos os downloads foram removidos!")
                time.sleep(1)
                st.rerun()
    
    # Rodapé
    st.markdown("---")
    if st.session_state.is_downloading:
        st.info("⏳ **Download em andamento...** Por favor, aguarde a conclusão.")
    st.caption("🎯 **Qualidade Garantida:** Vídeos em resolução máxima | Áudios em 320kbps MP3")

if __name__ == "__main__":
    main()