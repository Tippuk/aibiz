import os
import json
import threading
import customtkinter as ctk
import tkinter as tk
from auto_tiktok_pipeline import run_pipeline

CONFIG_FILE = "config.json"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Dark Psychology TikTok Automation")
        self.geometry("800x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Config variables
        self.pexels_key_var = ctk.StringVar()
        self.groq_key_var = ctk.StringVar()
        self.load_config()

        self._build_sidebar()
        self._build_main_area()

    def _add_context_menu(self, widget, is_textbox=False):
        # Создаем стильное темное меню
        menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white", 
                       activebackground="#1f538d", activeforeground="white", bd=0)
        
        def copy(): widget.event_generate("<<Copy>>")
        def paste(): widget.event_generate("<<Paste>>")
        def cut(): widget.event_generate("<<Cut>>")
        def select_all():
            if is_textbox:
                widget.tag_add("sel", "1.0", "end")
            else:
                widget.select_range(0, "end")
                widget.icursor("end")

        menu.add_command(label="Вырезать (Cut)", command=cut)
        menu.add_command(label="Копировать (Copy)", command=copy)
        menu.add_command(label="Вставить (Paste)", command=paste)
        menu.add_separator()
        menu.add_command(label="Выделить всё (Select All)", command=select_all)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(self.sidebar_frame, text="API Settings", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        # Pexels API
        ctk.CTkLabel(self.sidebar_frame, text="Pexels API Key:").grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.pexels_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.pexels_key_var, show="*", width=200)
        self.pexels_entry.grid(row=2, column=0, padx=20, pady=5)
        self._add_context_menu(self.pexels_entry._entry) # Бинд на внутреннее tk-поле

        # Groq API
        ctk.CTkLabel(self.sidebar_frame, text="Groq API Key:").grid(row=3, column=0, padx=20, pady=5, sticky="w")
        self.groq_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.groq_key_var, show="*", width=200)
        self.groq_entry.grid(row=4, column=0, padx=20, pady=5, sticky="n")
        self._add_context_menu(self.groq_entry._entry)

        # Save Config Button
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save Keys", command=self.save_config)
        self.save_btn.grid(row=5, column=0, padx=20, pady=20)

    def _build_main_area(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Topics Area (Top Right)
        self.topics_frame = ctk.CTkFrame(self)
        self.topics_frame.grid(row=0, column=1, padx=20, pady=(20, 10), sticky="nsew")
        self.topics_frame.grid_columnconfigure(0, weight=1)
        self.topics_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.topics_frame, text="Topics (one per line):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        self.topics_textbox = ctk.CTkTextbox(self.topics_frame)
        self.topics_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._add_context_menu(self.topics_textbox._textbox, is_textbox=True)
        
        # Insert default topics if empty
        default_topics = "Иллюзия выбора в общении\nКак заставить человека думать о тебе\nМрачный закон власти: молчание"
        self.topics_textbox.insert("0.0", default_topics)

        # Console Area (Bottom Right)
        self.console_frame = ctk.CTkFrame(self)
        self.console_frame.grid(row=1, column=1, padx=20, pady=(10, 20), sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.console_frame, text="Console Output:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        self.console_textbox = ctk.CTkTextbox(self.console_frame, state="disabled")
        self.console_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._add_context_menu(self.console_textbox._textbox, is_textbox=True)

        # Action Buttons frame
        self.action_frame = ctk.CTkFrame(self.console_frame, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.start_btn = ctk.CTkButton(self.action_frame, text="🚀 Запуск конвейера", command=self.start_pipeline_thread, height=40, font=ctk.CTkFont(weight="bold"))
        self.start_btn.grid(row=0, column=0, sticky="ew")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.pexels_key_var.set(config.get("pexels_key", ""))
                    self.groq_key_var.set(config.get("groq_key", ""))
            except Exception as e:
                self.log_message(f"Error loading config: {e}")

    def save_config(self):
        config = {
            "pexels_key": self.pexels_key_var.get(),
            "groq_key": self.groq_key_var.get()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        self.log_message("[System] API keys saved successfully.")

    def log_message(self, message):
        """Thread-safe way to append text to the console textbox"""
        self.after(0, self._append_to_console, str(message) + "\n")

    def _append_to_console(self, text):
        self.console_textbox.configure(state="normal")
        self.console_textbox.insert(tk.END, text)
        self.console_textbox.see(tk.END)
        self.console_textbox.configure(state="disabled")

    def start_pipeline_thread(self):
        pexels_key = self.pexels_key_var.get().strip()
        groq_key = self.groq_key_var.get().strip()
        topics_text = self.topics_textbox.get("0.0", tk.END).strip()

        if not pexels_key or not groq_key:
            self.log_message("[Error] Both Pexels and Groq API keys are required!")
            return

        if not topics_text:
            self.log_message("[Error] Please provide at least one topic.")
            return

        topics = [t.strip() for t in topics_text.split("\n") if t.strip()]

        # Disable button while running
        self.start_btn.configure(state="disabled", text="⏳ Running...")
        
        # Run in background thread so GUI doesn't freeze
        thread = threading.Thread(target=self._run_pipeline_worker, args=(pexels_key, groq_key, topics))
        thread.daemon = True
        thread.start()

    def _run_pipeline_worker(self, pexels_key, groq_key, topics):
        try:
            self.log_message("=== ПОДГОТОВКА К ЗАПУСКУ ===")
            # Call the main pipeline function
            run_pipeline(
                pexels_api_key=pexels_key,
                groq_api_key=groq_key,
                topics=topics,
                log_callback=self.log_message
            )
            self.log_message("\n=== КОНВЕЙЕР УСПЕШНО ЗАВЕРШИЛ РАБОТУ ===")
        except Exception as e:
            self.log_message(f"\n[Критическая ошибка]: {str(e)}")
        finally:
            # Re-enable the button (thread-safe)
            self.after(0, lambda: self.start_btn.configure(state="normal", text="🚀 Запуск конвейера"))

if __name__ == "__main__":
    app = App()
    app.mainloop()
