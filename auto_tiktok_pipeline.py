import os
# Принудительно указываем путь до движка субтитров
os.environ["IMAGEMAGICK_BINARY"] = r"C:\Program Files\ImageMagick-7.1.2-Q8\magick.exe"
import time
import asyncio
import random
import json
import requests
from groq import Groq
import edge_tts
from tiktok_uploader import upload_video
from faster_whisper import WhisperModel
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, CompositeAudioClip
from moviepy.video.VideoClip import VideoClip
import moviepy.video.fx.all as vfx
import moviepy.audio.fx.all as afx
import numpy as np
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
VOICE = "ru-RU-DmitryNeural"  # Русский мужской реалистичный голос
OUTPUT_DIR = "output_videos"
TEMP_DIR = "temp_files"
MUSIC_DIR = "dark_music"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)

# Глобальный колбек для логов (по умолчанию обычный print)
_log_cb = print

def log(msg):
    _log_cb(msg)

# ==========================================
# ПРОМПТЫ ДЛЯ НИШ
# ==========================================
SYSTEM_PROMPTS = {
    "psychology": (
        "Ты — профессор поведенческой психологии и сценарист. Твоя задача — составить сценарий "
        "разоблачающий токсичные социальные динамики и скрытые мотивы людей ('темная психология')."
    ),
    "finance": (
        "Ты — финансовый аналитик и эксперт по экономической безопасности. Твоя задача — разоблачать "
        "теневые схемы, обманы корпораций и скрытые ловушки банковской системы."
    ),
    "stories": (
        "Ты — мастер сторителлинга и анонимный инсайдер. Твоя задача — написать сценарий для "
        "шокирующей, пугающей или невероятной исповеди, основанной на 'реальных событиях' из сети."
    ),
    "docs": (
        "Ты — исследователь загадок истории и науки. Твоя задача — написать сценарий для "
        "мини-документалки о необъяснимых фактах, заговорах или тайнах нашей планеты."
    )
}

# ==========================================
# НАСТРОЙКИ СТИЛЯ ПО НИШАМ
# ==========================================
NICHE_SETTINGS = {
    "psychology": {
        "voice": "ru-RU-DmitryNeural",
        "rate": "-10%",
        "pitch": "-5Hz",
        "music_file": "everything_is_dead-dark-ambient-soundscape-493696.mp3",
        "hashtags": "#психология #темнаяпсихология #факты #манипуляции",
        "telegram_cta": "\n\nТехники защиты — в нашем Telegram (ссылка в профиле)."
    },
    "finance": {
        "voice": "ru-RU-DmitryNeural",
        "rate": "+5%",
        "pitch": "0Hz",
        "music_file": "paulyudin-suspense-suspense-cinematic-483326.mp3",
        "hashtags": "#финансы #деньги #бизнес #успех #инвестиции",
        "telegram_cta": "\n\nБольше теневых схем в Telegram (ссылка в профиле)."
    },
    "stories": {
        "voice": "ru-RU-SvetlanaNeural",
        "rate": "0%",
        "pitch": "0Hz",
        "music_file": "sigmamusicart-horror-394969.mp3",
        "hashtags": "#истории #reddit #краш #кринж #рассказы",
        "telegram_cta": ""
    },
    "docs": {
        "voice": "ru-RU-DmitryNeural",
        "rate": "-5%",
        "pitch": "-2Hz",
        "music_file": "everything_is_dead-sci-fi-ambient-dark-ambient-496940.mp3",
        "hashtags": "#документалка #факты #наука #история #космос",
        "telegram_cta": "\n\nСекретные архивы в Telegram (ссылка в профиле)."
    }
}

