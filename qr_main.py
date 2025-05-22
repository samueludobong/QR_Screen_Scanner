import ctypes
import json
import os
import socket
import subprocess
import tempfile
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()
import re
from time import sleep
import pyperclip
import keyboard
from PyQt5 import uic, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QWidget, QSystemTrayIcon, QMenu, QAction, \
    QRubberBand, QMessageBox
from PyQt5.QtCore import Qt, QRect, QEvent, QThread, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtGui import QPixmap, QIcon
from pyzbar.pyzbar import decode
from PIL import Image, UnidentifiedImageError
import sys
import win32event
import win32api
import winerror
import webbrowser
dir = os.path.dirname(__file__)
# from supabase import create_client
# url = os.environ.get("SUPABASE_URL")
# key = os.environ.get("SUPABASE_KEY")
# supabase = create_client(url, key)
import requests

PORT = 65432
def send_to_existing_instance(image_path):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("localhost", PORT))
            s.sendall(image_path.encode())
        return True
    except ConnectionRefusedError:
        return False

def listen_for_image_paths(callback):
    def listener():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", PORT))
            s.listen()
            while True:
                conn, _ = s.accept()
                with conn:
                    data = conn.recv(1024)
                    if data:
                        callback(data.decode())
    threading.Thread(target=listener, daemon=True).start()

def check_if_already_running():
    mutex = win32event.CreateMutex(None, False, "Global\\QRBarcodeScanner_Mutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            0,
            "The application is already running.",
            "QR Barcode Scanner",
            0x40 | 0x1
        )
        sys.exit(0)


def run_as_admin():
    """Restart script as administrator if not already elevated."""
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()

class KeyPressListener(QThread):
    trigger = pyqtSignal()
    def __init__(self, app2, callback):
        super().__init__()
        self.app = app2
        self.target_sequence = ['shift', 'q', 'r']
        self.callback = callback
        self.current_sequence = []
        sleep(3)

    def run(self):
        """Listen for key events in a separate thread."""
        while True:
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                key = event.name.lower()
                self.current_sequence.append(key)
                if len(self.current_sequence) > len(self.target_sequence):
                    self.current_sequence.pop(0)
                if self.current_sequence == self.target_sequence:
                    self.trigger.emit()
                    self.current_sequence.clear()

class QRScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.found_name = None
        self.actual_title = None
        self.user_return = None
        self.text_qr = None
        self.manual_mode = None
        self.pinmode = 0
        self.currenturl = None
        self.selection_widget = None
        relative_path = os.path.join(dir, "frames/mainframe.ui")
        ui_path = os.path.abspath(relative_path)
        uic.loadUi(ui_path, self)
        self.setFixedSize(332, 470)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""border-radius: 20px;""")
        self.text = 0
        self.manual_capture_btn.clicked.connect(self.manual_capture)
        self.reload.clicked.connect(self.automatic_qr_scan)
        self.hover_button = None
        self.key_listener = KeyPressListener(self, self.automatic_qr_scan)
        self.key_listener.start()
        self.key_listener.trigger.connect(self.automatic_qr_scan)
        screen_geometry = QApplication.desktop().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        self.stackedWidget.setCurrentWidget(self.fallback)
        QApplication.setQuitOnLastWindowClosed(False)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool | Qt.FramelessWindowHint)
        self.move(screen_width - self.width(), screen_height - self.height())
        self.task_setup()
        self.pinbtn.toggled.connect(self.pin_state)
        icon = QIcon(os.path.join(dir, "frames/keep.png"))
        self.pinbtn.setIcon(icon)
        self.pinbtn_2.toggled.connect(self.pin_state)
        icon = QIcon(os.path.join(dir, "frames/keep.png"))
        self.pinbtn_2.setIcon(icon)
        self.label_46.setPixmap(
            QtGui.QPixmap(os.path.join(dir, "frames/main_icon.png")))
        self.pinmode = 0
        self.open_main_menu()
        if image_path:
            try:
                if image_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")):
                    img = Image.open(image_path)
                    self.pic_from_windows(img)
                else:
                    raise ValueError("Unsupported file type.")
            except (UnidentifiedImageError, ValueError, FileNotFoundError) as e:
                sys.exit(1)
        # self.profile()

    def focus_on_start(self):
        self.text_start()
        filename = "index.txt"
        if os.path.exists(filename):
            with open(filename, "r") as file:
                content = file.read()
        if content == "0":
            self.show()
            self.raise_()
            self.activateWindow()
            with open(filename, "w") as file:
                file.write("1")
        else:
            pass


    def text_start(self):
        filename = "index.txt"
        if not os.path.exists(filename):
            with open(filename, "w") as file:
                file.write("0")
            print(f"{filename} created.")
            self.read_output()
        else:
            self.read_output()

    def read_output(self):
        filename = "index.txt"
        if os.path.exists(filename):
            with open(filename, "r") as file:
                content = file.read()
                self.user_return = content

    def task_setup(self):
        tray_icon_path = self.resource_path("frames/icon.ico")
        self.tray_icon = QSystemTrayIcon(QIcon(tray_icon_path), self)
        self.tray_icon.setToolTip("QR BarCode Scanner")
        tray_menu = QMenu(self)
        restore_action = QAction("Retore Window", self)
        restore_action.triggered.connect(self.restore_main_to)
        quick_action = QAction("Quick Scan", self)
        quick_action.triggered.connect(self.automatic_qr_scan)
        manual_action = QAction("Manual Scan", self)
        manual_action.triggered.connect(self.manual_capture)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quick_action)
        tray_menu.addAction(manual_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_icon_activated)
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "Systray", "No system tray detected")
            sys.exit(1)

    def quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()

    def restore_main_to(self):
        self.open_main_menu()
        self.restore_from_tray()

    def pin_state(self, checked):
        try:
            if checked:
                self.pinmode = 1
                icon = QIcon(os.path.join(dir, "frames/keep_off.png"))
                self.pinbtn.setIcon(icon)
                icon = QIcon(os.path.join(dir, "frames/keep_off.png"))
                self.pinbtn_2.setIcon(icon)
            else:
                self.pinmode = 0
                icon = QIcon(os.path.join(dir, "frames/keep.png"))
                self.pinbtn.setIcon(icon)
                icon = QIcon(os.path.join(dir, "frames/keep.png"))
                self.pinbtn_2.setIcon(icon)
        except Exception as E:
            print(E)

    def showEvent(self, event):
        """Ensure the window starts with focus on show."""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def on_focus_changed(self, old_widget, new_widget):
        """Handle focus change to minimize the window when focus is lost."""
        if old_widget == self and new_widget is None:
            self.hide_to_tray()

    def mouseDoubleClickEvent(self, event):
        """Restore window on double-click (when minimized to tray)."""
        if self.isMinimized():
            self.open_main_menu()
            self.restore_from_tray()

    def open_main_menu(self):
        self.stackedWidget.setCurrentWidget(self.main_window_)
        # icon = QIcon(os.path.join(dir, "frames/add.png"))
        # self.adduser.setIcon(icon)
        self.adduser.hide()
        self.listWidget.hide()
        self.label_5.hide()
        filename = "account_skip.txt"
        if os.path.exists(filename):
            with open(filename, "r") as file:
                content = file.read()
            if content == "1":
                self.adduser.show()
            else:
                self.adduser.hide()
                # try:
                #     with open("session.json", "r") as f:
                #         session_data = json.load(f)
                #     supabase.auth.set_session(
                #         session_data["access_token"],
                #         session_data["refresh_token"]
                #     )
                #     print("Session restored.")
                # except FileNotFoundError:
                #     print("No saved session found.")
        # self.adduser.clicked.connect(self.profile)
        self.auto3.clicked.connect(self.automatic_qr_scan)
        self.manual3.clicked.connect(self.manual_capture)
        # self.label_5.setText()

    def hide_to_tray(self):
        """Minimize the window to the system tray."""
        filename = "index.txt"
        if os.path.exists(filename):
            with open(filename, "r") as file:
                content = file.read()
        self.hide()
        self.setWindowState(self.windowState() | Qt.WindowMinimized)
        if content == "0":
            self.tray_icon.showMessage("QR BarCode Scanner", "We're Still Here In Tray If You Need Us", QSystemTrayIcon.Information, 2000)
            with open(filename, "w") as file:
                file.write("1")
        else:
            pass

    def restore_from_tray(self):
        """Restore the window from the system tray."""
        self.showNormal()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.activateWindow()
        self.raise_()

    def tray_icon_activated(self, reason):
        """Handle the system tray icon activation (double-click or click)."""
        if reason == QSystemTrayIcon.Trigger:
            self.restore_from_tray()

    def event(self, event):
        try:
            if self.pinmode == 1:
                pass
            else:
                if event.type() == QEvent.WindowDeactivate:
                    self.hide_to_tray()
                    return True
            return super().event(event)

        except Exception as E:
            pass
            return False

    def profile(self):
        self.pinmode = 1
        self.label_2.setPixmap(
            QtGui.QPixmap(os.path.join(dir, "frames/main_icon.png")))
        filename = "account_skip.txt"
        if os.path.exists(filename):
            with open(filename, "r") as file:
                content = file.read()
            if content == "1":
                self.pinmode = 0
                self.open_main_menu()
        else:
            self.stackedWidget.setCurrentWidget(self.start)
            self.skip_uss.clicked.connect(self.skip_account)
            self.addus.clicked.connect(self.add_us)
            self.adduser_5.clicked.connect(self.close)

    def skip_account(self):
        filename = "account_skip.txt"
        if not os.path.exists(filename):
            with open(filename, "w") as file:
                file.write("1")
            print(f"{filename} created.")
            self.pinmode = 0
            self.open_main_menu()
        else:
            pass

    def add_us(self):
        icon = QIcon(os.path.join(dir, "frames/cancel.png"))
        self.adduser_3.setIcon(icon)
        self.stackedWidget.setCurrentWidget(self.startup_user)
        self.createus.clicked.connect(self.create_us)
        self.adduser_3.clicked.connect(self.profile)
        self.lolin.clicked.connect(self.pull_req)

    def pull_req(self):
        users_email = self.emailus.text().strip()
        users_password = self.passus.text().strip()
        result = supabase.auth.sign_in_with_password({ "email": users_email, "password": users_password })
        if result.session:
            with open("session.json", "w") as f:
                json.dump(result.session.model_dump(), f, default=str)
            print("Login successful. Session saved.")
            filename = "account_skip.txt"
            if not os.path.exists(filename):
                with open(filename, "w") as file:
                    file.write("0")
                print(f"{filename} created.")
                self.pinmode = 0
                self.open_main_menu()
            else:
                pass
        else:
            print("Login failed.")

    def create_us(self):
        icon = QIcon(os.path.join(dir, "frames/cancel.png"))
        self.adduser_4.setIcon(icon)
        self.stackedWidget.setCurrentWidget(self.create)
        self.backtous.clicked.connect(self.add_us)
        self.adduser_4.clicked.connect(self.profile)
        self.createfinal.clicked.connect(self.add_test)

    def add_test(self):
        username = self.usernamefield.text().strip()
        email = self.emailfield.text().strip()
        password = self.passwordfield.text()
        confirmit = self.confirm_da_password.text()
        user = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "display_name": username
                }
            }
        })
        print(user)

    def automatic_qr_scan(self):
        """Captures the screen, scans for QR codes, and processes them accordingly."""
        self.hide_to_tray()
        screenshot_path = "entire_screen.png"
        try:
            screen = QGuiApplication.primaryScreen()
            screenshot = screen.grabWindow(0)
            screenshot.save(screenshot_path)
            image = Image.open(screenshot_path)
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return
        qr_codes = decode(image)
        try:
            self.manual_capture_btn.clicked.disconnect()
        except TypeError:
            pass
        if qr_codes:
            self.handle_qr_found(qr_codes)
        else:
            self.handle_no_qr_found()
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

    def pic_from_windows(self, pic):
        qr_codes = decode(pic)
        if qr_codes:
            self.handle_qr_found(qr_codes)
            self.restore_from_tray()
        else:
            self.handle_no_qr_found()
            self.restore_from_tray()

    def get_icon_path_from_url(self, url):
        temp_icon_path = os.path.join(tempfile.gettempdir(), "iconic.png")
        try:
            favicon_url = f"https://www.google.com/s2/favicons?sz=256&domain_url={url}"
            response = requests.get(favicon_url, timeout=3)
            if response.status_code == 200 and response.content:
                with open(temp_icon_path, "wb") as f:
                    f.write(response.content)
                print("Favicon saved.")
                return temp_icon_path
            else:
                raise Exception("No favicon content")
        except Exception:
            url = url.lower()
            if url.startswith("mailto:"):
                fallback_icon = "gmail.png"
            elif "wifi" in url or "192.168." in url:
                fallback_icon = "wifi.png"
            elif "github.com" in url:
                fallback_icon = "github.png"
            elif re.search(r"https?://|www\.", url):
                fallback_icon = "iconic.png"
            else:
                fallback_icon = "default.png"
            print(fallback_icon)
            fallback_path = self.resource_path(os.path.join("frames", fallback_icon))
            if os.path.exists(fallback_path):
                fallback_output = os.path.join(tempfile.gettempdir(), "yes.png")
                with open(fallback_path, "rb") as f:
                    with open(fallback_output, "wb") as out:
                        out.write(f.read())
                print(f"Used fallback icon: {fallback_icon}")
                return fallback_output
            else:
                print("Fallback icon not found.")
                return None

    def resource_path(self, relative_path):
        try:
            return os.path.join(sys._MEIPASS, relative_path)
        except AttributeError:
            return os.path.abspath(relative_path)

    def handle_qr_found(self, qr_codes):
        """Handles the logic when a QR code is detected."""
        self.tray_icon.showMessage("QR BarCode Scanner", f"QR code Received, Processing...",
                                   QSystemTrayIcon.Information, 2000)
        for qr_code in qr_codes:
            print(qr_code)
            qr_data = qr_code.data.decode("utf-8")
            self.currenturl = qr_data
            if os.path.exists("account_skip.txt"):
                with open("account_skip.txt", "r") as file:
                    content = file.read()
                if content.strip() == "1":
                    with open("history.txt", "a") as file:
                        file.write(self.currenturl + "\n")
                else:
                    self.adduser.hide()
            self.stackedWidget.setCurrentWidget(self.fallback)
            icon_path = self.get_icon_path_from_url(self.currenturl)
            if icon_path and os.path.exists(icon_path):
                self.label.setPixmap(QPixmap(icon_path))
            qr_type, action_text, action_func, found_name = self.detect_qr_type(qr_data)
            try:
                self.manual_capture_btn.clicked.disconnect()
            except TypeError:
                pass
            try:
                self.manual_capture_btn_2.clicked.disconnect()
            except TypeError:
                pass
            self.manual_capture_btn.setText(action_text)
            self.qr_state.setText(found_name)
            self.manual_capture_btn_2.clicked.connect(self.manual_capture)
            self.manual_capture_btn.clicked.connect(action_func)
            self.manual_capture_btn_2.show()
        QTimer.singleShot(4000, lambda: self.restore_from_tray())

    def handle_no_qr_found(self):
        """Handles the UI update when no QR code is found."""
        try:
            self.manual_capture_btn.clicked.disconnect()
        except TypeError:
            pass
        self.manual_capture_btn.clicked.connect(self.manual_capture)
        self.stackedWidget.setCurrentWidget(self.fallback)
        self.restore_from_tray()
        self.qr_state.setText("No QR Barcodes Found")
        self.label.setPixmap(QPixmap(os.path.join(dir, "frames/no.png")))
        self.manual_capture_btn.setText("Manual Capture")
        self.manual_capture_btn.clicked.connect(self.manual_capture)
        self.manual_capture_btn_2.hide()

    def detect_qr_type(self, data):
        insta_name = None
        wifi_data = self.currenturl.replace("WIFI:", "").split(";")
        wifi_info = {}
        for item in wifi_data:
            if ":" in item:
                key, value = item.split(":", 1)
                wifi_info[key] = value
        ssid = wifi_info.get("S", "").strip()
        Link_Title = self.get_link_title(self.currenturl)
        qr_patterns = {
            "url": (r"https?://|www\.", Link_Title, self.openn, "Link Found!!!"),
            "email": (r"^mailto:", "Send Email", self.open_email, "Email Link Found!!"),
            "phone": (r"^tel:", "Call Number", self.call_phone, "Cell-Phone Number Found!!"),
            "sms": (r"^sms:", "Send SMS", self.send_sms, "SMS Found!!"),
            "wifi": (r"^WIFI:", f"Connect to {ssid[0:20]}", self.connect_wifi, "Wi-Fi Network Found!!"),
            "geo": (r"^geo:", "View Location", self.view_location, "Location Found!!"),
            "crypto": (r"^bitcoin:|^ethereum:|^litecoin:", "Open Wallet", self.open_crypto_wallet, "Wallet Found!!"),
            "payment": (r"^upi://|^paypal.me/", "Make Payment", self.open_payment, "Payment Method Found!!!"),
        }
        for qr_type, (pattern, text, func, found_name) in qr_patterns.items():
            if re.search(pattern, data, re.IGNORECASE):
                return qr_type, text, func, found_name
        return "text", "Copy Text to Clipboard", self.manage_text, "Text Found!!!"

    def get_link_title(self, url):
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        path_parts = parsed.path.strip("/").split("/")

        platforms = {
            "instagram.com": {"label": "Instagram",
                              "ignore": ["p", "reel", "tv", "stories", "explore", "direct", "accounts"]},
            "tiktok.com": {"label": "TikTok", "ignore": ["video", "tag", "music", "discover"]},
            "twitter.com": {"label": "Twitter", "ignore": ["status", "hashtag", "i", "search"]},
            "x.com": {"label": "X", "ignore": ["status", "hashtag", "i", "search"]},
            "facebook.com": {"label": "Facebook",
                             "ignore": ["watch", "groups", "events", "pages", "photo", "photos", "videos",
                                        "marketplace"]},
            "threads.net": {"label": "Threads", "ignore": ["t"]},
            "youtube.com": {"label": "YouTube",
                            "ignore": ["watch", "shorts", "channel", "c", "user", "playlist", "results"]},
            "youtu.be": {"label": "YouTube", "ignore": []},
            "linkedin.com": {"label": "LinkedIn", "ignore": ["feed", "jobs", "company", "learning", "school"]},
            "github.com": {"label": "GitHub",
                           "ignore": ["features", "topics", "explore", "events", "sponsors", "about"]},
            "reddit.com": {"label": "Reddit", "ignore": ["r", "comments"]},
            "pinterest.com": {"label": "Pinterest", "ignore": ["pin"]},
            "snapchat.com": {"label": "Snapchat", "ignore": ["add", "stories"]},
            "twitch.tv": {"label": "Twitch", "ignore": ["videos", "directory", "p"]},
            "medium.com": {"label": "Medium", "ignore": ["tag", "topic", "p", "search"]},
            "telegram.me": {"label": "Telegram", "ignore": ["joinchat"]},
            "t.me": {"label": "Telegram", "ignore": ["joinchat"]},
            "behance.net": {"label": "Behance", "ignore": ["gallery"]},
            "dribbble.com": {"label": "Dribbble", "ignore": ["shots"]},
            "soundcloud.com": {"label": "SoundCloud", "ignore": ["tracks"]},
            "spotify.com": {"label": "Spotify", "ignore": ["track", "album", "playlist", "artist", "show", "episode"]}
        }

        platform_key = None
        for key in platforms:
            if key in host:
                platform_key = key
                break

        title = None
        if platform_key and path_parts:
            platform_data = platforms[platform_key]
            ignore_list = platform_data["ignore"]
            label = platform_data["label"]

            if platform_key == "reddit.com":
                if path_parts[0] == "user" and len(path_parts) > 1:
                    username = path_parts[1]
                    title = f"{username.capitalize()} on {label}"
            elif platform_key == "youtube.com":
                if path_parts[0] in ["c", "user", "channel"] and len(path_parts) > 1:
                    username = path_parts[1]
                    title = f"{username.capitalize()} on {label}"
            elif path_parts[0] not in ignore_list:
                username = path_parts[0]
                title = f"{username.capitalize()} on {label}"
        return title if title else url

    def open_email(self):
        """Opens the default email client."""
        os.system(f'start mailto:{self.currenturl.replace("mailto:", "")}')

    def call_phone(self):
        """Initiates a phone call (for mobile platforms)."""
        os.system(f'start {self.currenturl}')

    def send_sms(self):
        """Opens SMS application with pre-filled text."""
        os.system(f'start {self.currenturl}')

    def connect_wifi(self):
        """Parses Wi-Fi QR data and connects to the network."""
        print("SSID not found in QR data.")
        wifi_data = self.currenturl.replace("WIFI:", "").split(";")
        self.hide_to_tray()
        wifi_info = {}
        for item in wifi_data:
            if ":" in item:
                key, value = item.split(":", 1)
                wifi_info[key] = value
        ssid = wifi_info.get("S", "").strip()
        password = wifi_info.get("P", "").strip()
        encryption = wifi_info.get("T", "WPA").strip()
        if not ssid:
            print("SSID not found in QR data.")
            return
        if encryption == "WPA" or encryption == "WPA2":
            command = f'netsh wlan connect name="{ssid}"'
        else:
            command = f'netsh wlan connect ssid="{ssid}" key="{password}"'
        os.system(command)
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if "Connection request was completed successfully" in result.stdout:
            self.hide_to_tray()
            self.tray_icon.showMessage("QR BarCode Scanner", f"Connected to {ssid} Successfully",
                                       QSystemTrayIcon.Information, 2000)
        else:
            self.restore_from_tray()
            fallback_icon = "frames/wifi-slash.png"
            self.label.setPixmap(QPixmap(fallback_icon))
            self.manual_capture_btn.setText("Retry Connection")
            try:
                self.manual_capture_btn.clicked.disconnect()
            except TypeError:
                pass
            self.manual_capture_btn.clicked.connect(self.connect_wifi)
            self.qr_state.setText(f"Connection To {ssid[0:10]} Failed!!")
            self.manual_capture_btn_2.clicked.connect(self.manual_capture)
            self.manual_capture_btn_2.show()

    def view_location(self):
        """Opens a location in Google Maps."""
        os.system(f'start {self.currenturl}')

    def open_crypto_wallet(self):
        """Opens a cryptocurrency wallet app with the given address."""
        os.system(f'start {self.currenturl}')

    def open_payment(self):
        """Opens a payment app with the given UPI/PayPal link."""
        os.system(f'start {self.currenturl}')

    def openn(self):
        webbrowser.open(self.currenturl)
        self.hide_to_tray()

    def manage_text(self):
        print(self.text_qr)
        pyperclip.copy(self.text_qr)

    def manual_capture(self):
        self.manual_mode = ManualMode()
        self.manual_mode.link_found.connect(self.process_manual)
        self.manual_mode.show()

    def process_manual(self, links):
        try:
            self.manual_links = links
            file_path = 'screenshot.png'
            if os.path.exists(file_path):
                os.remove(file_path)
            if isinstance(links, list) and len(links) >= 1:
                self.handle_qr_found(links)
            else:
                self.handle_no_qr_found()

        except Exception as e:
            print(f"Error: {e}")
            return []


class ManualMode(QMainWindow):
    link_found = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Area for QR Scan")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.3)
        self.showFullScreen()
        self.setStyleSheet("background: rgba(0, 0, 0, 0);")
        self.start_point = None
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.rubber_band.setGeometry(QRect(self.start_point, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.start_point:
            rect = QRect(self.start_point, event.pos()).normalized()
            self.rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.rubber_band.hide()
            rect = self.rubber_band.geometry()
            self.capture_and_scan(rect)

    def capture_and_scan(self, rect):
        screen = QGuiApplication.primaryScreen()
        screenshot = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        screenshot.save("screenshot.png")
        image = Image.open("screenshot.png")
        qr_codes = decode(image)
        if qr_codes:
            self.close_window()
            self.link_found.emit(qr_codes)
        else:
            self.close_window()
            self.link_found.emit([])

    def close_window(self):
        self.hide()

if __name__ == "__main__":
    exe_path = sys.argv[0].lower()
    args = [arg for arg in sys.argv[1:] if arg.lower() != exe_path]
    image_path = args[0] if args else None
    if image_path and send_to_existing_instance(image_path):
        sys.exit(0)
    app = QApplication(sys.argv)

    def handle_new_image(path):
        window.pic_from_windows(Image.open(path))

    window = QRScannerApp()
    window.focus_on_start()
    if image_path:
        window.pic_from_windows(Image.open(image_path))
    listen_for_image_paths(handle_new_image)

    sys.exit(app.exec_())