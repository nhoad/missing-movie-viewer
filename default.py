import sys, os
import xbmc, xbmcgui, xbmcplugin
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

# plugin handle
handle = int(sys.argv[1])

FILE_EXTENSIONS = ['mpg', 'mpeg', 'avi', 'flv', 'wmv', 'mkv', '264', '3g2', '3gp', 'ifo', 'mp4', 'mov', 'iso', 'ogm']
FILE_EXTENSIONS.extend(xbmcplugin.getSetting(handle, "custom_file_extensions").split(";"))

OUTPUT_FILE = xbmcplugin.getSetting(handle, "output_file");

if not OUTPUT_FILE:
    OUTPUT_FILE = '/home/xbmc/missing-movies.txt'

def remove_duplicates(files):
    # converting it to a set and back drops all duplicates
    return list(set(files))

def clean_name(text):
    text = text.replace('%21', '!')
    text = text.replace('%3a', ':')
    text = text.replace('%5c', '\\')
    text = text.replace('%2f', '/')
    text = text.replace('%2c', ',')
    text = text.replace('%5f', '_')
    text = text.replace('%20', ' ')

    return text

def get_shares():
    shares = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetSources", "params": {"media": "video"}, "id": 1}'))['result']['shares']
    shares = [ s['file'] for s in shares ]

    results = []
    for s in shares:
        print "FOUND SHARE: %s" % s
        if s.startswith('addons://'):
            print s + ' is an addon share, ignoring...'
            shares.remove(s)
        elif s.startswith('multipath://'):
            print s + ' is a multipath share, splitting and adding individuals...'
            s = s.replace('multipath://', '')
            parts = s.split('/')
            parts = [ clean_name(f) for f in parts ]

            for b in parts:
                if b:
                    results.append(b)
        else:
            print s + ' is a straight forward share, adding...'
            results.append(s)

    return results

def get_movie_sources():
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"fields": ["file"]}, "id": 1}'))
    print result
    movies = result['result']['movies']
    print movies
    files = [ item['file'] for item in movies ]
    files = [ os.path.dirname(f) for f in files ]
    files = remove_duplicates(files)

    shares = remove_duplicates(get_shares())

    results = []
    for f in files:
        for s in shares:
            if f[-1] != os.sep:
                f += os.sep

            if f.startswith(s):
                print s + ' was confirmed as a movie share using ' + f
                results.append(s)
                shares.remove(s)
    return results

def get_tv_files(show_errors):
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "id": 1}'))
    # NOTE:this should help me identify Yulquen's bug
    print "VideoLibrary.GetTVShows results: %s" % result
    tv_shows = result['result']['tvshows']
    files = []

    for tv_show in tv_shows:
        show_id = tv_show['tvshowid']
        show_name = tv_show['label']

        episode_result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d}, "id": 1}' % show_id))

        try:
            episodes = episode_result['result']['episodes']
            files.extend([ e['file'] for e in episodes ])
        except KeyError:
            if show_errors:
                xbmcgui.Dialog().ok("ERROR!", "Could not retrieve episodes for %s!" % show_name, "Contact the developer!")

        nothing = """
        seasons_result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetSeasons", "params": {"tvshowid": %d}, "id": 1}' % show_id))
        seasons = seasons_result['result']['seasons']
        # will probably need tweaking to pick up special seasons and whatnot.
        seasons = [ f['label'].split(' ')[1] for f in seasons if f['label'].startswith('Season')]

        for season_no in seasons:
            episode_result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "season": %s}, "id": 1}' % (show_id, season_no)))
            episodes = episode_result['result']['episodes']

            files.extend([ e['file'] for e in episodes ])
        """
    return files

