import os
import json
import threading
import customtkinter as ctk
import tkinter as tk
from datetime import datetime
from PIL import Image

from auto_tiktok_pipeline import run_pipeline, generate_topics, get_reddit_story, adapt_reddit_story
from stats_manager import log_generation, get_performance_stats
from asset_manager import get_output_videos
import tiktok_uploader
import asyncio

CONFIG_FILE = "config.json"

# Design Tokens (Reference: Stitch API)
BG_COLOR = "#111621"
CARD_COLOR = "#1a2233"
BORDER_COLOR = "#242f47"
PRIMARY_COLOR = "#2463eb"
TEXT_COLOR = "#f1f5f9"
SECONDARY_TEXT = "#94a3b8"
SUCCESS_COLOR = "#10b981"
WARN_COLOR = "#f59e0b"
PROCESS_COLOR = "#ffffff"
ERROR_COLOR = "#ef4444"
ORANGE_COLOR = "#ea580c" # For Reddit button

LOCALIZATION = {
    "RU": {
        "title": "TikTok Automation Pro",
        "nav_engine": "ДВИЖОК АВТОМАТИЗАЦИИ",
        "dashboard": "Панель управления",
        "assets": "Библиотека ассетов",
        "history": "История работы",
        "api_config": "КОНФИГУРАЦИЯ API",
        "pexels_key": "Ключ Pexels API",
        "groq_key": "Ключ Groq Cloud",
        "save_settings": "Сохранить настройки",
        "factory_title": "Content Factory",
        "factory_subtitle": "Масштабируйте свои каналы с помощью AI-видео.",
        "start_pipeline": "▶ Запустить конвейер",
        "niche_psych": "🧠 Психология",
        "niche_finance": "💰 Финансы",
        "niche_stories": "📖 Истории",
        "niche_docs": "📜 Документалистика",
        "reddit_btn": "🤖 Парсить историю с Reddit",
        "count_label": "Кол-во:",
        "gen_btn": "✨ Генерировать темы",
        "active_theme": "ТЕКУЩАЯ АКТИВНАЯ ТЕМА",
        "workflow_script": "Скрипт воркфлоу / Список тем",
        "smart_console": "> УМНАЯ КОНСОЛЬ",
        "pause": "Пауза",
        "stop": "Стоп",
        "engine_perf": "ПРОИЗВОДИТЕЛЬНОСТЬ ДВИЖКА",
        "vids_gen": "ВИДЕО СОЗДАНО",
        "avg_eng": "СР. ВОВЛЕЧЕННОСТЬ",
        "account_status": "АКТИВНЫЙ АККАУУНТ",
        "active": "Активен",
        "offline": "Нужна авторизация",
        "open_file": "Открыть файл",
        "rendering": "Рендеринг:",
        "waiting": "Ожидание запуска...",
        "cut": "Вырезать",
        "copy": "Копировать",
        "paste": "Вставить",
        "select_all": "Выделить всё",
        "admin_user": "Пользователь",
        "no_videos": "Видео не найдены в output_videos/",
        "history_empty": "Логи истории появятся здесь после запуска.",
        "followers_label": "Подписчики",
        "likes_label": "Лайки",
        "check_comments": "Комментарии",
        "auth_short": "Нужен вход",
        "generating": "⏳ Генерирую темы...",
        "launching": "🚀 Запуск конвейера..."
    },
    "EN": {
        "title": "TikTok Automation Pro",
        "nav_engine": "AUTOMATION ENGINE",
        "dashboard": "Dashboard",
        "assets": "Asset Library",
        "history": "History",
        "api_config": "API CONFIGURATION",
        "pexels_key": "Pexels API Key",
        "groq_key": "Groq Cloud Key",
        "save_settings": "Save Settings",
        "factory_title": "Content Factory",
        "factory_subtitle": "Scale your automation channels with AI-generated shorts.",
        "start_pipeline": "▶ Start Pipeline",
        "niche_psych": "🧠 Psychology",
        "niche_finance": "💰 Finance",
        "niche_stories": "📖 Stories",
        "niche_docs": "📜 Documentaries",
        "reddit_btn": "🤖 Parse Story from Reddit",
        "count_label": "Count:",
        "gen_btn": "✨ Generate Themes",
        "active_theme": "CURRENT ACTIVE THEME",
        "workflow_script": "Workflow Script / Themes List",
        "smart_console": "> SMART CONSOLE",
        "pause": "Pause",
        "stop": "Stop",
        "engine_perf": "ENGINE PERFORMANCE",
        "vids_gen": "VIDEOS GENERATED",
        "avg_eng": "AVG. ENGAGEMENT",
        "account_status": "ACTIVE ACCOUNT",
        "active": "Active",
        "offline": "Needs Auth",
        "open_file": "Open File",
        "rendering": "Rendering:",
        "waiting": "Waiting for start...",
        "cut": "Cut",
        "copy": "Copy",
        "paste": "Paste",
        "select_all": "Select All",
        "admin_user": "User",
        "no_videos": "No videos found in output_videos/",
        "history_empty": "History logs will appear here after the first run.",
        "followers_label": "Followers",
        "likes_label": "Likes",
        "check_comments": "Comments",
        "auth_short": "Login Required",
        "generating": "⏳ Generating themes...",
        "launching": "🚀 Launching pipeline..."
    }
}

