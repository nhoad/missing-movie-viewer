import sys, os
import xbmc, xbmcgui, xbmcplugin
import unicodedata
import urllib

import datetime

# plugin modes
MODE_FIRST = 10
MODE_SECOND = 20
MODE_HELP = 30

# parameter keys
PARAMETER_KEY_MODE = "mode"

# menu item names
FIRST_SUBMENU = "Unadded Movies"
SECOND_SUBMENU = "Unadded TV Shows"
HELP_SUBMENU = "Help!"

def log(txt, severity=xbmc.LOGDEBUG):
    try:
        message = ("%s" % txt)
        xbmc.log(msg=message, level=severity)
    except UnicodeEncodeError:
        message = ("UnicodeEncodeError")
        xbmc.log(msg=message, level=xbmc.LOGWARNING) 

# plugin handle
log("THESE ARE THE SYS ARGUMENTS: %s" % sys.argv)
handle = int(sys.argv[1])

FILE_EXTENSIONS = ['mpg', 'mpeg', 'avi', 'flv', 'wmv', 'mkv', '264', '3g2', '3gp', 'ifo', 'mp4', 'mov', 'iso', 'ogm']
FILE_EXTENSIONS.extend(xbmcplugin.getSetting(handle, "custom_file_extensions").split(";"))

OUTPUT_FILE = xbmcplugin.getSetting(handle, "output_dir") + xbmcplugin.getSetting(handle, "output_file");
    
def remove_duplicates(files):
    # converting it to a set and back drops all duplicates
    return list(set(files))

def clean_name(text):
    #text = text.replace('%21', '!')
    #text = text.replace('%3a', ':')
    #text = text.replace('%5c', '\\')
    #text = text.replace('%2f', '/')
    #text = text.replace('%2c', ',')
    #text = text.replace('%5f', '_')
    #text = text.replace('%20', ' ')
    text = unicode(text, 'utf8')

    return text
    
def output_to_file(list):
    f = open(OUTPUT_FILE, 'a')
    for item in list:
        f.write(item + '\n')
    f.close()

def get_sources():
    sources = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetSources", "params": {"media": "video"}, "id": 1}'))['result']['sources']
    sources = [ s['file'] for s in sources ]

    results = []
    for s in sources:
        log("FOUND SOURCE: %s" % s, xbmc.LOGINFO)
        if s.startswith('addons://'):
            log("%s is an addon source, ignoring..." % s, xbmc.LOGINFO)
            sources.remove(s)
        elif s.startswith('multipath://'):
            log("%s is a multipath source, splitting and adding individuals..." % s, xbmc.LOGINFO)
            s = s.replace('multipath://', '')
            parts = s.split('/')
            parts = [ clean_name(f) for f in parts ]

            for b in parts:
                if b:
                    results.append(b)
        else:
            log("%s is a straight forward source, adding...", xbmc.LOGINFO)
            results.append(s)

    return results

def get_movie_sources():
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params":{"properties": ["file"]},  "id": 1}'))
    log(result, xbmc.LOGDEBUG)
    movies = result['result']['movies']
    log(movies, xbmc.LOGDEBUG)
    files = [ item['file'] for item in movies ]
    files = [ os.path.dirname(f) for f in files ]
    files = remove_duplicates(files)

    sources = remove_duplicates(get_sources())

    results = []
    for f in files:
        for s in sources:
            if f[-1] != os.sep:
                f += os.sep

            if f.startswith(s):
                log("%s was confirmed as a movie share using %s" % (s, f), xbmc.LOGINFO)
                results.append(s)
                sources.remove(s)
                
    return results

def get_tv_files(show_errors):
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "id": 1}'))
    log("VideoLibrary.GetTVShows results: %s" % result, xbmc.LOGDEBUG)
    tv_shows = result['result']['tvshows']
    files = []

    for tv_show in tv_shows:
        show_id = tv_show['tvshowid']
        show_name = tv_show['label']

        episode_result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["file"]}, "id": 1}' % show_id))
		
        try:
            episodes = episode_result['result']['episodes']
            files.extend([ unicode(e['file'], 'utf8') for e in episodes ])
        except KeyError:
            if show_errors:
                xbmcgui.Dialog().ok("ERROR!", "Could not retrieve episodes for %s!" % show_name, "Contact the developer if there actually are episodes!")

    return files

def get_tv_sources():
    files = get_tv_files(False)
    files = [ os.path.dirname(f) for f in files ]
    files = remove_duplicates(files)

    sources = remove_duplicates(get_sources())

    results = []
    for f in files:
        for s in sources:
            if f.startswith(s):
                log("%s was confirmed as a TV source using %s" % (s, f), xbmc.LOGINFO)
                results.append(s)
                sources.remove(s)
    return results

def file_has_extensions(filename, extensions):
    # get the file extension, without a leading colon.
    name, extension = os.path.splitext(os.path.basename(filename))
    name = name.lower()
    extension = extension[1:].lower()
    extensions = [ f.lower() for f in extensions ]

    if extension == 'ifo' and name != 'video_ts':
        return False

    return extension in extensions

def get_files(path):
    results = []
    for root, sub_folders, files in os.walk(unicode(path, 'utf8')):
        for f in files:
            if file_has_extensions(f, FILE_EXTENSIONS):
                f = os.path.join(root, f)
                results.append(f)

    return results

