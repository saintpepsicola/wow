import tkinter as tk
import cv2
import numpy as np
from mss import mss
import pyautogui
import time
import os
import json
import shutil
from glob import glob
from AppKit import NSWorkspace
import threading
from queue import Queue
import concurrent.futures
from tkmacosx import Button
import keyboard
import keyboard_utils

# Global variables
overlay_position = None
selected_class = None
keybinds = {}
settings = {}
ability_templates = {}
running = True
is_paused = False

# Thread-safe queues
action_queue = Queue()
status_queue = Queue()

# Thread pool
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def load_keybinds():
    global keybinds
    keybinds_file = "keybinds.json"
    try:
        if os.path.exists(keybinds_file) and os.path.getsize(keybinds_file) > 0:
            with open(keybinds_file, "r") as f:
                keybinds = json.load(f)
        else:
            keybinds = {}
            print("📝 No keybinds.json found. Creating new...")
            save_keybinds()
    except json.JSONDecodeError:
        print("📝 Keybinds corrupted. Resetting...")
        keybinds = {}
        save_keybinds()


def save_keybinds():
    with open("keybinds.json", "w") as f:
        json.dump(keybinds, f, indent=2)


def load_settings():
    global settings
    settings_file = "settings.json"
    try:
        if os.path.exists(settings_file) and os.path.getsize(settings_file) > 0:
            with open(settings_file, "r") as f:
                settings.update(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        settings = {}
        save_settings()


def save_settings():
    with open("settings.json", "w") as f:
        json.dump(settings, f, indent=2)


def setup_keybinds(class_name, spell_files):
    global keybinds
    if class_name not in keybinds:
        keybinds[class_name] = {}

    existing_keybinds = keybinds[class_name]
    spell_names = [os.path.splitext(os.path.basename(f))[0] for f in spell_files]
    if all(spell in existing_keybinds for spell in spell_names):
        print(f"🔧 Keybinds already set for {class_name}")
        return

    root = tk.Tk()
    root.title(f"Setup Keybinds - {class_name.replace('-', ' ').title()}")
    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)
    entries = {}

    def save_and_close():
        for spell, entry in entries.items():
            key = entry.get().strip()
            if key:
                keybinds[class_name][spell] = key
        save_keybinds()
        root.destroy()

    for spell_path in spell_files:
        spell_name = os.path.splitext(os.path.basename(spell_path))[0]
        spell_frame = tk.Frame(frame)
        spell_frame.pack(fill=tk.X, pady=2)
        tk.Label(spell_frame, text=spell_name + ":").pack(side=tk.LEFT)
        entry = tk.Entry(spell_frame, width=5)
        entry.pack(side=tk.LEFT, padx=5)
        entries[spell_name] = entry
        if spell_name in keybinds[class_name]:
            entry.insert(0, keybinds[class_name][spell_name])

    tk.Button(root, text="Save Keybinds", command=save_and_close).pack(pady=10)
    root.mainloop()


