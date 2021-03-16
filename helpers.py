import datetime
import requests

def datestr_tuple_to_datetime(datestr_tuple, pattern):
    """
    Converts a tuple of date strings and their pattern to datetime obj
    """
    for datestr_idx in range(3):
        if pattern[datestr_idx] == 'B': # Month name full
            month = datetime.datetime.strptime(datestr_tuple[datestr_idx], '%B').month
        elif pattern[datestr_idx] == 'b': # Month name short
            month = datetime.datetime.strptime(datestr_tuple[datestr_idx], '%b').month
        elif pattern[datestr_idx] == 'm':
            month = int(datestr_tuple[datestr_idx])
        elif pattern[datestr_idx] == 'd':
            day = int(datestr_tuple[datestr_idx])
        elif pattern[datestr_idx] == 'Y':
            year = int(datestr_tuple[datestr_idx])
    return datetime.datetime(year, month, day)

def download_file(url, filename=None):
    """
    Downloads a (large) file from url to filename
    """
    print(f"Downloading {url} ...")
    if not filename:
        filename = url.split('/')[-1]
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return filename