from plyer import notification
from platform import system as pf_system

def desktop_notification(title: str, message: str):
    system = pf_system()
    
    if system == "Windows":
        app_icon = "assets/icon.ico"
    elif system in ("Linux", "Darwin"):
        app_icon = "assets/icon.png"
    else:
        return
    
    notification.notify(
        title=title,
        message=message,
        timeout=1,
        app_name="Simple File Downloader",
        app_icon=app_icon
    )