NICHE_VIDEO_QUERIES = {
    "psychology": [
        "dark slow clouds atmospheric", "urban rain night lamp", "mysterious forest fog",
        "macro eye pupil dilation", "black ink in water slow motion", "shadow walking mystery",
        "deep ocean midnight water", "clock ticking close up", "candles burning in dark",
        "abstract dark waves", "brain neurons digital animation", "lonely street light night"
    ],
    "finance": [
        "stock market display data", "business skyscraper glass", "hands typing on luxury laptop",
        "bank gold bars close up", "digital money transfer animation", "trading charts neon",
        "modern office building exterior", "global business network", "currency exchange board",
        "luxury watches close up", "man in suit reflection glass", "abstract grid technology"
    ],
    "stories": [
        "sunny bright park nature", "colorful flower field wind", "happy golden retriever playing",
        "city street sunny bokeh", "delicious food cooking close up", "tropical beach blue water",
        "cute kitten playing garden", "summer sunset sky colors", "vibrant street market",
        "calm lake mountain reflection", "smiling people blurred background", "aesthetic coffee pouring"
    ],
    "docs": [
        "ancient ruins drone view", "space galaxy nebula stars", "scientific laboratory close up",
        "macro circuit board electronic", "old library dusty books", "microscope view cells",
        "mars surface simulation", "pyramids desert sunset", "vintage technology machinery",
        "underwater coral reef life", "forest from above drone", "blueprint drawing animation"
    ]
}

TOPIC_PROMPTS = {
    "psychology": "разоблачающих токсичные социальные динамики, когнитивные искажения и скрытые мотивы людей (темная психология).",
    "finance": "разоблачающих теневую экономику, махинации корпораций и скрытые финансовые ловушки (теневые финансы).",
    "stories": "содержащих анонимные шокирующие исповеди, страшные секреты и невероятные жизненные истории (шокирующие факты).",
    "docs": "раскрывающих величайшие загадки истории, необъяснимые научные факты и микро-документальные сенсации (микро-док)."
}

# ==========================================
# REDDIT ПАРСЕР И АДАПТАЦИЯ (Stories)
# ==========================================
def get_reddit_story():
    """Парсит топ постов с Reddit (Stories) через прямой JSON запрос"""
    used_reddit_file = "used_reddit_posts.txt"
    used_ids = set()
    if os.path.exists(used_reddit_file):
        with open(used_reddit_file, "r") as f:
            used_ids = {line.strip() for line in f if line.strip()}
    
    subreddits = ["TrueOffMyChest", "confessions", "AmItheAsshole", "pettyrevenge"]
    random.shuffle(subreddits)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for sub_name in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/top.json?t=week&limit=15"
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                continue
                
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            for post in posts:
                submission = post.get('data', {})
                post_id = submission.get('id')
                
                if post_id and post_id not in used_ids and not submission.get('over_18', False):
                    title = submission.get('title')
                    text = submission.get('selftext')
                    
                    if not text: # Пропускаем пустые посты
                        continue

                    # Сохраняем ID как использованный
                    with open(used_reddit_file, "a") as f:
                        f.write(post_id + "\n")
                    return title, text
                    
        except Exception as e:
            log(f"Ошибка при парсинге r/{sub_name}: {e}")
            continue
            
    return None, None

