import datetime

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