from urllib.parse import urlparse, unquote
from random import randint, choice
from os.path import basename as osp_basename
from re import sub as re_sub, search as re_search

def sanitize_filename(filename: str) -> str:
    filename = unquote(filename)
    return re_sub(r'[\\/*?:"<>|]', "", filename)

def get_filename_from_content_disposition(content_disposition: str):
    if not content_disposition:
        return None

    filename_match = re_search(r'filename\*?="?([^;"]+)"?', content_disposition)
    if filename_match:
        return sanitize_filename(filename_match.group(1))
    
    return None

def url_get_filename(url: str) -> str:
    parsed_url = urlparse(url)
    filename = osp_basename(parsed_url.path)
    return sanitize_filename(filename)

def url_is_valid(url: str) -> bool:
    parsed_url = urlparse(url)
    return parsed_url.scheme in ["http", "https"] and bool(parsed_url.netloc)

def get_random_url_example():
    w = randint(100, 300) # Width
    h = randint(100, 300) # Height
    
    url_examples = [
        f"https://picsum.photos/{w}/{h}",
        
        "https://filesamples.com/samples/video/avi/sample_1280x720_surfing_with_audio.avi",
        "https://filesamples.com/samples/video/avi/sample_960x400_ocean_with_audio.avi",
        "https://filesamples.com/samples/video/avi/sample_640x360.avi",
        "https://filesamples.com/samples/video/avi/sample_960x540.avi",
        "https://filesamples.com/samples/video/avi/sample_1280x720.avi",
        "https://filesamples.com/samples/video/avi/sample_1920x1080.avi",
        "https://filesamples.com/samples/video/avi/sample_2560x1440.avi",
        "https://filesamples.com/samples/video/avi/sample_3840x2160.avi"
    ]

    return choice(url_examples)
    