# utility functions
def parameters_string_to_dict(parameters):
    ''' Convert parameters encoded in a URL to a dict. '''
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = paramSplits[1]
    return paramDict

def addDirectoryItem(name, isFolder=True, parameters={}, totalItems=1):
    ''' Add a list item to the XBMC UI. '''
    li = xbmcgui.ListItem(name)

    url = sys.argv[0] + '?' + urllib.urlencode(parameters)

    if not isFolder:
        url  = name
    return xbmcplugin.addDirectoryItem(handle=handle, url=url, listitem=li, isFolder=isFolder,totalItems=totalItems)

# UI builder functions
def show_root_menu():
    ''' Show the plugin root menu. '''
    addDirectoryItem(name=FIRST_SUBMENU, parameters={ PARAMETER_KEY_MODE: MODE_FIRST }, isFolder=True)
    addDirectoryItem(name=SECOND_SUBMENU, parameters={ PARAMETER_KEY_MODE: MODE_SECOND }, isFolder=True)
    addDirectoryItem(name=HELP_SUBMENU, parameters={ PARAMETER_KEY_MODE: MODE_HELP }, isFolder=True)
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def show_movie_submenu():
    ''' Show movies missing from the library. '''
    movie_sources = remove_duplicates(get_movie_sources())
    if len(movie_sources) == 0 or len(movie_sources[0]) == 0:
        xbmcgui.Dialog().ok("ERROR!", "Could not detect movie sources! Contact developer!")
        log("No movie sources!", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle=handle, succeeded=False)
        return

    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params":{"properties": ["file"]},  "id": 1}'))
    movies = result['result']['movies']

    library_files = []
    missing = []

    log("SEARCHING MOVIES", xbmc.LOGNOTICE)
    # this magic section adds the files from trailers and sets!
    for m in movies:
        f = m['file']

        if f.startswith("videodb://"):
            set_files = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s"}, "id": 1}' % f))

            sub_files = []
            sub_trailers =  []

            for item in set_files['result']['files']:
                sub_files.append(unicode(item['file'], 'utf8'))
                try:
                    trailer = item['trailer']
                    if not trailer.startswith('http://'):
                        library_files.append(unicode(trailer, 'utf8'))
                except KeyError:
                    pass

            library_files.extend(sub_files)
            library_files.extend(sub_trailers)
        elif f.startswith('stack://'):
            f = f.replace('stack://', '')
            parts = f.split(' , ')

            parts = [ unicode(f, 'utf8') for f in parts ]

            for b in parts:
                library_files.append(b)
        else:
            library_files.append(unicode(f, 'utf8'))
            try:
                trailer = m['trailer']
                if not trailer.startswith('http://'):
                    library_files.append(unicode(trailer, 'utf8'))
            except KeyError:
                pass

    library_files = set(library_files)

    for movie_source in movie_sources:
        movie_files = set(get_files(movie_source))

        if not library_files.issuperset(movie_files):
            log("%s contains missing movies!" % movie_source, xbmc.LOGNOTICE)
            log("library files: %s" % library_files, xbmc.LOGDEBUG)
            l = list(movie_files.difference(library_files))
            l.sort()
            log("missing movies: %s" % l, xbmc.LOGNOTICE)
            missing.extend(l)
			
    if OUTPUT_FILE:        
        output_to_file(missing);
    
    for movie_file in missing:
        # get the end of the filename without the extension
        if os.path.splitext(movie_file.lower())[0].endswith("trailer"):
            log("%s is a trailer and will be ignored!" % movie_file, xbmc.LOGINFO)
        else:
            addDirectoryItem(movie_file, isFolder=False, totalItems=len(missing))

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def show_tvshow_submenu():
    ''' Show TV shows missing from the library. '''
    tv_sources = remove_duplicates(get_tv_sources())
    if len(tv_sources) == 0 or len(tv_sources[0]) == 0:
        xbmcgui.Dialog().ok("ERROR!", "Could not detect TV sources! Contact developer if they do exist!")
        log("No TV sources!", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle=handle, succeeded=False)
        return

    library_files = set(get_tv_files(True))
    missing = []

    log("SEARCHING TV SHOWS", xbmc.LOGNOTICE);
    for tv_source in tv_sources:
        tv_files = set(get_files(tv_source))

        if not library_files.issuperset(tv_files):
            log("%s contains missing TV shows!" % tv_source, xbmc.LOGNOTICE)
            log("library files: %s" % library_files, xbmc.LOGDEBUG)
            l = list(tv_files.difference(library_files))
            l.sort()
            log("missing episodes: %s" % l, xbmc.LOGNOTICE)
            missing.extend(l)

    if OUTPUT_FILE:
        output_to_file(missing)
        
    for tv_file in missing:
        addDirectoryItem(tv_file, isFolder=False)

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def show_help():
    xbmcgui.Dialog().ok("HELP!", "Add custom file types to settings.", "Then search!")

# parameter values
params = parameters_string_to_dict(sys.argv[2])
mode = int(params.get(PARAMETER_KEY_MODE, "0"))

# Depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
    # new start
    ok = show_root_menu()
elif mode == MODE_FIRST:
    ok = show_movie_submenu()
elif mode == MODE_SECOND:
    ok = show_tvshow_submenu()
elif mode == MODE_HELP:
    ok = show_help()