def adapt_reddit_story(title, text, groq_api_key):
    """Адаптирует Reddit-историю под TikTok формат через Groq"""
    prompt = f"""
    Ты редактор для TikTok. Твоя задача — перевести эту Reddit-историю на русский язык и адаптировать её для озвучки (до 150-200 слов).
    
    КРИТИЧЕСКИЕ ТРЕБОВАНИЯ:
    1. Текст должен быть написан ИСКЛЮЧИТЕЛЬНО на чистом, литературном и естественном русском языке. 
    2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать английские буквы, слова, транслит или склеивать слова из разных языков (никаких "которые.maskировали"). 
    3. Вычитай текст на наличие орфографических ошибок и артефактов машинного перевода.
    4. Сделай максимально интригующее первое предложение (хук).
    5. Убери лишнюю воду, оставь только самую суть, драму и концовку.
    6. Пиши от первого лица. Текст должен звучать живо и эмоционально.
    
    ЗАГОЛОВОК: {title}
    ТЕКСТ: {text}
    """
    
    try:
        client = Groq(api_key=groq_api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            timeout=60.0
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        log(f"Ошибка адаптации Groq: {e}")
        return None

# ==========================================
# 1. ГЕНЕРАЦИЯ СЦЕНАРИЯ (Groq API)
# ==========================================
def generate_script(topic, groq_api_key, niche="psychology"):
    system_instruction = SYSTEM_PROMPTS.get(niche, SYSTEM_PROMPTS["psychology"])
    
    prompt = f"""
    Напиши сценарий для TikTok Shorts (максимум 40 слов) на тему: {topic}.
    Инструкция: {system_instruction}
    Структура:
    1. Жесткий хук (первые 3 секунды): Заставь зрителя остановиться.
    2. Основная мысль: Мрачный факт, техника или история.
    3. Вывод/Призыв: Загадочное завершение.
    Выдай строго в формате JSON с двумя ключами: 
    'hook' (короткий текст для видеоряда) и 
    'voiceover' (полный текст для озвучки на русском языке, без ремарок и цифр).
    """
    
    try:
        client = Groq(api_key=groq_api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=30.0
        )
        
        data = json.loads(completion.choices[0].message.content)
        return dict(data)
    except Exception as e:
        log(f"Ошибка вызова Groq API (сценарий): {e}")
        return {"hook": "Сбой", "voiceover": "Произошла системная ошибка, скрипт будет перезапущен."}

def generate_topics(groq_api_key, niche="psychology", count=10):
    """Генерирует новые темы для видео через Groq API"""
    niche_desc = TOPIC_PROMPTS.get(niche, TOPIC_PROMPTS["psychology"])
    system_prompt = (
        "Ты — профессиональный сценарист. Твоя задача — составить список тем для "
        f"коротких видео, {niche_desc} "
        f"Выдай ровно {count} тем. Каждая тема — это цепляющий, циничный заголовок (1 предложение). "
        "Ответь СТРОГО списком, каждая тема с новой строки, без цифр, без вступлений и без предупреждений об этике."
    )
    
    try:
        client = Groq(api_key=groq_api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Сгенерируй {count} тем."}
            ],
            max_tokens=6000,
            timeout=80.0
        )
        
        topics_raw = completion.choices[0].message.content.strip()
        topics = [t.strip() for t in topics_raw.split('\n') if t.strip()]
        return topics
    except Exception as e:
        log(f"Критическая ошибка Groq (темы): {str(e)}")
        return []

# ==========================================
# 2. ОЗВУЧКА (TTS) - С защитой от обрывов
# ==========================================
async def create_audio(text, output_file, voice="ru-RU-DmitryNeural", rate="0%", pitch="0Hz", retries=3):
    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_file)
            return  # Если успешно, выходим из цикла
        except Exception as e:
            log(f"    [!] Сбой соединения с сервером голоса (попытка {attempt + 1}/{retries}).")
            if attempt < retries - 1:
                log("    [!] Ждем 5 секунд и пробиваем снова...")
                await asyncio.sleep(5)
            else:
                raise Exception("Критический сбой TTS: Microsoft разорвал соединение. Проверь VPN.")

# ==========================================
# 3. ПОИСК ФОНОВОГО ВИДЕО
# ==========================================
def get_background_video(api_key, query="dark raining street", output_file="bg.mp4"):
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Ошибка API Pexels: {response.status_code} - {response.text}")
        
    videos = response.json().get('videos', [])
    
    if not videos:
        raise Exception("Видео не найдено. Проверьте запрос или API ключ.")
        
    valid_videos = [v for v in videos if v['width'] < v['height']]
    chosen_video = random.choice(valid_videos if valid_videos else videos)
    
    download_url = next((f['link'] for f in chosen_video['video_files'] if f['height'] >= 1080), 
                        chosen_video['video_files'][0]['link'])
    
    with open(output_file, 'wb') as f:
        f.write(requests.get(download_url).content)
        
    return output_file

# ==========================================
# 4. ТРАНСКРИБАЦИЯ (ТАЙМИНГИ СЛОВ)
# ==========================================
def get_word_timings(audio_file):
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_file, word_timestamps=True)
    
    words = []
    for segment in segments:
        for word in segment.words:
            words.append({
                "word": word.word.strip().upper(),
                "start": word.start,
                "end": word.end
            })
    return words

