import asyncio
import os
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

def get_state_file(niche):
    return f"state_{niche}.json"

async def save_login_state(niche):
    """Открывает браузер для ручного логина и сохраняет состояние (куки) для конкретной ниши"""
    state_file = get_state_file(niche)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        print(f"\n=== АВТОРИЗАЦИЯ TIKTOK ДЛЯ НИШИ: {niche.upper()} ===")
        print("1. Залогиньтесь в аккаунт, соответствующий этой нише.")
        print("2. После входа подождите 10-15 секунд.")
        print("3. Закройте окно или дождитесь автоматического сохранения.")
        
        await page.goto("https://www.tiktok.com/login")
        
        try:
            await page.wait_for_timeout(120000)
        except:
            pass
            
        await context.storage_state(path=state_file)
        print(f"✅ Состояние входа для '{niche}' сохранено в {state_file}")
        await browser.close()

async def handle_popups(page):
    """Закрывает возможные всплывающие окна (Cookies, Login prompts) во всех фреймах"""
    popups = [
        "//button[contains(text(), 'Accept all')]",
        "//button[contains(text(), 'Принять все')]",
        "//div[contains(@class, 'mask')]//div[contains(@class, 'close')]",
        "[data-e2e='modal-close-inner-button']",
        "text=Continue as guest",
        "text=Got it",
        "text=Понятно",
        "text=Ок",
        "text=OK",
        "//button[contains(@class, 'close')]",
        "//div[contains(@class, 'close')]"
    ]
    contexts = [page] + page.frames
    for ctx in contexts:
        for selector in popups:
            try:
                elements = await ctx.locator(selector).all()
                for el in elements:
                    if await el.is_visible(timeout=500):
                        await el.click(force=True)
                        print(f"✅ Всплывающее окно закрыто в {getattr(ctx, 'url', 'главном окне')}: {selector}")
            except:
                pass

async def handle_post_confirmation(page):
    """Специальная обработка модальных окон ПОСЛЕ нажатия кнопки Опубликовать"""
    print("[TikTok] Проверка финальных подтверждений (модалок)...")
    
    # Приоритеты: 1. Опубликовать, 2. Разрешить, 3. Отмена/Выйти
    confirmation_selectors = [
        # Группа 1: Прямое подтверждение публикации
        "//button[contains(text(), 'Post now')]",
        "//button[contains(text(), 'Опубликовать сейчас')]",
        "//button[contains(text(), 'Confirm')]",
        "//button[contains(text(), 'Подтвердить')]",
        "//div[role='dialog']//button:has-text('Post')",
        "//div[role='dialog']//button:has-text('Опубликовать')",
        
        # Группа 2: Разрешения
        "//button[contains(text(), 'Allow')]",
        "//button[contains(text(), 'Разрешить')]",
        
        # Группа 3: Закрытие/Выход (если нет первых двух)
        "//button[contains(text(), 'Cancel')]",
        "//button[contains(text(), 'Отмена')]",
        "//button[contains(text(), 'Exit')]",
        "//button[contains(text(), 'Выйти')]",
        "//button[contains(text(), 'Not now')]",
        "//button[contains(text(), 'Не сейчас')]"
    ]
    
    for _ in range(3): # 3 попытки с паузой
        all_ctx = [page] + page.frames
        found_and_clicked = False
        
        for ctx in all_ctx:
            for selector in confirmation_selectors:
                try:
                    # Ищем первый попавшийся элемент из списка приоритетов
                    el = ctx.locator(selector).first
                    if await el.is_visible(timeout=1000):
                        text = await el.inner_text()
                        await el.click(force=True)
                        print(f"✅ Финальное подтверждение обработано: [{text}]")
                        found_and_clicked = True
                        break
                except: continue
            if found_and_clicked: break
        
        if not found_and_clicked:
            break # Окон больше нет
        await asyncio.sleep(2)