def t(key, lang="RU"):
    return LOCALIZATION.get(lang, LOCALIZATION["EN"]).get(key, key)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TikTok Automation Pro")
        self.geometry("1100x750")
        
        # Configure Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Config variables
        self.pexels_key_var = ctk.StringVar()
        self.groq_key_var = ctk.StringVar()
        self.lang = "RU"
        self.active_niche = "psychology"
        self.current_theme_text = ctk.StringVar(value=t("waiting", self.lang))
        self.active_account_var = ctk.StringVar(value="@loading...")
        self.followers_var = ctk.StringVar(value="0")
        self.likes_var = ctk.StringVar(value="0")
        
        self.load_config()

        # UI References
        self.niche_textboxes = {}
        self.niche_count_comboboxes = {}
        self.niche_gen_buttons = {}
        self.niche_start_buttons = {}
        self.nav_buttons = {}
        self.niche_nav_labels = {} # For text-based tabs

        # Thread control
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        self._setup_layout()

    def _setup_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=BG_COLOR, border_color=BORDER_COLOR, border_width=1)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Right Parent (Header + Content)
        self.right_parent = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_COLOR)
        self.right_parent.grid(row=0, column=1, sticky="nsew")
        self.right_parent.grid_columnconfigure(0, weight=1)
        self.right_parent.grid_rowconfigure(2, weight=1) # Row 2 is Scrollable Content

        self._build_sidebar()
        self._build_header()
        
        # Main Content Area (Scrollable by default)
        self.content_container = ctk.CTkScrollableFrame(self.right_parent, corner_radius=0, fg_color=BG_COLOR)
        self.content_container.grid(row=2, column=0, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)

        self._show_dashboard() # Default view

    def _build_header(self):
        # Header Container
        self.header_frame = ctk.CTkFrame(self.right_parent, height=65, fg_color=BG_COLOR, border_width=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(0, weight=1)

        # Bottom Border Line
        self.header_line = ctk.CTkFrame(self.right_parent, height=1, fg_color=BORDER_COLOR)
        self.header_line.grid(row=1, column=0, sticky="ew")

        # Right side icons
        icons_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        icons_frame.pack(side="right", padx=30)

        # Notification
        ctk.CTkLabel(icons_frame, text="🔔", font=("Inter", 18), text_color=SECONDARY_TEXT).pack(side="left", padx=15)
        
        # Comments/Messages
        comments_btn = ctk.CTkLabel(icons_frame, text="💬", font=("Inter", 18), text_color=SECONDARY_TEXT, cursor="hand2")
        comments_btn.pack(side="left", padx=15)
        comments_btn.bind("<Button-1>", lambda e: self._open_manual_tiktok("https://www.tiktok.com/messages"))

        # Settings
        settings_btn = ctk.CTkLabel(icons_frame, text="⚙️", font=("Inter", 18), text_color=SECONDARY_TEXT, cursor="hand2")
        settings_btn.pack(side="left", padx=15)
        settings_btn.bind("<Button-1>", lambda e: self._open_settings())

        # Profile
        profile_frame = ctk.CTkFrame(icons_frame, fg_color="transparent")
        profile_frame.pack(side="left", padx=(15, 0))
        ctk.CTkLabel(profile_frame, text=self.t("admin_user"), font=("Inter", 13, "bold"), text_color=TEXT_COLOR).pack(side="left", padx=5)
        ctk.CTkLabel(profile_frame, text="👤", font=("Inter", 20), text_color=PRIMARY_COLOR).pack(side="left")

    def _open_settings(self):
        # Simple modal for language switching
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("api_config", self.lang))
        dialog.geometry("300x200")
        dialog.after(10, dialog.lift) # Focus

        ctk.CTkLabel(dialog, text="Language / Язык", font=("Inter", 14, "bold")).pack(pady=20)
        
        lang_cb = ctk.CTkComboBox(dialog, values=["English", "Русский"], command=self._change_lang)
        lang_cb.set("Русский" if self.lang == "RU" else "English")
        lang_cb.pack(pady=10)

    def _change_lang(self, val):
        self.lang = "RU" if val == "Русский" else "EN"
        # Refresh UI
        self._setup_layout()
        self.log_message(f"[System] Language changed to {val}")

    def t(self, key):
        return t(key, self.lang)

    def _build_sidebar(self):
        # Logo Area
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(padx=25, pady=(30, 40), fill="x")
        
        logo_icon = ctk.CTkLabel(logo_frame, text="🧠", font=("Inter", 24), fg_color=PRIMARY_COLOR, width=32, height=32, corner_radius=8)
        logo_icon.pack(side="left", padx=(0, 10))
        
        logo_text = ctk.CTkLabel(logo_frame, text="Auto Pro", font=("Inter", 18, "bold"), text_color=TEXT_COLOR)
        logo_text.pack(side="left")

        # Navigation
        nav_header = ctk.CTkLabel(self.sidebar, text=self.t("nav_engine"), font=("Inter", 11, "bold"), text_color=SECONDARY_TEXT)
        nav_header.pack(padx=25, pady=(0, 10), anchor="w")

        self.nav_buttons["dashboard"] = self._create_nav_button(self.t("dashboard"), "📊", self._show_dashboard)
        self.nav_buttons["assets"] = self._create_nav_button(self.t("assets"), "🎬", self._show_assets)
        self.nav_buttons["history"] = self._create_nav_button(self.t("history"), "📜", self._show_history)

        # API Configuration Block
        api_header = ctk.CTkLabel(self.sidebar, text=self.t("api_config"), font=("Inter", 11, "bold"), text_color=SECONDARY_TEXT)
        api_header.pack(padx=25, pady=(40, 10), anchor="w")

        api_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        api_frame.pack(padx=25, fill="x")

        # Pexels
        ctk.CTkLabel(api_frame, text=self.t("pexels_key"), font=("Inter", 12, "bold"), text_color=SECONDARY_TEXT).pack(anchor="w", pady=(0, 5))
        self.pexels_entry = ctk.CTkEntry(api_frame, textvariable=self.pexels_key_var, show="*", height=38, fg_color=CARD_COLOR, border_color=BORDER_COLOR)
        self.pexels_entry.pack(fill="x", pady=(0, 15))
        self._add_context_menu(self.pexels_entry._entry)

        # Groq
        ctk.CTkLabel(api_frame, text=self.t("groq_key"), font=("Inter", 12, "bold"), text_color=SECONDARY_TEXT).pack(anchor="w", pady=(0, 5))
        self.groq_entry = ctk.CTkEntry(api_frame, textvariable=self.groq_key_var, show="*", height=38, fg_color=CARD_COLOR, border_color=BORDER_COLOR)
        self.groq_entry.pack(fill="x", pady=(0, 25))
        self._add_context_menu(self.groq_entry._entry)

        # Save Button
        self.save_btn = ctk.CTkButton(api_frame, text=self.t("save_settings"), command=self.save_config, 
                                      fg_color=PRIMARY_COLOR, hover_color="#1d4ed8", font=("Inter", 14, "bold"), height=42)
        self.save_btn.pack(fill="x")

        # TikTok Account Status Block
        self.status_block = ctk.CTkFrame(self.sidebar, fg_color=CARD_COLOR, corner_radius=12, border_color=BORDER_COLOR, border_width=1)
        self.status_block.pack(padx=15, pady=30, fill="x", side="bottom")
        
        ctk.CTkLabel(self.status_block, text=self.t("account_status"), font=("Inter", 10, "bold"), text_color=SECONDARY_TEXT).pack(pady=(12, 5))
        
        acc_info = ctk.CTkFrame(self.status_block, fg_color="transparent")
        acc_info.pack(pady=(0, 12))
        
        self.status_indicator = ctk.CTkLabel(acc_info, text="●", font=("Inter", 14), text_color=ERROR_COLOR)
        self.status_indicator.pack(side="left", padx=5)
        
        acc_label = ctk.CTkLabel(acc_info, textvariable=self.active_account_var, font=("Inter", 12, "bold"), 
                                 text_color=PRIMARY_COLOR, cursor="hand2")
        acc_label.pack(side="left")
        acc_label.bind("<Button-1>", lambda e: self._open_manual_tiktok())

        # Followers & Likes stats
        stats_frame = ctk.CTkFrame(self.status_block, fg_color="transparent")
        stats_frame.pack(fill="x", padx=15, pady=(0, 12))
        
        ctk.CTkLabel(stats_frame, text="👥", font=("Inter", 11)).pack(side="left")
        ctk.CTkLabel(stats_frame, textvariable=self.followers_var, font=("Inter", 11, "bold"), text_color=TEXT_COLOR).pack(side="left", padx=(2, 10))
        
        ctk.CTkLabel(stats_frame, text="❤️", font=("Inter", 11)).pack(side="left")
        ctk.CTkLabel(stats_frame, textvariable=self.likes_var, font=("Inter", 11, "bold"), text_color=TEXT_COLOR).pack(side="left", padx=(2, 0))

    def _create_nav_button(self, text, icon, command):
        btn = ctk.CTkButton(self.sidebar, text=f"  {icon}  {text}", command=command,
                            fg_color="transparent", hover_color=BORDER_COLOR,
                            text_color=SECONDARY_TEXT, anchor="w",
                            font=("Inter", 14, "bold"), height=40, corner_radius=8)
        btn.pack(padx=15, pady=2, fill="x")
        return btn

    def _update_account_status(self, niche=None):
        if not niche: niche = self.active_niche
        
        state_file = f"state_{niche}.json"
        exists = os.path.exists(state_file)
        
        self.status_indicator.configure(text_color=SUCCESS_COLOR if exists else ERROR_COLOR)
        
        if exists:
            # We will update these asynchronously via _async_update_account_metrics
            # For now, keep the loading text if it was just switched
            if "@" not in self.active_account_var.get() or niche in self.active_account_var.get():
                pass # Already loading or set
            
            # Trigger background update
            threading.Thread(target=self._async_update_account_metrics, args=(niche,), daemon=True).start()
        else:
            self.active_account_var.set(self.t("offline"))
            self.followers_var.set("0")
            self.likes_var.set("0")

    def _async_update_account_metrics(self, niche):
        """Фоновый поток для получения статистики аккаунта"""
        try:
            data = asyncio.run(tiktok_uploader.get_account_info(niche))
            if data:
                if "error" in data:
                    self.after(0, lambda: self.active_account_var.set(self.t("auth_short")))
                else:
                    self.after(0, lambda d=data: self._apply_account_metrics(d))
        except Exception as e:
            print(f"Error in _async_update_account_metrics: {e}")

    def _apply_account_metrics(self, data):
        self.active_account_var.set(data.get("nickname", "@error"))
        self.followers_var.set(data.get("followers", "0"))
        self.likes_var.set(data.get("likes", "0"))

    def _open_manual_tiktok(self, url="https://www.tiktok.com/"):
        """Потокобезопасный запуск браузера для ручных действий"""
        threading.Thread(target=lambda: asyncio.run(tiktok_uploader.open_manual_session(self.active_niche, url)), daemon=True).start()

    def _update_nav_selection(self, active_key):
        for key, btn in self.nav_buttons.items():
            if key == active_key:
                btn.configure(fg_color="#1b2a4a", text_color=PRIMARY_COLOR)
            else:
                btn.configure(fg_color="transparent", text_color=SECONDARY_TEXT)

    def _clear_content(self):
        # In the new Ribbon Flow, we simply clear everything inside the scrollable content_container
        for widget in self.content_container.winfo_children():
            widget.destroy()

    def _show_dashboard(self):
        self._update_nav_selection("dashboard")
        self._clear_content()

        # Dashboard Header with Title and Start Button
        dash_header = ctk.CTkFrame(self.content_container, fg_color="transparent")
        dash_header.pack(fill="x", padx=40, pady=(30, 20))

        title_frame = ctk.CTkFrame(dash_header, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text=self.t("factory_title"), font=("Inter", 26, "bold"), text_color=TEXT_COLOR).pack(anchor="w")
        ctk.CTkLabel(title_frame, text=self.t("factory_subtitle"), 
                     font=("Inter", 14), text_color=SECONDARY_TEXT).pack(anchor="w")

        self.pipeline_btn = ctk.CTkButton(dash_header, text=self.t("start_pipeline"), command=self.start_pipeline_thread,
                                         fg_color=PRIMARY_COLOR, hover_color="#1d4ed8", font=("Inter", 15, "bold"), 
                                         height=42, corner_radius=10)
        self.pipeline_btn.pack(side="right")

        # Custom Niche Navigation (Text Tabs)
        self._build_niche_nav()

        # Niche-specific controls will be packed here
        self._build_niche_controls(self.active_niche)

        # Engine Performance & Console (At the bottom of the ribbon)
        self._build_stats_and_console(self.content_container)

        self._update_account_status(self.active_niche)

    def _build_niche_nav(self):
        nav_frame = ctk.CTkFrame(self.content_container, fg_color="transparent", height=40)
        nav_frame.pack(fill="x", padx=40, pady=(0, 10))
        nav_frame.pack_propagate(False)

        niches = [
            ("psychology", self.t("niche_psych")),
            ("finance", self.t("niche_finance")),
            ("stories", self.t("niche_stories")),
            ("docs", self.t("niche_docs"))
        ]

        for nid, name in niches:
            lbl_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
            lbl_frame.pack(side="left", padx=(0, 30))
            
            lbl = ctk.CTkLabel(lbl_frame, text=name, font=("Inter", 14, "bold"), text_color=SECONDARY_TEXT, cursor="hand2")
            lbl.pack(pady=(0, 5))
            lbl.bind("<Button-1>", lambda e, n=nid: self._switch_niche(n))
            
            underline = ctk.CTkFrame(lbl_frame, height=2, fg_color="transparent", width=40)
            underline.pack(fill="x")
            
            self.niche_nav_labels[nid] = (lbl, underline)

    def _switch_niche(self, niche_id):
        self.active_niche = niche_id
        # In the new Ribbon Flow, switching niche means redraw the whole dashboard 
        # to maintain the correct sequence of elements
        self._show_dashboard()

    def _build_niche_controls(self, niche_id):
        # Container for niche work (this replaces the old scrollable frame logic)
        work_area = ctk.CTkFrame(self.content_container, fg_color="transparent")
        work_area.pack(fill="x")

        # Settings + Preview Frame
        controls_frame = ctk.CTkFrame(work_area, fg_color=CARD_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=15)
        controls_frame.pack(fill="x", padx=40, pady=10)
        
        # Grid layout for controls
        controls_frame.grid_columnconfigure(0, weight=2) # Generator
        controls_frame.grid_columnconfigure(1, weight=1) # Preview Card

        # --- Generator (Left) ---
        gen_section = ctk.CTkFrame(controls_frame, fg_color="transparent")
        gen_section.grid(row=0, column=0, sticky="nsew", padx=25, pady=20)

        if niche_id == "stories":
            reddit_btn = ctk.CTkButton(gen_section, text=self.t("reddit_btn"), command=self.parse_reddit_thread,
                                       fg_color=ORANGE_COLOR, hover_color="#c2410c", font=("Inter", 14, "bold"), 
                                       height=46, corner_radius=10)
            reddit_btn.pack(fill="x")
        else:
            gen_controls = ctk.CTkFrame(gen_section, fg_color="transparent")
            gen_controls.pack(fill="x")
            
            ctk.CTkLabel(gen_controls, text=self.t("count_label"), font=("Inter", 12, "bold"), text_color=SECONDARY_TEXT).pack(side="left", padx=(0, 10))
            count_cb = ctk.CTkComboBox(gen_controls, values=["5", "10", "20", "50"], width=80, height=32,
                                       fg_color=BG_COLOR, border_color=BORDER_COLOR, button_color=BORDER_COLOR)
            count_cb.set("20")
            count_cb.pack(side="left")
            self.niche_count_comboboxes[niche_id] = count_cb

            gen_btn = ctk.CTkButton(gen_controls, text=self.t("gen_btn"), command=self.generate_new_topics_thread,
                                    fg_color="#1e2f55", hover_color="#2a4078", 
                                    text_color=PRIMARY_COLOR, font=("Inter", 13, "bold"), border_color="#2a4078",
                                    border_width=1, height=36)
            gen_btn.pack(side="left", padx=(15, 0), fill="x", expand=True)
            self.niche_gen_buttons[niche_id] = gen_btn

        # --- Preview Card (Right) ---
        preview_card = ctk.CTkFrame(controls_frame, fg_color=BG_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=12)
        preview_card.grid(row=0, column=1, sticky="nsew", padx=(0, 25), pady=20)
        
        ctk.CTkLabel(preview_card, text=self.t("active_theme"), font=("Inter", 10, "bold"), text_color=PRIMARY_COLOR).pack(pady=(15, 5))
        ctk.CTkLabel(preview_card, textvariable=self.current_theme_text, font=("Inter", 14, "bold"), text_color=TEXT_COLOR, wraplength=180).pack(pady=(0, 15))

        # --- Text Editor (Full Width) ---
        ctk.CTkLabel(work_area, text=self.t("workflow_script"), font=("Inter", 12, "bold"), text_color=SECONDARY_TEXT).pack(anchor="w", padx=65, pady=(15, 5))
        txt = ctk.CTkTextbox(work_area, height=280, fg_color=CARD_COLOR, border_color=BORDER_COLOR, 
                             border_width=1, corner_radius=15, font=("Inter", 14), text_color=TEXT_COLOR, padx=15, pady=15)
        txt.pack(fill="x", padx=40, pady=(0, 20))
        self._add_context_menu(txt._textbox, is_textbox=True)
        self.niche_textboxes[niche_id] = txt
        
        if niche_id == "psychology" and not txt.get("1.0", tk.END).strip():
            txt.insert("0.0", "The Illusion of Choice in Conversation\nHow to Make Anyone Think of You\nSilent Power Dynamics")

    def _build_stats_and_console(self, parent):
        bottom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, padx=40, pady=(0, 40))
        bottom_frame.grid_columnconfigure(0, weight=3) # Console
        bottom_frame.grid_columnconfigure(1, weight=2) # Stats

        # Console (Left)
        console_card = ctk.CTkFrame(bottom_frame, fg_color=CARD_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=15)
        console_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        console_header = ctk.CTkFrame(console_card, fg_color="transparent")
        console_header.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(console_header, text=self.t("smart_console"), font=("Inter", 13, "bold"), text_color=TEXT_COLOR).pack(side="left")
        
        btn_frame = ctk.CTkFrame(console_header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.pause_btn = ctk.CTkButton(btn_frame, text=self.t("pause"), command=self.toggle_pause, width=70, height=28, fg_color=BORDER_COLOR, text_color=SECONDARY_TEXT, font=("Inter", 11, "bold"))
        self.pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(btn_frame, text=self.t("stop"), command=self.stop_pipeline, width=70, height=28, fg_color=ERROR_COLOR, hover_color="#b91c1c", font=("Inter", 11, "bold"))
        self.stop_btn.pack(side="left")

        self.console_textbox = ctk.CTkTextbox(console_card, height=300, fg_color=BG_COLOR, border_color=BORDER_COLOR, border_width=1, 
                                             corner_radius=12, font=("Consolas", 12), text_color=SUCCESS_COLOR, state="disabled", 
                                             padx=15, pady=15)
        self.console_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Console is now a standard textbox without scroll locking

        # Stats (Right)
        stats_card = ctk.CTkFrame(bottom_frame, fg_color=CARD_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=15)
        stats_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        ctk.CTkLabel(stats_card, text=self.t("engine_perf"), font=("Inter", 13, "bold"), text_color=TEXT_COLOR).pack(anchor="w", padx=20, pady=15)
        
        metrics_frame = ctk.CTkFrame(stats_card, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=20)
        
        total_gen, _ = get_performance_stats()
        self.vid_count_label = self._create_metric(metrics_frame, self.t("vids_gen"), str(total_gen), "+12%")
        self._create_metric(metrics_frame, self.t("avg_eng"), "8.4k", "NEW")

        # Mini Chart Placehoder (Canvas)
        self.chart_canvas = tk.Canvas(stats_card, bg=CARD_COLOR, highlightthickness=0, height=100)
        self.chart_canvas.pack(fill="x", padx=20, pady=10)
        self.after(500, self._draw_chart_placeholder)

    def _create_metric(self, parent, title, value, badge=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(side="left", expand=True)
        ctk.CTkLabel(frame, text=title, font=("Inter", 10, "bold"), text_color=SECONDARY_TEXT).pack(anchor="w")
        val_frame = ctk.CTkFrame(frame, fg_color="transparent")
        val_frame.pack(anchor="w")
        ctk.CTkLabel(val_frame, text=value, font=("Inter", 20, "bold"), text_color=PRIMARY_COLOR).pack(side="left")
        if badge:
            ctk.CTkLabel(val_frame, text=f" {badge}", font=("Inter", 10, "bold"), text_color=SUCCESS_COLOR).pack(side="left", padx=5)
        return frame # Or value label if needed for updates

    def _draw_chart_placeholder(self):
        # Simply draw a line/curve on canvas to mimic the SVG chart
        w = self.chart_canvas.winfo_width()
        h = self.chart_canvas.winfo_height()
        if w < 10: return # Not ready
        
        points = [(0, h-20), (50, h-30), (100, h-60), (150, h-40), (200, h-80), (250, h-70), (w, h-90)]
        # Drawing a smooth line
        self.chart_canvas.delete("all")
        self.chart_canvas.create_line(points, fill=PRIMARY_COLOR, width=3, smooth=True)
        # Gradient effect (simplified)
        poly_points = [(0, h)] + points + [(w, h)]
        self.chart_canvas.create_polygon(poly_points, fill=PRIMARY_COLOR, stipple="gray25", outline="")

    def _add_context_menu(self, widget, is_textbox=False):
        menu = tk.Menu(self, tearoff=0, bg=BG_COLOR, fg=TEXT_COLOR, 
                       activebackground=PRIMARY_COLOR, activeforeground="white", bd=0)
        
        def copy(): widget.event_generate("<<Copy>>")
        def paste(): widget.event_generate("<<Paste>>")
        def cut(): widget.event_generate("<<Cut>>")
        def select_all():
            if is_textbox:
                widget.tag_add("sel", "1.0", "end")
            else:
                widget.select_range(0, "end")
                widget.icursor("end")

        menu.add_command(label=self.t("cut"), command=cut)
        menu.add_command(label=self.t("copy"), command=copy)
        menu.add_command(label=self.t("paste"), command=paste)
        menu.add_separator()
        menu.add_command(label=self.t("select_all"), command=select_all)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)

    def _show_assets(self):
        self._update_nav_selection("assets")
        self._clear_content()

        header = ctk.CTkFrame(self.content_container, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(40, 20))
        ctk.CTkLabel(header, text=self.t("assets"), font=("Inter", 26, "bold"), text_color=TEXT_COLOR).pack(anchor="w")
        
        assets_frame = ctk.CTkFrame(self.content_container, fg_color=CARD_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=15)
        assets_frame.pack(fill="x", padx=40, pady=(0, 40))

        videos = get_output_videos()
        if not videos:
            ctk.CTkLabel(assets_frame, text=self.t("no_videos"), font=("Inter", 14), text_color=SECONDARY_TEXT).pack(pady=40)
        else:
            for vid in videos:
                self._create_asset_item(assets_frame, vid)

    def _create_asset_item(self, parent, vid):
        item = ctk.CTkFrame(parent, fg_color=BG_COLOR, height=70, corner_radius=10, border_color=BORDER_COLOR, border_width=1)
        item.pack(fill="x", padx=15, pady=5)
        item.pack_propagate(False)

        ctk.CTkLabel(item, text="🎬", font=("Inter", 20)).pack(side="left", padx=15)
        
        info = ctk.CTkFrame(item, fg_color="transparent")
        info.pack(side="left", fill="y", pady=10)
        ctk.CTkLabel(info, text=vid["name"], font=("Inter", 14, "bold"), text_color=TEXT_COLOR).pack(anchor="w")
        ctk.CTkLabel(info, text=f"{vid['date']} • {vid['size']}", font=("Inter", 11), text_color=SECONDARY_TEXT).pack(anchor="w")

        play_btn = ctk.CTkButton(item, text=self.t("open_file"), width=80, height=32, fg_color=BORDER_COLOR, 
                                 text_color=TEXT_COLOR, font=("Inter", 12, "bold"), 
                                 command=lambda p=vid['path']: os.startfile(p))
        play_btn.pack(side="right", padx=15)

    def _show_history(self):
        self._update_nav_selection("history")
        self._clear_content()

        header = ctk.CTkFrame(self.content_container, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(40, 20))
        ctk.CTkLabel(header, text=self.t("history"), font=("Inter", 26, "bold"), text_color=TEXT_COLOR).pack(anchor="w")
        
        # Simple placeholder for now
        placeholder = ctk.CTkFrame(self.content_container, fg_color=CARD_COLOR, border_color=BORDER_COLOR, border_width=1, corner_radius=15)
        placeholder.pack(fill="x", padx=40, pady=(0, 40), height=300)
        ctk.CTkLabel(placeholder, text=self.t("history_empty"), 
                     font=("Inter", 14), text_color=SECONDARY_TEXT).pack(expand=True)

    def log_message(self, message):
        """Thread-safe way to append text to the console textbox with color tagging"""
        self.after(0, self._append_to_console, str(message))

    def _append_to_console(self, text):
        if not hasattr(self, 'console_textbox') or not self.console_textbox.winfo_exists():
            return

        self.console_textbox.configure(state="normal")
        
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        
        # Determine color based on tag
        color = TEXT_COLOR
        if "SUCCESS" in text: color = SUCCESS_COLOR
        elif "WARN" in text or "WARNING" in text: color = WARN_COLOR
        elif "INFO" in text: color = PRIMARY_COLOR
        elif "PROCESS" in text: color = PROCESS_COLOR
        elif "ERROR" in text: color = ERROR_COLOR

        # We can't easily do per-line tags in ctk.CTkTextbox (it's one state)
        # But we can try to use standard tk Text tags if we reach the internal widget
        inner = self.console_textbox._textbox
        inner.tag_config("timestamp", foreground=SECONDARY_TEXT)
        inner.tag_config("msg", foreground=color)

        start_index = inner.index("end-1c")
        inner.insert(tk.END, timestamp, "timestamp")
        inner.insert(tk.END, text + "\n", "msg")
        
        inner.see(tk.END)
        self.console_textbox.see("end") # Double security for auto-scroll
        inner.update_idletasks()
        self.console_textbox.configure(state="disabled")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.pexels_key_var.set(config.get("pexels_key", ""))
                    self.groq_key_var.set(config.get("groq_key", ""))
            except Exception as e:
                self.log_message(f"ERROR: Error loading config: {e}")

    def save_config(self):
        config = {
            "pexels_key": self.pexels_key_var.get(),
            "groq_key": self.groq_key_var.get()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        self.log_message("[System] API keys saved successfully.")

    def start_pipeline_thread(self):
        pexels_key = self.pexels_key_var.get().strip()
        groq_key = self.groq_key_var.get().strip()
        
        niche = self.active_niche
        topics_text = self.niche_textboxes[niche].get("0.0", tk.END).strip()
 
        if not pexels_key or not groq_key:
            self.log_message("[Error] Both Pexels and Groq API keys are required!")
            return
 
        if not topics_text:
            self.log_message(f"[Error] Please provide at least one topic for {niche}.")
            return
 
        topics = [t.strip() for t in topics_text.split("\n") if t.strip()]
 
        # Reset events
        self.stop_event.clear()
        self.pause_event.set()
        self.pause_btn.configure(text="⏸ Пауза", state="normal")
        self.stop_btn.configure(state="normal")
        
        # Mmediately update status text for UI feedback
        self.current_theme_text.set(self.t("launching"))
        self.update_idletasks()

        # Disable all start buttons while running
        for btn in self.niche_start_buttons.values():
            btn.configure(state="disabled", text="⏳ Running...")
        
        # Run in background thread so GUI doesn't freeze
        thread = threading.Thread(target=self._run_pipeline_worker, args=(pexels_key, groq_key, topics, niche))
        thread.daemon = True
        thread.start()

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="▶ Продолжить")
            self.log_message("[System] Пауза...")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="⏸ Пауза")
            self.log_message("[System] Продолжение работы.")

    def stop_pipeline(self):
        self.stop_event.set()
        self.pause_event.set() # Unpause to allow stop check
        self.log_message("[System] Запрос на остановку отправлен...")
        self.stop_btn.configure(state="disabled")

    def generate_new_topics_thread(self):
        groq_key = self.groq_key_var.get().strip()
        if not groq_key:
            self.log_message("[Error] Groq API key is required for generation!")
            return
            
        niche = self.active_niche
        count_cb = self.niche_count_comboboxes.get(niche)
        gen_btn = self.niche_gen_buttons.get(niche)
        
        if not count_cb or not gen_btn:
            self.log_message(f"[Error] Controls not found for niche {niche}")
            return

        count = int(count_cb.get())
        gen_btn.configure(state="disabled", text="⏳ Генерирую...")
        
        # Immediately update status text for UI feedback
        self.current_theme_text.set(self.t("generating"))
        self.update_idletasks()
        
        thread = threading.Thread(target=self._generate_topics_worker, args=(groq_key, niche, count))
        thread.daemon = True
        thread.start()
 
    def _generate_topics_worker(self, groq_key, niche, count):
        try:
            self.log_message(f"[System] Запрос к Groq ({niche}) на генерацию {count} тем...")
            new_topics = generate_topics(groq_key, niche, count)
            
            if not new_topics:
                self.log_message("[Error] Не удалось сгенерировать темы (пустой ответ).")
                return
 
            # Фильтрация дубликатов
            used_topics_file = f"used_topics_{niche}.txt"
            used_topics = set()
            if os.path.exists(used_topics_file):
                with open(used_topics_file, "r", encoding="utf-8") as f:
                    used_topics = {line.strip() for line in f if line.strip()}
            
            unique_topics = [t for t in new_topics if t not in used_topics]
            
            duplicates_count = len(new_topics) - len(unique_topics)
            if duplicates_count > 0:
                self.log_message(f"[System] [{niche}] Отсеяно {duplicates_count} дубликатов из базы.")
 
            if unique_topics:
                # Вставляем в поле Topics конкретной ниши
                self.after(0, self._insert_unique_topics, niche, unique_topics)
                self.log_message(f"✅ [{niche}] Добавлено {len(unique_topics)} новых уникальных тем.")
            else:
                self.log_message(f"[Warning] [{niche}] Все сгенерированные темы уже есть в базе.")

        except Exception as e:
            self.log_message(f"[Error] Ошибка при генерации: {e}")
        finally:
            self.after(0, self._reset_gen_buttons)

    def _reset_gen_buttons(self):
        for btn in self.niche_gen_buttons.values():
            btn.configure(state="normal", text="✨ Сгенерировать темы")
 
    def parse_reddit_thread(self):
        groq_key = self.groq_key_var.get().strip()
        
        if not groq_key:
            self.log_message("[Error] Groq key is required for stories adaptation!")
            return
            
        thread = threading.Thread(target=self._parse_reddit_worker, args=(groq_key,))
        thread.daemon = True
        thread.start()

    def _parse_reddit_worker(self, groq_key):
        try:
            self.log_message("[System] Ищу свежую историю на Reddit...")
            title, content = get_reddit_story()
            
            if not title:
                self.log_message("[Error] Не удалось найти новые истории на Reddit.")
                return
                
            self.log_message(f"[System] История найдена: {title}. Адаптирую через Groq...")
            adapted_story = adapt_reddit_story(title, content, groq_key)
            
            if adapted_story:
                self.after(0, self._set_stories_text, adapted_story)
                self.log_message("✅ Reddit-история успешно адаптирована и добавлена.")
            else:
                self.log_message("[Error] Ошибка адаптации истории.")
        except Exception as e:
            self.log_message(f"[Error] Ошибка Reddit-парсера: {e}")

    def _set_stories_text(self, text):
        textbox = self.niche_textboxes["stories"]
        textbox.delete("0.0", tk.END)
        textbox.insert("0.0", text)

    def _insert_unique_topics(self, niche, topics):
        textbox = self.niche_textboxes[niche]
        current_text = textbox.get("0.0", tk.END).strip()
        if current_text:
            textbox.insert(tk.END, "\n" + "\n".join(topics))
        else:
            textbox.insert("0.0", "\n".join(topics))
        textbox.see(tk.END)
 
    def _run_pipeline_worker(self, pexels_key, groq_key, topics, niche):
        try:
            self.log_message(f"=== INITIALIZING PIPELINE [{niche}] ===")
            
            # Custom log callback to capture theme updates
            def extended_log(msg):
                self.log_message(msg)
                if "Rendering final output" in msg:
                    # Try to extract theme name from message or just use niche
                    self.current_theme_text.set(f"{self.t('rendering')} {niche}")
                elif "Generated script for" in msg:
                    theme = msg.split("'")[1] if "'" in msg else niche
                    self.current_theme_text.set(theme)

            run_pipeline(
                pexels_api_key=pexels_key,
                groq_api_key=groq_key,
                topics=topics,
                niche=niche,
                log_callback=extended_log,
                stop_event=self.stop_event,
                pause_event=self.pause_event
            )
            
            # Log success to DB
            for topic in topics:
                log_generation(niche, topic, success=1)
                
            self.log_message(f"=== [{niche}] PIPELINE COMPLETED SUCCESSFULLY ===")
            self.current_theme_text.set("All tasks finished.")
            
        except Exception as e:
            self.log_message(f"ERROR: {str(e)}")
            self.current_theme_text.set("Pipeline failed.")
        finally:
            self.after(0, self._reset_ui_after_run)

    def _reset_ui_after_run(self):
        self.pipeline_btn.configure(state="normal", text="▶ Start Pipeline", fg_color=PRIMARY_COLOR)
        self.pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")
        
        # Update stats label
        total, _ = get_performance_stats()
        # Find the metric label (it's inside vid_count_label frame)
        for child in self.vid_count_label.winfo_children():
            if isinstance(child, ctk.CTkFrame): # val_frame
                for gc in child.winfo_children():
                    if isinstance(gc, ctk.CTkLabel) and gc.cget("text") != " +12%":
                        gc.configure(text=str(total))

if __name__ == "__main__":
    app = App()
    app.mainloop()
