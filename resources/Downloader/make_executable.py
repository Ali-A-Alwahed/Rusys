from os import system as os_system
from platform import system as pf_system
from main import __version__, RELEASE_STATE

def include_data_dir(dir: str) -> str:
    return f"--include-data-dir={dir}={dir}"

def program_icon(filename: str) -> str:
    match pf_system():
        case "Windows":
            return f"--windows-icon-from-ico={filename}"
        
        case "Linux":
            return f"--linux-icon={filename}"
        
        case "Darwin":
            return f"--macos-app-icon={filename}"
        
        case _:
            raise SystemError("Unsupported system")

def make_executable(version: str):
    options = (
        # General
        "--standalone",
        "--onefile",
        # "--quiet",
        "--assume-yes-for-downloads",
        "--windows-console-mode=attach",
        
        # Plugins
        "--enable-plugin=tk-inter",
        
        # Files
        include_data_dir("assets"),
        
        # Output
        "--output-dir=build/",
        f"--output-filename=SimpleFileDownloader_{RELEASE_STATE}_v{version}",
        
        # Program File Information
        "--company-name=OhRetro",
        "--product-name=SimpleFileDownloader",
        f"--product-version={version}",
        f"--file-version={version}",
        
        # Program Icon
        program_icon("assets/icon.ico"
                     if pf_system() == "Windows" else 
                     "assets/icon.png"),
    )

    _options = " ".join(options)
    
    # subprocess.run() raises an exception
    os_system(f"nuitka {_options} main.py")

if __name__ == "__main__":
    make_executable(__version__)
    