async def upload_video(video_path, text_caption, hashtags, niche):
    """Автоматическая загрузка видео в TikTok для конкретной ниши"""
    state_file = get_state_file(niche)
    
    if not os.path.exists(state_file):
        print(f"⚠️ Сессия для ниши '{niche}' не найдена ({state_file}). Пропуск загрузки.")
        return False

    if not os.path.exists(video_path):
        print(f"❌ Ошибка: видеофайл {video_path} не найден.")
        return False

    async with async_playwright() as p:
        print(f"[TikTok] ({niche}) Запуск браузера...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        try:
            print(f"[TikTok] ({niche}) Переход на страницу загрузки...")
            try:
                await page.goto("https://www.tiktok.com/creator-center/upload", wait_until="domcontentloaded", timeout=90000)
            except Exception as goto_err:
                print(f"❌ Ошибка перехода на страницу: {goto_err}")
                await page.screenshot(path=f"timeout_goto_{niche}.png")
                await browser.close()
                return False

            # Проверка авторизации: если видим кнопки "Log in", значит сессия протухла
            login_selectors = ["[data-e2e='nav-login-button']", "button:has-text('Log in')", "button:has-text('Войти')"]
            for sel in login_selectors:
                if await page.locator(sel).is_visible(timeout=5000):
                    print(f"❌ ОШИБКА: Требуется авторизация в TikTok для ниши '{niche}'. Сессия недействительна.")
                    await page.screenshot(path=f"auth_required_{niche}.png")
                    await browser.close()
                    return False

            # Обработка всплывающих окон перед началом
            await handle_popups(page)
            
            # Поиск инпута и кнопки загрузки (Глобальный поиск во всех фреймах)
            print(f"[TikTok] ({niche}) Глобальный поиск инпутов...")
            
            # Функция для принудительного раскрытия инпутов (включая Shadow DOM)
            async def force_unhide_inputs(context):
                js_code = """
                () => {
                    function findDeep(root, selector) {
                        let found = Array.from(root.querySelectorAll(selector));
                        root.querySelectorAll('*').forEach(el => {
                            if (el.shadowRoot) {
                                found = found.concat(findDeep(el.shadowRoot, selector));
                            }
                        });
                        return found;
                    }
                    const sels = ['input.jsx-2995057667', 'input[type="file"]', 'input[accept*="video"]'];
                    let total = 0;
                    sels.forEach(s => {
                        const targets = findDeep(document, s);
                        targets.forEach(el => {
                            el.style.display = 'block'; el.style.opacity = '1';
                            el.style.visibility = 'visible'; el.style.position = 'relative';
                            el.style.height = '100px'; el.style.width = '300px'; el.style.zIndex = '9999';
                            total++;
                        });
                    });
                    return total;
                }
                """
                try: return await context.evaluate(js_code)
                except: return 0

            # Ждем прогрузки фреймов
            await asyncio.sleep(7)
            all_contexts = [page] + page.frames
            print(f"[TikTok] ({niche}) Анализ {len(all_contexts)} контекстов...")

            # --- МЕТОД 1: File Chooser через поиск кнопки «Загрузить» во всех фреймах ---
            print(f"[TikTok] ({niche}) Шаг 1: Поиск кнопки «Загрузить»...")
            target_names = ["Загрузить", "Select video", "Выбрать видео", "Upload video", "Выбрать файл"]
            
            for ctx in all_contexts:
                for name in target_names:
                    try:
                        # Ищем все элементы с таким текстом (даже если они не button)
                        candidates = await ctx.get_by_text(name).all()
                        for cand in candidates:
                            print(f"🎯 Найден элемент '{name}' в {getattr(ctx, 'url', 'главном окне')}. Пробую File Chooser...")
                            try:
                                async with page.expect_file_chooser(timeout=20000) as fc_info:
                                    # Пробуем кликнуть по элементу или его родителю
                                    try: await cand.click(force=True, timeout=5000)
                                    except: 
                                        handle = await cand.element_handle()
                                        if handle: await ctx.evaluate("el => el.click()", handle)
                                
                                file_chooser = await fc_info.value
                                await file_chooser.set_files(video_path)
                                print(f"✅ Видео успешно выбрано через File Chooser (элемент '{name}')")
                                upload_input = "SUCCESS"
                                target_context = ctx
                                break
                            except Exception as fc_err:
                                print(f"ℹ️ Клики по '{name}' не открыли диалог: {fc_err}")
                        if upload_input: break
                    except: pass
                if upload_input: break

            # --- МЕТОД 2: Прямая передача во все найденные инпуты ---
            if not upload_input:
                print(f"[TikTok] ({niche}) Шаг 2: Прямая передача файла в инпуты...")
                for ctx in all_contexts:
                    # Раскрываем инпуты в этом контексте
                    revealed = await force_unhide_inputs(ctx)
                    if revealed > 0: print(f"🔍 В контексте {getattr(ctx, 'url', 'главном окне')} разоблачено {revealed} инпутов.")
                    
                    # Ищем все потенциальные инпуты
                    input_candidates = await ctx.locator('input[type="file"], input.jsx-2995057667').all()
                    for inp in input_candidates:
                        try:
                            # Пробуем передать файл
                            await inp.set_input_files(video_path, timeout=5000)
                            print(f"✅ Видео успешно выбрано через прямую передачу в инпут!")
                            upload_input = "SUCCESS"
                            target_context = ctx
                            break
                        except Exception as inp_err:
                            print(f"ℹ️ Не удалось передать файл в конкретный инпут: {str(inp_err)[:100]}...")
                    if upload_input: break

            # --- ФИНАЛЬНЫЙ ШАНС: JS-диагностика и аудит ---
            if not upload_input:
                print(f"❌ ОШИБКА: Все методы выбора видео исчерпаны.")
                for i, ctx in enumerate(all_contexts):
                    try:
                        inps = await ctx.evaluate("() => Array.from(document.querySelectorAll('input')).map(i => ({type: i.type, id: i.id, class: i.className, visible: i.offsetWidth > 0}))")
                        print(f"--- Дебаг фрейма #{i} ---")
                        for inp_info in inps: 
                            if inp_info['type'] == 'file' or 'jsx' in inp_info['class']:
                                print(f"  Найден кандидат: {inp_info}")
                    except: pass
                
                content = await page.content()
                dump_path = f"debug_page_{niche}.html"
                with open(dump_path, "w", encoding="utf-8") as f: f.write(content)
                await page.screenshot(path=f"debug_upload_failed_{niche}.png")
                await browser.close()
                return False

            # Ждем появления полей ввода после загрузки
            print(f"[TikTok] ({niche}) Видео успешно выбрано, жду появления полей описания...")
            try:
                # Ожидаем появление любого редактора текста
                caption_selectors = [
                    'div[contenteditable="true"]', 
                    '.notranslate.public-DraftEditor-content',
                    '[data-e2e="post-edit-caption"]'
                ]
                cap_found = False
                for i in range(20): # Ждем до 60 секунд (20 * 3сек)
                    for c_sel in caption_selectors:
                        for ctx in [target_context, page] + page.frames:
                            try:
                                el = await ctx.wait_for_selector(c_sel, timeout=3000)
                                if el: 
                                    cap_found = True
                                    target_context = ctx
                                    print(f"🎉 Победа! Видео загружено в TikTok Studio, перехожу к описанию.")
                                    break
                            except: pass
                        if cap_found: break
                    if cap_found: break
                    print(f"⏳ Жду загрузки видео на сервер... ({i+1}/20)")
                    await asyncio.sleep(3)
                
                if not cap_found:
                    print(f"⚠️ Видео выбрано, но поля ввода не появились вовремя.")
            except Exception as e:
                print(f"❌ Ошибка в ожидании после загрузки: {e}")

            # Ввод описания
            print(f"[TikTok] ({niche}) Ввод описания и хэштегов...")
            try:
                caption_selectors = [
                    'div[contenteditable="true"]', 
                    '.notranslate.public-DraftEditor-content',
                    '[data-e2e="post-edit-caption"]'
                ]
                cap_el = None
                for c_sel in caption_selectors:
                    try:
                        el = await target_context.wait_for_selector(c_sel, timeout=5000)
                        if el: cap_el = el; break
                    except: pass

                if cap_el:
                    # Фокусируемся и очищаем поле
                    await cap_el.focus()
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Control+A")
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Backspace")
                    await page.wait_for_timeout(500)
                    
                    # Новый текст по запросу пользователя
                    user_fixed_caption = "Сними розовые очки. Суровая реальность и темные факты — в Telegram. Ссылка в профиле.#психология #манипуляции #даркпсихология #психологиячеловека #скрытыймотив #социальнаяинженерия #чтениелюдей #языктела #психологическиефакты #законывласти #даркпсихологи #факты"
                    print(f"[TikTok] ({niche}) Установка нового описания...")
                    
                    # insert_text более надежен для Draft.js редакторов
                    await page.keyboard.insert_text(user_fixed_caption)
                    print(f"✅ Описание введено.")
                    
                    # Клик по нейтральной области, чтобы закрыть выпадающие списки хэштегов и убрать фокус
                    await page.mouse.click(10, 10)
                    await asyncio.sleep(1)
                else:
                    print(f"⚠️ Поле описания не найдено после загрузки.")
            except Exception as ce:
                print(f"❌ Ошибка при вводе описания: {ce}")
            
            await asyncio.sleep(random.uniform(1, 2))

            # Выбор хэштегов из Истории
            print(f"[TikTok] ({niche}) Выбор хэштегов из истории...")
            try:
                for ctx in [target_context, page] + page.frames:
                    # Ищем заголовок "История"
                    history_label = ctx.get_by_text("История").first
                    if not await history_label.is_visible(timeout=2000):
                        history_label = ctx.get_by_text("History").first
                    
                    if await history_label.is_visible(timeout=1000):
                        # Находим все теги в контейнере рядом с "История"
                        # Обычно это соседние элементы или элементы внутри того же родителя
                        tags = await ctx.locator('//span[contains(text(), "#")]').all()
                        clicked_count = 0
                        for tag in tags:
                            try:
                                if await tag.is_visible(timeout=500):
                                    await tag.click(force=True)
                                    clicked_count += 1
                                    await asyncio.sleep(0.4) # Небольшая пауза между кликами
                            except: continue
                        if clicked_count > 0:
                            print(f"✅ Выбрано хэштегов из истории: {clicked_count}")
                            break
            except Exception as h_err:
                print(f"ℹ️ Не удалось выбрать хэштеги из истории: {h_err}")

            await asyncio.sleep(random.uniform(2, 3))
            
            # Включение метки "AI-generated content"
            print(f"[TikTok] ({niche}) Проверка переключателя AI...")
            try:
                # Поиск во всех фреймах
                ai_switch = None
                for ctx in [target_context, page] + page.frames:
                    try:
                        ai_switch = await ctx.locator('button[aria-checked="false"]').filter(has_text="AI-generated content").first
                        if await ai_switch.is_visible(timeout=2000):
                            await ai_switch.click()
                            print("✅ Метка AI-generated content включена.")
                            break
                    except: pass
            except Exception as ai_err:
                print(f"ℹ️ Метка AI не найдена или уже включена.")
            
            await asyncio.sleep(random.uniform(3, 5))
            
            # Кнопка Post (с долгим ожиданием готовности видео)
            print(f"[TikTok] ({niche}) Ожидание активации кнопки Опубликовать (Post)...")
            try:
                post_btn = None
                target_btn_ctx = page
                selectors = [
                    'button:has-text("Post")', 
                    'button:has-text("Опубликовать")',
                    '//button[contains(@class, "btn-post")]',
                    '//div[contains(text(), "Post")]/parent::button'
                ]
                
                # Цикл ожидания активации кнопки (до 20 минут)
                print(f"[TikTok] ({niche}) Начало мониторинга загрузки... (Лимит: 20 минут)")
                for attempt in range(120): # 120 * 10 секунд = 1200 сек (20 мин)
                    progress_text = None
                    for ctx in [target_context, page] + page.frames:
                        try:
                            # Ищем текст с процентами или статусом
                            # Примеры: "Uploading 85%", "Uploaded", "Загрузка 85%", "Загружено", "100%"
                            status_candidates = [
                                ctx.locator('//*[contains(text(), "%")]').last,
                                ctx.locator('//*[contains(text(), "Uploaded")]').first,
                                ctx.locator('//*[contains(text(), "Загружено")]').first,
                                ctx.locator('//*[contains(text(), "100%")]').first
                            ]
                            for cand in status_candidates:
                                if await cand.is_visible(timeout=500):
                                    text = await cand.inner_text()
                                    if "%" in text or "Uploaded" in text or "Загружено" in text:
                                        progress_text = text.strip()
                                        break
                            if progress_text: break
                        except: continue

                    if progress_text:
                        print(f"⏳ Статус загрузки: {progress_text} (Попытка {attempt+1}/120)")
                    
                    for sel in selectors:
                        for ctx in [target_context, page] + page.frames:
                            try:
                                btn = await ctx.wait_for_selector(sel, timeout=2000)
                                if btn:
                                    # Проверяем, активна ли кнопка (не заблокирована ли загрузкой)
                                    is_disabled = await btn.get_attribute("disabled")
                                    if is_disabled is None: # Кнопка активна!
                                        post_btn = btn
                                        target_btn_ctx = ctx
                                        break
                                    else:
                                        if attempt % 6 == 0 and not progress_text: # Пишем раз в минуту если нет прогресса
                                            print(f"⏳ Видео загружается... Кнопка Post пока заблокирована. ({attempt+1}/120)")
                            except: continue
                        if post_btn: break
                    if post_btn: break
                    await asyncio.sleep(10)
                
                if post_btn:
                    print(f"[TikTok] ({niche}) Нажатие кнопки Опубликовать...")
                    await post_btn.click(force=True)
                    
                    # НОВОЕ: Обработка финальных модальных окон (подтверждение публикации)
                    await asyncio.sleep(3)
                    await handle_post_confirmation(page)
                    
                    print(f"✨ Видео для '{niche}' успешно опубликовано!")
                    await asyncio.sleep(17) # Общий итог ожидания ~20 сек
                else:
                    print(f"❌ Кнопка Post не стала активной за 20 минут. Выход.")
                    await page.screenshot(path=f"debug_post_timeout_{niche}.png")
            except Exception as post_err:
                print(f"❌ Ошибка в шаге публикации: {post_err}")
            
            await browser.close()
            return True
            
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в tiktok_uploader ({niche}): {e}")
            await browser.close()
            return False

async def get_account_info(niche):
    """Парсит информацию о профиле (подписчики, лайки) в фоновом режиме"""
    state_file = get_state_file(niche)
    if not os.path.exists(state_file):
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        try:
            try:
                await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                print(f"⚠️ Warning: TikTok home page timeout or error: {e}")

            # Проверка, залогинены ли мы
            if "login" in page.url:
                await browser.close()
                return {"error": "auth_required"}

            # Переход в профиль
            try:
                await page.goto("https://www.tiktok.com/@me", wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                print(f"⚠️ Warning: TikTok profile page timeout or error: {e}")
                
            await asyncio.sleep(3) # Даем время на отрисовку цифр (важно для React-приложений)
            
            # Парсим статы (селекторы могут меняться, используем data-e2e)
            try:
                followers = await page.locator('[data-e2e="followers-count"]').text_content()
                likes = await page.locator('[data-e2e="likes-count"]').text_content()
                nickname = await page.locator('[data-e2e="user-title"]').text_content()
                
                await browser.close()
                return {
                    "followers": followers or "0",
                    "likes": likes or "0",
                    "nickname": nickname or niche
                }
            except Exception as parse_err:
                print(f"⚠️ Ошибка парсинга статов ({niche}): {parse_err}")
                await browser.close()
                return {"error": "parse_error"}
                
        except Exception as e:
            print(f"❌ Ошибка get_account_info ({niche}): {e}")
            await browser.close()
            return None

async def open_manual_session(niche, url="https://www.tiktok.com/"):
    """Открывает браузер в видимом режиме с загруженной сессией"""
    state_file = get_state_file(niche)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        # Если файла нет, открываем пустую страницу для логина
        context_args = {"storage_state": state_file} if os.path.exists(state_file) else {}
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        await page.goto(url)
        
        # Ждем, пока пользователь сам закроет браузер
        while True:
            try:
                if browser.is_connected():
                    await asyncio.sleep(1)
                else:
                    break
            except:
                break

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        niche_arg = sys.argv[2] if len(sys.argv) > 2 else "psychology"
        
        if cmd == "login":
            asyncio.run(save_login_state(niche_arg))
        elif cmd == "info":
            print(asyncio.run(get_account_info(niche_arg)))
        elif cmd == "manual":
            asyncio.run(open_manual_session(niche_arg))
    else:
        print("Usage: python tiktok_uploader.py [login|info|manual] [niche]")
