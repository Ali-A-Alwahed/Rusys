from customtkinter import (CTk,
                           CTkFrame,
                           CTkButton,
                           CTkScrollableFrame,
                           CTkEntry)
from tkinter import messagebox as tk_messagebox
from requests import Session
from .url import url_is_valid, get_random_url_example
from .widgets import FileURLDownloaderWidget
from .log import log

class Wrapper(CTkFrame):
    def __init__(self, root: CTk, session: Session, **kwargs):
        super().__init__(root)
        self.downloader_widgets: dict[str, FileURLDownloaderWidget] = {}
        self.session = session

        self._setup_widgets()
        self.add_url_examples(kwargs.get("url_example", 0))

    def _setup_widgets(self):
        entry_frame = CTkFrame(self)
        entry_frame.pack(fill="x", padx=10, pady=10)

        self.url_entry = CTkEntry(entry_frame, placeholder_text="Type/Paste a file URL")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=5)

        self.add_button = CTkButton(entry_frame, text="Add", command=self.on_add_button_clicked)
        self.add_button.pack(side="left", padx=5, pady=5)
        
        control_frame = CTkFrame(self)
        control_frame.pack(fill="x", padx=10, pady=0)

        self.download_all_button = CTkButton(control_frame, text="Download All", command=self.on_download_all_button_clicked)
        self.download_all_button.pack(side="left", padx=5, pady=5, fill="x", expand=True)

        self.remove_completed_button = CTkButton(control_frame, text="Remove Completed", fg_color="red", hover_color="darkred", command=self.on_remove_completed_button_clicked)
        self.remove_completed_button.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        self.remove_all_button = CTkButton(control_frame, text="Remove All", fg_color="red", hover_color="darkred", command=self.on_remove_all_button_clicked)
        self.remove_all_button.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        self.list_of_download_task = CTkScrollableFrame(self, label_text="URLs list")
        self.list_of_download_task.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.update()
        
        log(f"{self.__class__.__name__} Widgets Setup!")
    
    # TODO: see an efficient way to update the label, and also implement this
    def _update_list_of_download_task_label_text(self):
        urls_count = len(self.downloader_widgets)
        self.list_of_download_task.configure(label_text=f"URLs list | {urls_count} Tasks")
        self.update()
        
    def _download_all_warning(self):
        log("Too many download tasks to do at the same!")
        user_consent = tk_messagebox.askokcancel(
            "Too many downloads!", (
                "Are you sure you want to continue?\n"
                "It's recommended to download fewer than 10 files at the same time.\n"
                "Downloading more may make the app unstable and could crash your PC."
            )
        )
        
        log("User continues with the operation" 
            if user_consent else
            "User canceled the operation")
        
        return user_consent
        
    def on_download_all_button_clicked(self):
        dw_len = len(self.downloader_widgets)
        
        if dw_len > 10:
            user_consent = self._download_all_warning()
            if not user_consent: return
        
        if dw_len > 0:
            log(f"Downloading all!")
        else:
            log("No URLs to download!")
            return
            
        for _, widget in self.downloader_widgets.items():
            widget: FileURLDownloaderWidget
            if not widget.is_downloading and not widget.was_download_success:
                widget.download_button.invoke()
                self.update()
            # else:
            #     log(f"Is already downloading or is completed: {url}")

    def on_remove_completed_button_clicked(self):
        is_there_completed_tasks = False
        
        for _, widget in self.downloader_widgets.items():
            if widget.was_download_success:
                is_there_completed_tasks = True
                break

        if is_there_completed_tasks:
            log(f"Removing Completed Tasks!")
        else:
            log("No Completed Tasks to remove!")
            return
        
        for url in reversed(list((self.downloader_widgets).keys())):
            widget: FileURLDownloaderWidget = self.downloader_widgets.get(url)
            if widget.was_download_success:
                widget.remove_button.invoke()
                self.update()
            # else:
            #     log(f"Can't remove as it's not successful: {url}")
                
    def on_remove_all_button_clicked(self):
        if len(self.downloader_widgets) > 0:
            log(f"Removing all!")
        else:
            log("No URLs to remove!")
            return
        
        for url in reversed(list((self.downloader_widgets).keys())):
            widget: FileURLDownloaderWidget = self.downloader_widgets.get(url)
            if not widget.is_downloading:
                widget.remove_button.invoke()
                self.update()
            # else:
            #     log(f"Can't remove as it's downloading: {url}")
            
    def on_add_button_clicked(self):
        url = self.url_entry.get()
        self.add_downloader_widget(url)
        self.url_entry.delete(0, "end")
        self.update()

    def add_downloader_widget(self, url: str):
        success = False
        if url and not url_is_valid(url):
            error_message = f"The provided link is not a valid URL:\n\"{url}\"\nPlease enter a valid URL."
            tk_messagebox.showerror("Invalid URL", error_message)
            log(error_message)

        elif url and url_is_valid(url) and url in self.downloader_widgets:
            error_message = f"The provided link is already in the list:\n\"{url}\""
            tk_messagebox.showerror("Already on List", error_message)
            log(error_message)
                     
        elif url and url_is_valid(url) and url not in self.downloader_widgets:
            success = True
            downloader_widget = FileURLDownloaderWidget(
                self.list_of_download_task, url, self.session,
                true_parent=self,
                )
            
            self.downloader_widgets[url] = downloader_widget
            downloader_widget.bind_events(self.master)
            
            log(f"Added URL: {url}")

        self.update()
        return success

    def add_url(self, url: str):
        self.add_downloader_widget(url)
    
    def add_url_examples(self, quantity: int):
        for _ in range(quantity):
            while True:
                choose = get_random_url_example()
                
                if choose in self.downloader_widgets:
                    continue
                else: break
            
            self.add_url(choose)
