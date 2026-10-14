from customtkinter import (CTk,
                           CTkFrame,
                           CTkBaseClass,
                           CTkTextbox,
                           CTkButton,
                           CTkProgressBar,
                           CTkLabel)
from requests import Session
from typing import TYPE_CHECKING, TypeVar
from threading import Thread
from os import makedirs as os_makedirs, remove as os_remove
from os.path import (abspath as osp_abspath, 
                     expanduser as osp_expanduser, 
                     isfile as osp_isfile, 
                     splitext as osp_splitext)
from math import floor
from .url import url_get_filename, get_filename_from_content_disposition
from .log import log, log_exception
from .env import get_env_var
from .system import desktop_notification

if TYPE_CHECKING:
    from .wrapper import Wrapper
else:
    Wrapper = TypeVar("Wrapper")

class FileURLDownloaderWidget(CTkFrame):
    def __init__(self, parent: CTkBaseClass, url: str, session: Session, **kwargs):
        super().__init__(parent, corner_radius=5)
        self.pack(fill="x", padx=5, pady=5)
        self._setup_widgets(url)
        
        self.url = url
        self.progress_value: float = 0
        self.download_thread: Thread = None
        
        self.was_download_success = False
        self.was_download_cancelled = False
        self.was_download_size_reported = False
        self.is_downloading = False
        
        self.session = session
        self.true_parent: Wrapper = kwargs.get("true_parent", None)
        
    def _setup_widgets(self, url: str):
        self.url_textbox = CTkTextbox(self, 250, height=5, activate_scrollbars=False, wrap="none")
        self.url_textbox.pack(side="left", padx=5, pady=5, fill="x")
        self.url_textbox.insert("0.0", url)
        self.url_textbox.configure(state="disabled")

        self.control_frame = CTkFrame(self, height=5, corner_radius=5)
        self.control_frame.pack(side="right", padx=5, pady=5, fill="x", expand=True)

        self.progress_bar = CTkProgressBar(self.control_frame, 125, progress_color="#4a4d50")
        self.progress_bar.pack(side="left", padx=5)
        self.progress_bar.set(0)
             
        self.remove_button = CTkButton(self.control_frame, 
                                        10, 10, 
                                        text="X", fg_color="red", hover_color="darkred", 
                                        command=self.remove)
        self.remove_button.pack(side="right", padx=5)
        
        self.download_button = CTkButton(self.control_frame,
                                        text="Download", text_color_disabled="white", 
                                        command=self._start_download_thread)
        self.download_button.pack(side="right", padx=5, pady=5)
        
        self.percent_label = CTkLabel(self.control_frame, text="0%")
        self.percent_label.pack(side="right", padx=5, pady=5)

    def remove(self):
        log(f"Removing download task: {self.url}")
        self.destroy()
        
        if self.true_parent:
            del self.true_parent.downloader_widgets[self.url]
            self.true_parent.update()
            
    # def event_generate(self, *args, **kwargs):
    #     if self.test_env: return
    #     super().event_generate(*args, **kwargs)

    def bind_events(self, root: CTk):
        root.bind(f"<<{self.url} download>>", self._downloading_state)
        root.bind(f"<<{self.url} fail>>", self._fail_state)
        root.bind(f"<<{self.url} cancel>>", self._cancelled_state)
        root.bind(f"<<{self.url} success>>", self._success_state)
        root.bind(f"<<{self.url} progress>>", self._progress_update)
    
    def _create_download_thread(self):
        log(f"Creating download thread: {self.url}")
        return Thread(
            target=self._download_file, 
            name=f"FileURLDownload @ \"{self.url}\"",
            daemon=True
        )
    
    def _start_download_thread(self):
        self.download_thread = self._create_download_thread()
        log(f"Starting download thread: {self.url}")
        self.download_thread.start()
    
    # I don't know if this is the right way to save resources
    def _clear_download_thread(self):
        self.download_thread = None
    
    def _downloading_state(self, _):
        self.progress_bar.configure(progress_color="#1f6aa5")
        self.download_button.configure(text="Downloading, Cancel?", 
                                       fg_color="#4a4d50", hover_color="darkred",
                                       state="normal", command=self._cancel_download_file)
        self.remove_button.configure(fg_color="darkred", state="disabled")
        self.update()

    def _fail_state(self, _):
        self.progress_bar.configure(progress_color="red")
        self.download_button.configure(text="Failed. Retry?", 
                                       fg_color="red", hover_color="darkred", 
                                       state="normal", command=self._start_download_thread)
        self.remove_button.configure(fg_color="red", state="normal")
        self.update()

    def _cancelled_state(self, _):
        self.progress_bar.configure(progress_color="red")
        self.download_button.configure(text="Cancelled. Retry?", 
                                       fg_color="red", hover_color="darkred", 
                                       state="normal", command=self._start_download_thread)
        self.remove_button.configure(fg_color="red", state="normal")
        self.update()
         
    def _success_state(self, _):
        self.progress_bar.configure(progress_color="green")
        self.download_button.configure(text="Completed!", 
                                       fg_color="green", 
                                       state="disabled", command=self._start_download_thread)
        self.remove_button.configure(fg_color="red", state="normal")
        self.update()
    
    def _progress_update(self, _):
        if self.was_download_size_reported:
            self.progress_bar.set(self.progress_value)
            self.percent_label.configure(text=f"{floor(self.progress_value * 100)}%")
        else:
            self.percent_label.configure(text="???%")
            
        self.update()

    def _progress_indeterminate_start(self):
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.update()

    def _progress_indeterminate_stop(self, success: bool):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        if success:
            self.progress_bar.set(1)
            self.percent_label.configure(text="100%")
        else:
            self.progress_bar.set(0)
            self.percent_label.configure(text="???%")
        
        self.update()
    
    def _cancel_download_file(self):
        self.was_download_cancelled = True
    
    def _download_file(self):
        self.was_download_cancelled = False
        self.is_downloading = True
        self.event_generate(f"<<{self.url} download>>")
        log(f"Downloading URL: {self.url}")
        
        try:
            self._request_file()
        except Exception as e:
            log_exception(e)
            
        if not self.was_download_size_reported:
            self._progress_indeterminate_stop(self.was_download_success)
        
        if self.was_download_success:
            self.event_generate(f"<<{self.url} success>>")
            log(f"Download successful: {self.url}")
            desktop_notification("Download successful", self.url)
            
        elif not self.was_download_success and not self.was_download_cancelled:
            self.event_generate(f"<<{self.url} fail>>")
            log(f"Download failed: {self.url}")
            desktop_notification("Download failed", self.url)

        elif not self.was_download_success and self.was_download_cancelled:
            self.event_generate(f"<<{self.url} cancel>>")
            log(f"Cancelling download: {self.url}")
        
        self.is_downloading = False
        self._clear_download_thread()
        
    def _request_file(self):
        subfolder = "SimpleFileDownloader"
        destination_dir = osp_abspath(f"{osp_expanduser('~')}/Downloads/{subfolder}")
        LOG_PRINT_DOWNLOAD_PROGRESS = get_env_var("LOG_PRINT_DOWNLOAD_PROGRESS") == "true"
        
        with self.session.get(self.url, stream=True, allow_redirects=True) as response:
            content_disposition: str = response.headers.get("content-disposition", None)
            filename = get_filename_from_content_disposition(content_disposition) or url_get_filename(response.url)
            
            is_response_ok = response.ok
            total_size = int(response.headers.get("content-length", 0))
            self.was_download_size_reported = total_size > 0
            
            log(f"Response Status: {response.status_code}: {self.url}")
            
            if self.was_download_size_reported:
                log(f"Total size: {total_size}: {self.url}")
            else:
                log(f"Total size: UNKNOWN: {self.url}")
            
            if not is_response_ok: return
                
            os_makedirs(destination_dir, exist_ok=True)
            file_destination = f"{destination_dir}/{filename}"
            
            i = 1
            base_filename, extension = osp_splitext(filename)
            while osp_isfile(file_destination):
                file_destination = f"{destination_dir}/{base_filename} ({i}){extension}"
                i += 1
                
            with open(file_destination, "wb") as file:
                downloaded_size = 0
                
                if not self.was_download_size_reported:
                    self._progress_indeterminate_start()
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk and not self.was_download_cancelled:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if self.was_download_size_reported:
                            progress_percentage = downloaded_size / total_size
                            self.progress_value = progress_percentage
                            
                            if LOG_PRINT_DOWNLOAD_PROGRESS:
                                log(f"[{round(progress_percentage * 100, 2)}% | {downloaded_size} / {total_size}] {self.url}")
                        
                        elif not self.was_download_size_reported and LOG_PRINT_DOWNLOAD_PROGRESS:
                            log(f"[???% | {downloaded_size} / ???] {self.url}")
                        
                        self.event_generate(f"<<{self.url} progress>>")
                    
                    elif self.was_download_cancelled:
                        break
                
                if not self.was_download_cancelled:
                    self.was_download_success = True
                    log(f"File saved as \"{file_destination}\"")

            if self.was_download_cancelled:
                os_remove(file_destination)
                