def get_tv_sources():
    files = get_tv_files(False)
    files = [ os.path.dirname(f) for f in files ]
    files = remove_duplicates(files)

    shares = remove_duplicates(get_shares())

    results = []
    for f in files:
        for s in shares:
            if f.startswith(s):
                print s + ' was confirmed as a tv show share using ' + f
                results.append(s)
                shares.remove(s)
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
    for root, sub_folders, files in os.walk(path):
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
    ''' Add a list item to the XBMC UI.'''
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
    MOVIE_PATHS = remove_duplicates(get_movie_sources())
    if len(MOVIE_PATHS) == 0 or len(MOVIE_PATHS[0]) == 0:
        xbmcgui.Dialog().ok("ERROR!", "Could not detect movie paths! Contact developer!")
        xbmcplugin.endOfDirectory(handle=handle, succeeded=False)
        return

    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"fields": ["file", "title", "trailer"]}, "id": 1}'))
    movies = result['result']['movies']

    library_files = []
    missing = []

    # this magic section adds the files from trailers and sets!
    for m in movies:
        f = m['file']

        if f.startswith("videodb://"):
            set_files = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s"}, "id": 1}' % f))

            sub_files = []
            sub_trailers =  []

            for item in set_files['result']['files']:
                sub_files.append(clean_name(item['file']))
                try:
                    trailer = item['trailer']
                    if not trailer.startswith('http://'):
                        library_files.append(clean_name(trailer))
                except KeyError:
                    pass

            library_files.extend(sub_files)
            library_files.extend(sub_trailers)
        elif f.startswith('stack://'):
            f = f.replace('stack://', '')
            parts = f.split(' , ')

            parts = [ clean_name(f) for f in parts ]

            for b in parts:
                library_files.append(b)
        else:
            library_files.append(clean_name(f))
            try:
                trailer = m['trailer']
                if not trailer.startswith('http://'):
                    library_files.append(clean_name(trailer))
            except KeyError:
                pass

    library_files = set(library_files)

    for movie_path in MOVIE_PATHS:
        movie_files = set(get_files(movie_path))

        if not library_files.issuperset(movie_files):
            print "%s contains missing movies!" % movie_path
            print "missing movies: %s" % list(movie_files.difference(library_files))
            l = list(movie_files.difference(library_files))
            l.sort()
            missing.extend(l)

    f = None

    tmp = """try:
        f = open(OUTPUT_FILE, 'a')
    except IOError:
        f = open(OUTPUT_FILE, 'w')

    now = datetime.datetime.now()

    f.write('%s: search results for missing movies using the missing movies plugin:' % now.strftime('%Y-%m-%d %H:%M'))
    """
    for movie_file in missing:
        # get the end of the filename without the extension
        if os.path.splitext(movie_file.lower())[0].endswith("trailer"):
            print "%s is a trailer and will be ignored!" % movie_file
        else:
            addDirectoryItem(movie_file, isFolder=False, totalItems=len(missing))
            #f.write(tv_file)

    #f.close()

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def show_tvshow_submenu():
    ''' Show TV shows missing from the library. '''
    TV_PATHS = remove_duplicates(get_tv_sources())
    if len(TV_PATHS) == 0 or len(TV_PATHS[0]) == 0:
        xbmcgui.Dialog().ok("ERROR!", "Could not detect TV paths! Contact developer!")
        xbmcplugin.endOfDirectory(handle=handle, succeeded=False)
        return

    library_files = set(get_tv_files(True))
    missing = []

    for tv_path in TV_PATHS:
        tv_files = set(get_files(tv_path))

        if not library_files.issuperset(tv_files):
            print "%s contains missing TV shows!" % tv_path
            l = list(tv_files.difference(library_files))
            l.sort()
            missing.extend(l)

    f = None

    tmp = """try:
        f = open(OUTPUT_FILE, 'a')
    except IOError:
        f = open(OUTPUT_FILE, 'w')

    now = datetime.datetime.now()

    f.write('%s: search results for missing tv shows using the missing movies plugin:' % now.strftime('%Y-%m-%d %H:%M'))
    """
    for tv_file in missing:
        addDirectoryItem(tv_file, isFolder=False)
        #f.write(tv_file)

    #f.close()

    nothing = """
    for tv_file in tv_files:
        print "looking for %s in %s" % (tv_file, tv_path)
        if tv_file not in files:
            print "%s NOT found!" % tv_file
        else:
            print "%s found!" % tv_file
            # it looks like it should be tv_files instead of files, but it's not.
            files.remove(tv_file)
    """

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
