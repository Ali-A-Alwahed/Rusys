import unittest
from main import App

class TestGUI(unittest.TestCase):
    def setUp(self):
        self.app = App(url_example=2, test_env=True)

    def tearDown(self):
        self.app.destroy()

    def test_download_all(self):
        self.app.wrapper.download_all_button.invoke()
        
        while True:
            all_downloaded = True
            
            for _, download_widget in self.app.wrapper.downloader_widgets.items():
                if download_widget.downloading:
                    all_downloaded = False
                    break
                elif not download_widget.download_success:
                    all_downloaded = False
            
            if all_downloaded:
                break
        
    def test_remove_all(self):
        self.app.wrapper.remove_all_button.invoke()