def process_screen(screen):
    best_match = (None, None, 0)
    try:
        # Convert to grayscale only once
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        # Use a regular threshold for accurate matching
        threshold = 0.75

        for name, (template_gray, key) in ability_templates.items():
            if template_gray is None:
                continue
            try:
                # Use the pre-converted grayscale template
                result = cv2.matchTemplate(
                    screen_gray, template_gray, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > threshold and max_val > best_match[2]:
                    best_match = (name, key, max_val)
            except Exception as e:
                print(f"❌ Error matching template {name}: {str(e)}")
                continue
    except Exception as e:
        print(f"❌ Error in process_screen: {str(e)}")
        pass

    if best_match[0]:
        print(
            f"🔍 Matched {best_match[0]}: Score = {best_match[2]:.3f}, Key = {best_match[1]}"
        )
        return best_match[0], best_match[1]
    return None, None


def screen_capture_thread(overlay_root):
    global running, is_paused
    sct = mss()
    last_capture_time = 0
    min_capture_interval = 0.1
    last_key_press = 0
    min_key_interval = 0.5
    last_key = None

    while running:
        try:
            current_time = time.time()
            if current_time - last_capture_time < min_capture_interval:
                continue

            if is_paused:
                time.sleep(0.1)
                continue

            x, y = overlay_root.winfo_x(), overlay_root.winfo_y()
            region = {"top": y, "left": x, "width": 32, "height": 32}
            screen = np.array(sct.grab(region))

            name, key = process_screen(screen)

            if key:
                if (
                    key != last_key
                    or (current_time - last_key_press) >= min_key_interval
                ):
                    action_queue.put(("press", key))
                    last_key_press = current_time
                    last_key = key
            else:
                save_unrecognized_ability(screen)

            last_capture_time = current_time

        except Exception as e:
            print(f"❌ Error in screen capture: {str(e)}")
            continue


def press_keys(keys):
    """Press a combination of keys"""
    try:
        # Convert string keys to actual keys
        actual_keys = [get_key_from_string(k) for k in keys]

        # Press all modifier keys first
        for key in actual_keys[:-1]:  # All except the last key
            keyboard.press(key)

        # Press and release the last key (number)
        keyboard.press(actual_keys[-1])
        keyboard.release(actual_keys[-1])

        # Release all modifier keys in reverse order
        for key in reversed(actual_keys[:-1]):
            keyboard.release(key)

    except Exception as e:
        # Emergency key release
        for key in reversed(actual_keys):
            try:
                keyboard.release(key)
            except:
                pass


def create_overlay():
    global overlay_position, ability_templates, running, is_paused

    print("🖥️ Creating overlay")
    overlay_root = tk.Tk()
    overlay_root.overrideredirect(True)
    overlay_root.attributes("-alpha", 1.0)
    overlay_root.attributes("-topmost", True)
    overlay_root.attributes("-transparent", True)
    print("🖼️ Overlay window initialized")

    if "overlay_position" in settings:
        pos = settings["overlay_position"]
        overlay_root.geometry(f"32x32+{pos[0]}+{pos[1]}")
    else:
        overlay_root.geometry("32x32+100+100")

    if os.name == "posix":
        overlay_root.attributes("-type", "utility")

    canvas = tk.Canvas(
        overlay_root,
        width=32,
        height=32,
        highlightthickness=1,
        highlightbackground="green",
        bg="systemTransparent",
    )
    canvas.pack(fill="none", expand=False)
    print("🎨 Canvas packed")

    last_toggle_time = 0

    def toggle_pause():
        global is_paused
        nonlocal last_toggle_time
        current_time = time.time()
        if current_time - last_toggle_time > 0.5:  # Debounce
            is_paused = not is_paused
            button_root.after(0, lambda: update_toggle_button_state())
            last_toggle_time = current_time
            print(f"⏯️ Toggled: {'Paused' if is_paused else 'Running'}")

    # Use spacebar as a reliable hotkey
    def check_spacebar():
        try:
            if keyboard_utils.is_key_pressed("space"):
                current_time = time.time()
                if current_time - last_toggle_time > 0.5:  # Double-check debounce
                    toggle_pause()
                    # Don't check again too soon
                    overlay_root.after(500, check_spacebar)
                    return
        except Exception as e:
            pass  # Silent failure

        # Check again after a short delay
        overlay_root.after(100, check_spacebar)

    # Start checking for spacebar
    overlay_root.after(500, check_spacebar)
    print("⌨️ Pause hotkey activated (press Spacebar)")

    button_root = tk.Tk()
    button_root.overrideredirect(True)
    button_root.attributes("-alpha", 0.95)
    button_root.attributes("-topmost", True)
    button_root.configure(bg="#1a1a1a")

    def update_toggle_button_state():
        # This function is called by the main thread via after()
        toggle_btn.configure(
            text="▶" if is_paused else "⏸",
            bg="#ff4d4d" if is_paused else "#4dff4d",
            activebackground="#cc0000" if is_paused else "#00cc00",
        )

    toggle_btn = Button(
        button_root,
        text="⏸",
        command=toggle_pause,
        font=("Arial", 14, "bold"),
        bg="#4dff4d",
        fg="#ffffff",
        activebackground="#00cc00",
        activeforeground="#ffffff",
        borderless=1,
        focusthickness=0,
        width=34,
        height=28,
        cursor="hand2",
        relief="flat",
        highlightbackground="#333333",
        highlightcolor="#333333",
    )
    toggle_btn.pack(pady=1, padx=1)

    def update_button_position():
        x = overlay_root.winfo_x()
        y = overlay_root.winfo_y()
        button_root.geometry(f"+{x}+{y + 34}")
        button_root.lift()
        button_root.attributes("-topmost", True)
        button_root.after(10, update_button_position)

    def move_window(event):
        x = event.x_root
        y = event.y_root
        overlay_root.geometry(f"+{x}+{y}")
        settings["overlay_position"] = [x, y]
        save_settings()
        overlay_root.lift()
        overlay_root.attributes("-topmost", True)

    def keep_on_top():
        overlay_root.lift()
        overlay_root.attributes("-topmost", True)
        button_root.lift()
        button_root.attributes("-topmost", True)
        button_root.after(100, keep_on_top)

    def update_border_color():
        color = "red" if is_paused else "green"
        canvas.configure(highlightbackground=color)
        overlay_root.after(100, update_border_color)

    def process_queues():
        """Process the action queue to trigger key presses"""
        while not action_queue.empty():
            try:
                action, value = action_queue.get_nowait()

                if action == "press" and not is_paused:
                    if value.isdigit():  # Only process number keys
                        try:
                            # Use our custom keyboard module
                            keyboard_utils.send_key_combo("", value)
                        except Exception as e:
                            print(f"❌ Error pressing key '{value}': {str(e)}")
            except Exception as e:
                print(f"❌ Error processing queue: {str(e)}")
                continue

        # Check again after a short delay
        overlay_root.after(10, process_queues)

    capture_thread = threading.Thread(
        target=screen_capture_thread, args=(overlay_root,)
    )
    capture_thread.daemon = True
    capture_thread.start()
    print("📷 Screen capture thread started")

    overlay_root.bind("<B1-Motion>", move_window)
    keep_on_top()
    update_button_position()
    update_border_color()
    process_queues()
    print("🔄 Overlay loops started")

    def on_closing():
        global running
        running = False
        # Clean up any keyboard resources
        try:
            keyboard.unhook_all()
        except:
            pass
        thread_pool.shutdown(wait=False)
        overlay_root.destroy()
        button_root.destroy()
        print("🚀 Overlay closed")

    overlay_root.protocol("WM_DELETE_WINDOW", on_closing)
    print("🚀 Entering mainloop")
    overlay_root.mainloop()


def select_class():
    global selected_class, settings
    root = tk.Tk()
    root.title("Select Class")

    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(main_frame, text="Select your class:", font=("Arial", 10, "bold")).pack(
        pady=(0, 10)
    )
    buttons_frame = tk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(0, 10))

    classes = [
        d for d in os.listdir("spells") if os.path.isdir(os.path.join("spells", d))
    ]

    def on_class_select(class_name):
        global selected_class
        selected_class = class_name
        settings["save_unrecognized"] = save_unrecognized_var.get()
        save_settings()
        print(
            f"⚙️ Save unrecognized abilities: {'Enabled' if settings['save_unrecognized'] else 'Disabled'}"
        )
        root.destroy()

    for class_name in sorted(classes):
        display_name = class_name.replace("-", " ").title()
        btn = tk.Button(
            buttons_frame,
            text=display_name,
            command=lambda c=class_name: on_class_select(c),
        )
        btn.pack(pady=2, padx=10, fill=tk.X)

    tk.Frame(main_frame, height=1, bg="gray").pack(fill=tk.X, pady=10)
    settings_frame = tk.Frame(main_frame)
    settings_frame.pack(fill=tk.X)

    save_unrecognized_var = tk.BooleanVar(
        value=settings.get("save_unrecognized", False)
    )
    save_checkbox = tk.Checkbutton(
        settings_frame,
        text="Save unrecognized abilities to pending folder (for training)",
        variable=save_unrecognized_var,
        font=("Arial", 9, "bold"),
    )
    save_checkbox.pack(pady=5)

    root.mainloop()