# ==========================================
# 5. СБОРКА И МОНТАЖ ВИДЕО
# ==========================================
def assemble_video(bg_path, audio_path, word_timings, output_path, music_file=None):
    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration
    
    bg_video = VideoFileClip(bg_path)
    
    # 1. Центрирование и обрезка до пропорций 9:16 (1080x1920)
    target_w, target_h = 1080, 1920
    bg_ratio = bg_video.w / bg_video.h
    target_ratio = target_w / target_h
    
    if bg_ratio > target_ratio:
        new_w = int(bg_video.h * target_ratio)
        x_center = bg_video.w / 2
        bg_video = vfx.crop(bg_video, x_center=x_center, y_center=bg_video.h/2, width=new_w, height=bg_video.h)
    else:
        new_h = int(bg_video.w / target_ratio)
        bg_video = vfx.crop(bg_video, x_center=bg_video.w/2, y_center=bg_video.h/2, width=bg_video.w, height=new_h)
        
    bg_video = bg_video.resize((target_w, target_h))
    
    # 2. Обработка продолжительности (зацикливание)
    if bg_video.duration < audio_duration:
        bg_video = vfx.loop(bg_video, duration=audio_duration)
    else:
        bg_video = bg_video.subclip(0, audio_duration)
        
    # Мрачная цветокоррекция
    bg_video = bg_video.fx(vfx.colorx, 0.4)
    
    # 3. Добавление фоновой музыки
    if music_file:
        music_path = os.path.join(MUSIC_DIR, music_file)
        if os.path.exists(music_path):
            music_clip = AudioFileClip(music_path)
            
            if music_clip.duration < audio_duration:
                music_clip = afx.audio_loop(music_clip, duration=audio_duration)
            else:
                music_clip = music_clip.subclip(0, audio_duration)
                
            music_clip = music_clip.fx(afx.volumex, 0.15)
            final_audio = CompositeAudioClip([audio, music_clip])
        else:
            log(f"Музыкальный файл {music_path} не найден. Используем только голос.")
            final_audio = audio
    else:
        final_audio = audio
        
    bg_video = bg_video.set_audio(final_audio)
    
    # 4. Продуктивный генератор субтитров (Один слой, предотвращает перегрузку RAM)
    txt_clips = {}
    for ww in word_timings:
        word = ww['word']
        if word not in txt_clips:
            # Создаем TextClip раз и навсегда. Кэшируем готовый numpy array кадра и маски
            tc = TextClip(word, fontsize=100, color='white', font='Impact', 
                          stroke_color='black', stroke_width=3)
            # Центрируем текст на полномасштабном холсте 1080x1920
            comp_tc = CompositeVideoClip([tc.set_position('center')], size=(target_w, target_h)).set_duration(0.1)
            txt_clips[word] = {
                "frame": comp_tc.get_frame(0),
                "mask": comp_tc.mask.get_frame(0)
            }

    def make_text_frame(t):
        for ww in word_timings:
            if ww['start'] <= t <= ww['end']:
                return txt_clips[ww['word']]["frame"]
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)

    def make_text_mask(t):
        for ww in word_timings:
            if ww['start'] <= t <= ww['end']:
                return txt_clips[ww['word']]["mask"]
        return np.zeros((target_h, target_w), dtype=float)

    subs_clip = VideoClip(make_text_frame, duration=audio_duration)
    # ismask=True обязательно для маски!
    subs_clip = subs_clip.set_mask(VideoClip(make_text_mask, duration=audio_duration, ismask=True))
    
    final_video = CompositeVideoClip([bg_video, subs_clip])
    
    final_video.write_videofile(
        output_path, 
        fps=30, 
        codec="libx264", 
        audio_codec="aac", 
        threads=4,
        preset="ultrafast",
        logger=None # Отключаем стандартный прогресс-бар MoviePy в консоль
    )

def get_next_video_id(niche="psychology"):
    """Читает и инкрементирует счетчик видео из файла video_counter_{niche}.txt"""
    counter_file = f"video_counter_{niche}.txt"
    if not os.path.exists(counter_file):
        with open(counter_file, "w") as f:
            f.write("1")
        return 1
    
    try:
        with open(counter_file, "r") as f:
            current_id = int(f.read().strip())
        
        next_id = current_id + 1
        with open(counter_file, "w") as f:
            f.write(str(next_id))
        
        return current_id
    except:
        return int(time.time()) # Фолбэк на таймстемп при ошибке

