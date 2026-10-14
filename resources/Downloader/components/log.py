from os import makedirs as os_makedirs
from traceback import format_exception
from datetime import datetime
from .env import get_env_var

_log_printing_enabled = get_env_var("LOG_PRINTING_ENABLED") == "true"
_log_text = ""

# Not the best way, but I needed a way to toggle
# I'm also aware of the logging module, but I wanted to make one
def log(message: str):
    global _log_text
    if is_log_printing_enabled(): print(message)
    _log_text += f"{message}\n"

def log_exception(exception: Exception):
    global _log_text
    bar = "=" * 100
    message = f"\n{bar}\n"
    message += "".join(format_exception(exception))
    message += f"{bar}\n"
    
    if is_log_printing_enabled(): print(message)
    _log_text += f"{message}\n"
    
def export_log_text():
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    
    destination_dir = "./logs"
    
    os_makedirs(destination_dir, exist_ok=True)
    with open(f"{destination_dir}/{timestamp}.log", "w", encoding="utf-8") as f:
        f.write(_log_text)

def set_log_printing_enabled(enabled: bool):
    global _log_printing_enabled
    _log_printing_enabled = enabled
    
def is_log_printing_enabled():
    return _log_printing_enabled
