import sys, os
import xbmc, xbmcgui, xbmcplugin
import urllib

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

def remove_duplicates(files):
    d = {}
    for x in files:
        d[x] = 1

    return list(d.keys())

def get_shares():
    shares = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetSources", "params": {"media": "video"}, "id": 1}'))['result']['shares']
    shares = [ s['file'] for s in shares ]

    results = []
    for s in shares:
        print "FOUND SHARE: %s" % s
        if s.startswith('addons://'):
            shares.remove(s)
        elif s.startswith('multipath://'):
            s = s.replace('multipath://', '')
            parts = s.split('/')
            parts = [ f.replace('%3a', ':') for f in parts ]
            parts = [ f.replace('%5c', '\\') for f in parts ]
            parts = [ f.replace('%2f', '/') for f in parts ]
            parts = [ f.replace('%21', '!') for f in parts ]

            for b in parts:
                if b:
                    results.append(b)
        else:
            results.append(s)

    return results

def get_movie_sources():
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "id": 1}'))
    movies = result['result']['movies']
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
                results.append(s)
                shares.remove(s)
    return results

def get_tv_files(show_errors):
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "id": 1}'))
    # NOTE:this should help me identify Yulquen's bug
    print "VideoLibrary.GetTVShows results: %s" % results
    tv_shows = result['result']['tvshows']
    files = []

    for tv_show in tv_shows:
        show_id = tv_show['tvshowid']
        show_name = tv_show['label']

        episode_result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "season": "all"}, "id": 1}' % show_id))

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
                results.append(s)
                shares.remove(s)
    return results

# plugin handle
handle = int(sys.argv[1])

FILE_EXTENSIONS = ['mpg', 'mpeg', 'avi', 'flv', 'wmv', 'mkv', '264', '3g2', '3gp', 'vob', 'mp4', 'mov', 'iso']
FILE_EXTENSIONS.extend(xbmcplugin.getSetting(handle, "custom_file_extensions").split(";"))

def file_has_extensions(file, extensions):
    # get the file extension, without a leading colon.
    extension = os.path.splitext(os.path.basename(file))[1][1:]

    extensions = [ f.lower() for f in extensions ]
    extension = extension.lower()

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
        return
    # use a horrid eval here to convert the string to a dictionary.
    result = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"fields": ["file", "label", "trailer"]}, "id": 1}'))
    movies = result['result']['movies']
    library_files = [ item['file'] for item in movies ]
    missing = []

    # this magic section adds the files from trailers and sets!
    for m in movies:
        f = m['file']

        if f.startswith("videodb://"):
            set_files = eval(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s"}, "id": 1}' % f))

            sub_files = [ item['file'] for item in set_files['result']['files'] ]

            library_files.extend(sub_files)
        elif f.startswith('stack://'):
            xbmcgui.Dialog().ok("Multi-file Movie!!", f)
            parts = f.split(' , ')
            parts = [ f.replace('%21', '!') for f in parts ]
            parts = [ f.replace('%3a', ':') for f in parts ]
            parts = [ f.replace('%5c', '\\') for f in parts ]
            parts = [ f.replace('%2f', '/') for f in parts ]

            for b in parts:
                results.append(b)
        else:
            try:
                trailer = m['trailer']
                if not trailer.startswith('http://'):
                    library_files.append(trailer)
            except KeyError:
                pass

    for movie_path in MOVIE_PATHS:
        movie_files = set(get_files(movie_path))
        library_files = set(library_files)

        if not library_files.issuperset(movie_files):
            print "%s contains missing movies!" % movie_path
            missing.extend(list(movie_files.difference(library_files)))

    for movie_file in missing:
        ext = os.path.splitext(movie_file.lower())[1]
        if movie_file.lower().endswith("trailer" + ext):
            print "%s is a trailer and will be ignored!" % movie_file
        else:
            addDirectoryItem(movie_file, isFolder=False, totalItems=len(missing))
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def show_tvshow_submenu():
    ''' Show TV shows missing from the library. '''
    TV_PATHS = remove_duplicates(get_tv_sources())
    if len(TV_PATHS) == 0 or len(TV_PATHS[0]) == 0:
        xbmcgui.Dialog().ok("ERROR!", "Could not detect TV paths! Contact developer!")
        return

    files = get_tv_files(True)

    for tv_path in TV_PATHS:
        tv_files = get_files(tv_path)

        for tv_file in tv_files:
            print "looking for %s in %s" % (tv_file, tv_path)
            if tv_file not in files:
                print "%s NOT found!" % tv_file
                addDirectoryItem(tv_file, isFolder=False)
            else:
                print "%s found!" % tv_file
                # it looks like it should be tv_files instead of files, but it's not.
                files.remove(tv_file)

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