# ==========================================
# ЗАПУСК КОНВЕЙЕРА (API)
# ==========================================
def run_pipeline(pexels_api_key, groq_api_key, topics, niche="psychology", log_callback=print, stop_event=None, pause_event=None):
    global _log_cb
    _log_cb = log_callback
    
    used_topics_file = f"used_topics_{niche}.txt"
    niche_output_dir = os.path.join(OUTPUT_DIR, niche)
    os.makedirs(niche_output_dir, exist_ok=True)
    
    for i, topic in enumerate(topics):
        try:
            # 0. Проверка на паузу
            if pause_event:
                pause_event.wait()
            
            # 0. Проверка на остановку
            if stop_event and stop_event.is_set():
                log("[System] Работа конвейера прервана пользователем.")
                break

            log(f"\n[{i+1}/{len(topics)}] Запуск [{niche}]: {topic}")
            video_id = get_next_video_id(niche)
            base_name = f"video_{int(time.time())}" # Для временных файлов оставляем таймстемп
            
            audio_path = os.path.join(TEMP_DIR, f"{base_name}.mp3")
            bg_path = os.path.join(TEMP_DIR, f"{base_name}_bg.mp4")
            final_path = os.path.join(niche_output_dir, f"{video_id}.mp4")
            
            log("1. Пишем сценарий с Groq...")
            if niche == "stories":
                # Для историй тема — это уже готовый текст озвучки
                script_data = {"hook": "История", "voiceover": topic}
            else:
                script_data = generate_script(topic, groq_api_key, niche)
            
            if stop_event and stop_event.is_set(): break

            log(f"План видео: {json.dumps(script_data, ensure_ascii=False, indent=2)}\n")
            voiceover_text = script_data.get("voiceover", "")
            
            settings = NICHE_SETTINGS.get(niche, NICHE_SETTINGS["psychology"])
            
            log("2. Генерируем озвучку...")
            asyncio.run(create_audio(voiceover_text, audio_path, 
                                     voice=settings["voice"], 
                                     rate=settings["rate"], 
                                     pitch=settings["pitch"]))
            if stop_event and stop_event.is_set(): break
            
            log("3. Ищем фон...")
            queries = NICHE_VIDEO_QUERIES.get(niche, NICHE_VIDEO_QUERIES["psychology"])
            random_query = random.choice(queries)
            log(f"Выбран запрос для видео: {random_query}")
            
            get_background_video(api_key=pexels_api_key, 
                                 query=random_query, 
                                 output_file=bg_path)
            if stop_event and stop_event.is_set(): break
            
            log("4. Вычисляем тайминги слов...")
            timings = get_word_timings(audio_path)
            if stop_event and stop_event.is_set(): break
            
            log("5. Монтаж видео (MoviePy)...")
            assemble_video(bg_path, audio_path, timings, final_path, 
                           music_file=settings["music_file"])
            
            log(f"✅ Готово! Сохранено в: {final_path}")
            
            # --- ИНТЕГРАЦИЯ TIKTOK ---
            log("6. Автозагрузка в TikTok...")
            from tiktok_uploader import upload_video
            hashtags = settings.get("hashtags", "#tiktok")
            cta = settings.get("telegram_cta", "")
            title_text = script_data.get("title", niche)
            
            final_caption = f"{title_text}{cta}"
            
            try:
                # Запускаем асинхронную загрузку с привязкой к нише
                success = asyncio.run(upload_video(final_path, final_caption, hashtags, niche))
                if success:
                    log(f"🚀 Видео успешно загружено в аккаунт '{niche}'!")
                else:
                    log(f"⚠️ Шаг загрузки для '{niche}' пропущен или завершился с ошибкой.")
            except Exception as upload_err:
                log(f"⚠️ Ошибка вызова загрузчика: {upload_err}")
            
            # Сохраняем тему в список отработанных
            try:
                with open(used_topics_file, "a", encoding="utf-8") as f:
                    f.write(topic + "\n")
            except Exception as e:
                log(f"Ошибка сохранения темы в {used_topics_file}: {e}")
            
            if i < len(topics) - 1:
                log("Пауза 15 секунд перед следующим видео...")
                # Заменяем обычный sleep на ожидание события с таймаутом, чтобы мгновенно реагировать на стоп
                if stop_event:
                    if stop_event.wait(15): break
                else:
                    time.sleep(15)
        except Exception as e:
            log(f"❌ Ошибка при обработке темы '{topic}': {e}")
            continue

if __name__ == "__main__":
    # Логика для тестов из консоли, если запускать файл напрямую
    run_pipeline(
        pexels_api_key="твой_ключ",
        groq_api_key="твой_ключ",
        topics=["Тестовый топик для консоли"]
    )