def load_ability_templates():
    global ability_templates
    if selected_class is None:
        print("❌ No class selected!")
        return {}

    templates = {}
    class_path = os.path.join("spells", selected_class)
    spell_files = glob(os.path.join(class_path, "*.*"))

    if not spell_files:
        print(f"⚠️ No spell images for {selected_class}!")
        return {}

    setup_keybinds(selected_class, spell_files)

    print(f"🔄 Pre-processing {len(spell_files)} spell templates...")
    start_time = time.time()
    for spell_path in spell_files:
        spell_name = os.path.splitext(os.path.basename(spell_path))[0]
        if selected_class in keybinds and spell_name in keybinds[selected_class]:
            key = keybinds[selected_class][spell_name]
            template = cv2.imread(spell_path)
            if template is not None:
                # Convert to grayscale immediately
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                templates[spell_name] = (template_gray, key)
                print(f"🖼️ Loaded {spell_name} -> {key}")
            else:
                print(f"⚠️ Failed to load {spell_path}")

    elapsed = time.time() - start_time
    print(f"✅ Loaded {len(templates)} templates for {selected_class}")
    print(f"⚡ Optimization complete! Templates pre-processed in {elapsed:.3f}s")
    return templates


def save_unrecognized_ability(screen):
    if selected_class is None or not settings.get("save_unrecognized", False):
        return

    try:
        pending_dir = os.path.join("pending", selected_class)
        os.makedirs(pending_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(
            "pending", selected_class, f"unrecognized_{timestamp}.png"
        )
        cv2.imwrite(filepath, screen)
    except Exception as e:
        print(f"❌ Error saving unrecognized ability: {str(e)}")


def clean_pending_folder():
    pending_dir = "pending"
    if os.path.exists(pending_dir):
        shutil.rmtree(pending_dir)
    os.makedirs(pending_dir, exist_ok=True)
    print("🗑️ Cleaned pending folder")


if __name__ == "__main__":
    clean_pending_folder()
    load_keybinds()
    load_settings()

    print("🎲 Please select your class")
    select_class()

    if selected_class is None:
        print("🚫 No class selected. Exiting...")
        exit()

    ability_templates = load_ability_templates()
    if not ability_templates:
        print("🚫 No abilities loaded. Exiting...")
        exit()

    if "overlay_position" in settings:
        print("📌 Overlay at saved position")
    else:
        print("📌 Position overlay over Hekili")

    create_overlay()
