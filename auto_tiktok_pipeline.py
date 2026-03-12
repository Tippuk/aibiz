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
# 1. ГЕНЕРАЦИЯ СЦЕНАРИЯ (Groq API)
# ==========================================
def generate_script(topic, groq_api_key):
    prompt = f"""
    Напиши сценарий для TikTok Shorts (максимум 40 слов) на тему: {topic}.
    Ниша: Темная психология.
    Структура:
    1. Жесткий хук (первые 3 секунды): Заставь зрителя остановиться.
    2. Основная мысль: Мрачный факт или техника манипуляции.
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
            response_format={"type": "json_object"}
        )
        
        data = json.loads(completion.choices[0].message.content)
        return dict(data)
    except Exception as e:
        log(f"Ошибка вызова Groq API: {e}")
        return {"hook": "Сбой", "voiceover": "Произошла системная ошибка, скрипт будет перезапущен."}

# ==========================================
# 2. ОЗВУЧКА (TTS) - С защитой от обрывов
# ==========================================
async def create_audio(text, output_file, retries=3):
    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="-5Hz")
            await communicate.save(output_file)
            return  # Если успешно, выходим из цикла
        except Exception as e:
            print(f"    [!] Сбой соединения с сервером голоса (попытка {attempt + 1}/{retries}).")
            if attempt < retries - 1:
                print("    [!] Ждем 5 секунд и пробиваем снова...")
                await asyncio.sleep(5)
            else:
                raise Exception("Критический сбой TTS: Microsoft разорвал соединение. Проверь VPN.")

# ==========================================
# 3. ПОИСК ФОНОВОГО ВИДЕО
# ==========================================
def get_dark_background(api_key, query="dark raining street", output_file="bg.mp4"):
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
def assemble_video(bg_path, audio_path, word_timings, output_path):
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
    
    # 3. Добавление фоновой музыки (dark_music)
    music_files = [f for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')]
    if music_files:
        music_file = random.choice(music_files)
        music_clip = AudioFileClip(os.path.join(MUSIC_DIR, music_file))
        
        if music_clip.duration < audio_duration:
            music_clip = afx.audio_loop(music_clip, duration=audio_duration)
        else:
            music_clip = music_clip.subclip(0, audio_duration)
            
        music_clip = music_clip.fx(afx.volumex, 0.15)
        final_audio = CompositeAudioClip([audio, music_clip])
    else:
        log(f"В папке {MUSIC_DIR} нет mp3 файлов. Музыка добавлена не будет.")
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

# ==========================================
# ЗАПУСК КОНВЕЙЕРА (API)
# ==========================================
def run_pipeline(pexels_api_key, groq_api_key, topics, log_callback=print):
    global _log_cb
    _log_cb = log_callback
    
    for i, topic in enumerate(topics):
        log(f"\n[{i+1}/{len(topics)}] Запуск: {topic}")
        base_name = f"video_{int(time.time())}"
        
        audio_path = os.path.join(TEMP_DIR, f"{base_name}.mp3")
        bg_path = os.path.join(TEMP_DIR, f"{base_name}_bg.mp4")
        final_path = os.path.join(OUTPUT_DIR, f"{base_name}_final.mp4")
        
        log("1. Пишем сценарий с Groq...")
        script_data = generate_script(topic, groq_api_key)
        log(f"План видео: {json.dumps(script_data, ensure_ascii=False, indent=2)}\n")
        voiceover_text = script_data.get("voiceover", "")
        
        log("2. Генерируем озвучку...")
        asyncio.run(create_audio(voiceover_text, audio_path))
        
        log("3. Ищем фон...")
        get_dark_background(api_key=pexels_api_key, query="dark cinematic abstract", output_file=bg_path)
        
        log("4. Вычисляем тайминги слов...")
        timings = get_word_timings(audio_path)
        
        log("5. Монтаж видео (MoviePy)...")
        assemble_video(bg_path, audio_path, timings, final_path)
        
        log(f"✅ Готово! Сохранено в: {final_path}")
        time.sleep(15)  # Пауза между видео

if __name__ == "__main__":
    # Логика для тестов из консоли, если запускать файл напрямую
    run_pipeline(
        pexels_api_key="твой_ключ",
        groq_api_key="твой_ключ",
        topics=["Тестовый топик для консоли"]
    )
