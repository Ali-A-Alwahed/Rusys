from sys import exit as sys_exit
from customtkinter import CTk
from tkinter import PhotoImage
from requests import Session
from ua_generator import generate as ua_generate
from argparse import ArgumentParser
from components.wrapper import Wrapper
from components.log import (log, 
                            log_exception, 
                            export_log_text,
                            set_log_printing_enabled, 
                            is_log_printing_enabled)
from components.file import get_filepath

__version__ = "1.0.1"
RELEASE_STATES = (
    "Stable",
    "Beta"
)
RELEASE_STATE = RELEASE_STATES[0]

class App(CTk):
    def __init__(self, **kwargs):
        ua = ua_generate()
        log(f"Generated UA: {ua}")
        
        self.session = Session()
        self.session.headers.update(ua.headers.get())

        super().__init__()
        self.title(f"Simple File Downloader | {RELEASE_STATE} v{__version__}")
        self.set_icon(get_filepath("assets/icon.png"))
        self.geometry("700x450")
        self.resizable(False, False)
        self.center_window()
        self.wrapper = Wrapper(self, self.session, **kwargs)
        self.wrapper.pack(fill="both", expand=True, padx=10, pady=10)
        
    def destroy(self):
        super().destroy()
        
        #! Note to self, always remember to close sessions if using requests.Session() in the future.
        log(f"Closing session")
        self.session.close()
        
    def set_icon(self, icon_path: str):
        icon = PhotoImage(file=icon_path)
        self.wm_iconbitmap()
        self.wm_iconphoto(True, icon, icon)
        
    def center_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = self.winfo_width()
        height = self.winfo_height()
        
        y_offset = -(screen_height // 16)
        x = (screen_width // 2) - (width // 2)
        y = ((screen_height // 2) - (height // 2)) + y_offset
        
        self.geometry(f"{width}x{height}+{x}+{y}")

def main():
    parser = ArgumentParser(
        "Simple File Downloader",
        description="A Simple File Downloader made with Python and customtkinter"
        )
    parser.add_argument("-e", "--export-log", action="store_true", help="export logs into a file after closing the program")
    parser.add_argument("-l", "--log", action="store_true", help="enable log printing")
    parser.add_argument("--url-example", type=int, default=0, help="add example urls to download", metavar="QUANTITY")
    args = parser.parse_args()
    
    if not is_log_printing_enabled(): set_log_printing_enabled(args.log)
    
    app: App = None
    try:
        app = App(url_example=args.url_example)
        app.mainloop()
        
    except Exception as e:
        log_exception(e)
        if app: app.destroy()
    
    except KeyboardInterrupt:
        if app: app.destroy()
    
    if args.export_log:
        export_log_text()

if __name__ == "__main__":
    main()
    sys_exit()

# python -m unittest discover -s tests