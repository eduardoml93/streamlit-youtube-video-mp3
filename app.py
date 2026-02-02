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

# CSS personalizado
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

def get_video_quality_options(video_url):
    """Obtém as opções de qualidade disponíveis para o vídeo."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            formats = info.get('formats', [])
            
            video_formats = []
            audio_formats = []
            
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    # Formatos com vídeo e áudio
                    resolution = f.get('height', 0)
                    if resolution:
                        video_formats.append({
                            'format_id': f['format_id'],
                            'resolution': resolution,
                            'ext': f.get('ext', 'mp4'),
                            'filesize': f.get('filesize', 0),
                            'note': f"{resolution}p"
                        })
                
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    # Apenas áudio
                    audio_formats.append({
                        'format_id': f['format_id'],
                        'abr': f.get('abr', 0),
                        'ext': f.get('ext', 'mp3'),
                        'filesize': f.get('filesize', 0),
                        'note': f"Áudio {f.get('abr', 0)}kbps"
                    })
            
            # Ordenar por qualidade
            video_formats.sort(key=lambda x: x['resolution'], reverse=True)
            audio_formats.sort(key=lambda x: x['abr'], reverse=True)
            
            return {
                'best_video': video_formats[0] if video_formats else None,
                'best_audio': audio_formats[0] if audio_formats else None,
                'all_video': video_formats[:5],
                'all_audio': audio_formats[:3]
            }
            
    except Exception as e:
        st.error(f"Erro ao obter qualidades: {str(e)}")
        return None

def download_video_hd(video_url, video_title, quality_option="best"):
    """Baixa o vídeo do YouTube na melhor qualidade possível."""
    try:
        if not video_url or not video_url.startswith("http"):
            raise ValueError("URL do vídeo inválida!")

        temp_dir = tempfile.mkdtemp()
        safe_title = sanitize_filename(video_title)
        
        # Configurações para a melhor qualidade possível
        if quality_option == "best":
            # Melhor vídeo + melhor áudio combinados
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [lambda d: None],
                'postprocessor_args': [
                    '-strict', '-2',  # Habilita codecs experimentais
                    '-c:v', 'copy',   # Copia o vídeo sem recompressão
                    '-c:a', 'aac',    # Converte áudio para AAC
                    '-b:a', '320k'    # Bitrate alto para áudio
                ],
                'ffmpeg_location': None,  # Usa ffmpeg do sistema se disponível
            }
        elif quality_option == "4k":
            # Tenta baixar em 4K se disponível
            ydl_opts = {
                'format': 'bestvideo[height>=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height>=1440][ext=mp4]+bestaudio[ext=m4a]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}_4K.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [lambda d: None],
            }
        elif quality_option == "1080p":
            # Especificamente 1080p
            ydl_opts = {
                'format': 'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}_1080p.%(ext)s"),
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [lambda d: None],
            }
        else:
            # Padrão: melhor qualidade disponível
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [lambda d: None],
            }

        with st.spinner(f"Baixando vídeo em alta qualidade: {video_title[:50]}..."):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Se for arquivo separado (vídeo+áudio), mescla
                if not os.path.exists(filename):
                    # Procura pelo arquivo mesclado
                    base_name = os.path.splitext(filename)[0]
                    for ext in ['.mp4', '.mkv', '.webm', '.avi']:
                        if os.path.exists(base_name + ext):
                            filename = base_name + ext
                            break
                
        return filename, safe_title
    except Exception as e:
        st.error(f"Erro ao baixar vídeo: {str(e)}")
        return None, None

def download_audio_hq(video_url, video_title, bitrate="320"):
    """Baixa o áudio do YouTube na melhor qualidade possível."""
    try:
        if not video_url or not video_url.startswith("http"):
            raise ValueError("URL do vídeo inválida!")

        temp_dir = tempfile.mkdtemp()
        safe_title = sanitize_filename(video_title)
        
        # Configurações para áudio de alta qualidade
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, f"{safe_title}.%(ext)s"),
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [lambda d: None],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate,  # 320 para melhor qualidade
            }],
            'postprocessor_args': [
                '-ar', '44100',      # Taxa de amostragem padrão CD
                '-ac', '2',          # Estéreo
                '-b:a', f'{bitrate}k',  # Bitrate especificado
                '-vn',               # Apenas áudio, sem vídeo
            ],
            'extractaudio': True,    # Extrai apenas áudio
            'audioformat': 'mp3',    # Formato de saída
            'keepvideo': False,      # Não mantém o vídeo
        }

        with st.spinner(f"Baixando áudio em alta qualidade ({bitrate}kbps): {video_title[:50]}..."):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                mp3_file = os.path.splitext(filename)[0] + ".mp3"
                
        return mp3_file, safe_title
    except Exception as e:
        st.error(f"Erro ao baixar áudio: {str(e)}")
        return None, None

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
        
        # Obter tamanho do arquivo
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
                use_container_width=True
            )
            
    except Exception as e:
        st.error(f"Erro ao criar botão de download: {str(e)}")
        return None

def main():
    # Título e busca
    st.title("🎬 YouTube Downloader HD")
    st.markdown("---")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações de Qualidade")
        
        # Configurações de vídeo
        st.subheader("🎬 Qualidade do Vídeo")
        video_quality = st.radio(
            "Selecione a qualidade:",
            ["Melhor Disponível", "1080p", "4K (se disponível)", "720p"],
            index=0,
            key="video_quality"
        )
        
        # Configurações de áudio
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
        
        st.markdown("---")
        st.info("""
        **Dicas:**
        - 4K só está disponível em vídeos originais
        - 320kbps é a qualidade máxima de áudio
        - Download pode ser mais lento em qualidades altas
        """)
    
    # Área principal de busca
    col1, col2, col3 = st.columns([3, 1, 1], vertical_alignment="bottom")
    
    with col1:
        query = st.text_input("", placeholder="Digite sua busca (ex: música, tutorial, etc)...", 
                            key="search_input", label_visibility="collapsed")
    
    with col2:
        if st.button("🔍 **Buscar**", use_container_width=True, type="primary"):
            if query:
                st.session_state.search_count += 1
                with st.spinner("Buscando vídeos..."):
                    st.session_state.videos = search_youtube(query)
                    st.session_state.last_query = query
                    st.rerun()
            else:
                st.warning("Digite algo para buscar!")
    
    with col3:
        if st.button("🗑️ **Limpar**", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key not in ['search_count', 'download_count', 'video_quality', 'audio_bitrate']:
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
    
    # Mostrar resultados
    if st.session_state.videos:
        st.subheader(f"📺 Resultados encontrados ({len(st.session_state.videos)} vídeos)")
        st.caption(f"🔧 Configurações atuais: Vídeo → {video_quality} | Áudio → {audio_bitrate}kbps")
        
        # Organizar em colunas
        cols = st.columns(3)
        
        for idx, video in enumerate(st.session_state.videos):
            with cols[idx % 3]:
                with st.container():
                    st.markdown(f'<div class="video-card">', unsafe_allow_html=True)
                    
                    # Thumbnail
                    st.image(video["thumbnail"], use_container_width=True)
                    
                    # Título
                    st.markdown(f'<div class="title">{video["title"]}</div>', unsafe_allow_html=True)
                    
                    # Canal
                    st.markdown(f'<div class="channel">📺 {video["channel"]}</div>', unsafe_allow_html=True)
                    
                    # Botões de ação
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button("▶️ Assistir", key=f"watch_{video['video_id']}", use_container_width=True):
                            st.markdown(f'[Abrir no YouTube]({video["url"]})', unsafe_allow_html=True)
                    
                    with col_btn2:
                        # Determinar qualidade do vídeo baseado na seleção
                        quality_map = {
                            "Melhor Disponível": "best",
                            "1080p": "1080p",
                            "4K (se disponível)": "4k",
                            "720p": "best"
                        }
                        video_quality_option = quality_map[video_quality]
                        
                        if st.button("📥 Vídeo HD", key=f"video_{video['video_id']}", use_container_width=True):
                            with st.spinner(f"Baixando vídeo em {video_quality}..."):
                                file_path, safe_title = download_video_hd(
                                    video["url"], 
                                    video["title"],
                                    quality_option=video_quality_option
                                )
                                if file_path and os.path.exists(file_path):
                                    filename = os.path.basename(file_path)
                                    st.session_state.downloads.append({
                                        "path": file_path,
                                        "filename": filename,
                                        "type": "video",
                                        "title": video["title"],
                                        "quality": video_quality
                                    })
                                    st.session_state.download_count += 1
                                    st.success(f"✅ Vídeo baixado em {video_quality}: {filename}")
                                    time.sleep(1)
                                    st.rerun()
                    
                    # Botão para baixar MP3 HQ
                    if st.button("🎵 MP3 HQ", key=f"audio_{video['video_id']}", use_container_width=True):
                        with st.spinner(f"Baixando áudio em {audio_bitrate}kbps..."):
                            file_path, safe_title = download_audio_hq(
                                video["url"], 
                                video["title"],
                                bitrate=audio_bitrate
                            )
                            if file_path and os.path.exists(file_path):
                                filename = os.path.basename(file_path)
                                st.session_state.downloads.append({
                                    "path": file_path,
                                    "filename": filename,
                                    "type": "audio",
                                    "title": video["title"],
                                    "quality": f"{audio_bitrate}kbps"
                                })
                                st.session_state.download_count += 1
                                st.success(f"✅ Áudio baixado em {audio_bitrate}kbps: {filename}")
                                time.sleep(1)
                                st.rerun()
                    
                    # Botão para verificar qualidades disponíveis
                    if st.button("📊 Qualidades", key=f"quality_{video['video_id']}", use_container_width=True):
                        with st.spinner("Verificando qualidades disponíveis..."):
                            qualities = get_video_quality_options(video["url"])
                            if qualities:
                                with st.expander("Qualidades disponíveis:"):
                                    st.write("**Vídeo:**")
                                    for fmt in qualities.get('all_video', []):
                                        st.code(f"{fmt['note']} - {fmt['ext'].upper()}")
                                    
                                    st.write("**Áudio:**")
                                    for fmt in qualities.get('all_audio', []):
                                        st.code(f"{fmt['note']} - {fmt['ext'].upper()}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mostrar downloads disponíveis
    if st.session_state.downloads:
        st.markdown("---")
        st.subheader("📂 Downloads Disponíveis (Alta Qualidade)")
        st.markdown('<div class="download-section">', unsafe_allow_html=True)
        
        # Separar downloads por tipo
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
            if st.button("🗑️ Limpar Todos", use_container_width=True):
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
    st.caption("🎯 **Qualidade Garantida:** Vídeos em resolução máxima | Áudios em 320kbps MP3")

if __name__ == "__main__":
    main()