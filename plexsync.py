import os
import sys
import json
import requests
import pathlib
import argparse
import time
import xml.etree.ElementTree as ET
from plexapi.server import PlexServer
from datetime import datetime, timezone

# example http://192.168.1.XXX:32400
PLEXURL = ''
# https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
PLEXTOKEN = ''

filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'anime-list.xml')

def getScudLee():
    # create element tree object from ScudLee XML
    # get ScudLee XML from github
    if not os.path.exists(filepath):
        scudleeXML = requests.get("https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list.xml")
        with open(filepath, "wb") as f:
            f.write(scudleeXML.content)
    else: 
        # update XML if its older than 24h
        try: 
            if time.time() - os.path.getmtime(filepath) > 60*60*24:
                scudleeXML = requests.get("https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list.xml")
                with open(filepath, "wb") as f:
                    f.write(scudleeXML.content)
        except OSError:
            scudleeXML = requests.get("https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list.xml")
            with open(filepath, "wb") as f:
                f.write(scudleeXML.content)

def anidbToTvdb(anidbid, episode=None):
    """Convert the Tvdb anime info into Anidb info

    Args:
        anidbid (int): TvdbID of the anime
        episode (int): Tvdb episode

    Returns:
        tvdbidb: Corresponding TvdbID of the anime
        season: Anime seasons in Tvdb
        episode: Anime episode in Tvdb
    """
    
    getScudLee()
    tree = ET.parse(filepath)
    root = tree.getroot()

    for anime in root.findall(f'./*[@anidbid="{anidbid}"]'):
        if anime.attrib['tvdbid'].isdigit():
            if not episode:
                return anime.attrib['tvdbid']
            if anime.attrib['defaulttvdbseason'] == 'a':
                # CANNOT HANDLE ABSOLUTE EPISODES MATCHING
                for map in anime.findall(f'./mapping-list/mapping/[@anidbseason="1"]'):
                    if not map.text == None:
                        l = map.text.split(";")
                        for eps in l[1:-1] :
                            eps = eps.split("-")
                            if int(eps[0]) == episode:
                                return int(anime.attrib['tvdbid']), int(map.attrib['tvdbseason']), int(eps[1])
                    if 'start' in map.attrib:
                        if int(map.attrib['start']) <= episode <= int(map.attrib['end']) :
                            if 'offset' in map.attrib:
                                return int(anime.attrib['tvdbid']), int(map.attrib['tvdbseason']), (episode + int(map.attrib['offset'])) 
                            else:
                                return int(anime.attrib['tvdbid']), int(map.attrib['tvdbseason']), episode              
            elif anime.attrib['defaulttvdbseason'].isdigit():
                # IGNORE SPECIALS
                for map in anime.findall(f'./mapping-list/mapping/[@anidbseason="1"]'):
                    if not map.text == None:
                        l = map.text.split(";")
                        for eps in l[1:-1] :
                            eps = eps.split("-")
                            if int(eps[0]) == episode:
                                return int(anime.attrib['tvdbid']), int(map.attrib['tvdbseason']), int(eps[1])
                    if 'start' in map.attrib:
                        if int(map.attrib['start']) <= episode <= int(map.attrib['end']) :
                            return int(anime.attrib['tvdbid']), int(map.attrib['tvdbseason']), (episode + int(map.attrib['offset']))
                if 'episodeoffset' in anime.attrib:
                    return int(anime.attrib['tvdbid']), int(anime.attrib['defaulttvdbseason']), episode + int(anime.attrib['episodeoffset'])
                else:
                    return int(anime.attrib['tvdbid']), int(anime.attrib['defaulttvdbseason']), episode
        elif 'tmdbid' in anime.attrib:
            return anime.attrib['tmdbid']
    return 0,0,episode

def updateWatchedState(guidLookup, plexLIB, allItems):
    # if video.title.lower() in animeshow["show"]["title"].lower():
    # print(video.title, " matched ", animeshow["show"]["title"])
    # Update Animes
    for animeshow in allItems["anime"]:
        completed = True if animeshow["status"] == "completed" else False
        ep_watched = int(animeshow["watched_episodes_count"])
        anidbid = animeshow["show"]["ids"]["anidb"]
        title = animeshow["show"]["title"]
        
        tmdbid = tvdbid = 0

        # Search for IDs in simkl
        if "tmdb" in animeshow["show"]["ids"]:
            tmdbid = animeshow["show"]["ids"]["tmdb"]
        elif animeshow["anime_type"] == "movie":
            tmdbid = anidbToTvdb(anidbid)
        if "tvdb" in animeshow["show"]["ids"]:
            tvdbid = animeshow["show"]["ids"]["tvdb"]
        elif animeshow["anime_type"] == "tv":
            tvdbid = anidbToTvdb(anidbid)
            
        print (f"Searching for {title} in plex with anidbid: {anidbid} matching tvdb-{tvdbid} or tmdb-{tmdbid}")
        # Look for the show in plex
        if f"tvdb://{tvdbid}" in guidLookup:
            # Mark each episode until last ep watched
            for i in range(1, ep_watched+1):
                tvdbid, season, episode = anidbToTvdb(anidbid, i)
                try:
                    if tvdbid:
                        plexLIB.getGuid(f"tvdb://{tvdbid}").episode(season=season, episode=episode).markWatched()
                        print(f"marked as watched ep{episode} for season {season} with anidb {anidbid}")
                    else:
                        print(f"\033[93mShow {title} is unsupported\033[0m")
                        break
                except:
                    print(f"\033[93mEpisode {episode} for season {season} NOT FOUND\033[0m")
        # Handle Anime Movies since Simkl as them as Anime
        if f"tmdb://{tmdbid}" in guidLookup and completed and animeshow["anime_type"] == "movie":
            print(f"marking movie {title} as watched with tmdbid: {tmdbid}")
            plexLIB.getGuid(f"tmdb://{tmdbid}").markWatched()

    # Update TV Shows
    for tvshow in allItems["shows"]:
        completed = True if tvshow["status"] == "completed" else False
        if int(tvshow["watched_episodes_count"]) > 0:
            lastseason = int(tvshow["last_watched"].split('E')[0][1:])
            lastepisode = int(tvshow["last_watched"].split('E')[1])
        else:
            lastseason = lastepisode = 0
        tvdbid = tvshow["show"]["ids"]["tvdb"]
        title = tvshow["show"]["title"]
        print (f"Searching for {title} in plex with tvdbid: {tvdbid}")
        # Look for the show in plex
        if f"tvdb://{tvdbid}" in guidLookup:
            # If the show is completed, dont look at episodes and just mark everything as watched
            if completed:
                plexLIB.getGuid(f"tvdb://{tvdbid}").markWatched()
                print(f"marking entire show {title} as watched with tvdbid: {tvdbid}")
            else:
            # Mark each episode of every season until last ep watched
                for season in range(1, lastseason+1):
                    for episode in range(1, lastepisode+1):
                        try:
                            plexLIB.getGuid(f"tvdb://{tvdbid}").episode(season=season, episode=episode).markWatched()
                            print(f"marked as watched ep{episode} for season {season} with tvdb {tvdbid}")
                        except:
                            print(f"\033[93mEpisode {episode} for season {season} NOT FOUND\033[0m")
    # Update Movies
    for movie in allItems["movies"]:
        completed = True if movie["status"] == "completed" else False
        tmdbid = movie["movie"]["ids"]["tmdb"]
        title = movie["movie"]["title"]
        print (f"Searching for {title} in plex with anidbid: {anidbid}")
        if f"tmdb://{tmdbid}" in guidLookup and completed:
            print(f"marking movie {title} as watched with tmdbid: {tmdbid}")
            plexLIB.getGuid(f"tmdb://{tmdbid}").markWatched()

def get_simkl_token_for_user(simkluser):
    filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'simkl_tokens', f'{simkluser}.txt')
    try:
        with open(filepath) as f:
            return f.readline().strip()
    except:
        print(f"No file named {simkluser}. Please run simkl_auth.py")
        return None

def getSimklWatched(simkluser):
    simkl_token = get_simkl_token_for_user(simkluser)
    #print (f"simkl token: {simkl_token}")

    filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'simkl_api_id.txt')

    try:
        with open(filepath) as f:
            simkl_client_id = f.readline().strip()
    except:
        print(f"No file named simkl_api_id.txt. Please create a file named simkl_api_id.txt and write the api id inside.")
        return

    if not simkl_client_id:
        print("No simkl api client id found. Please create a file named simkl_api_id.txt and write the api id inside.")
        return

    headers = {
        'Authorization': 'Bearer ' + simkl_token,
        'simkl-api-key': simkl_client_id,
        'Content-Type': 'application/json'
    }


    # https://api.simkl.com/sync/all-items/type?anime/status?date_from=2016-09-12T13%3A00%3A30Z
    # get all items list
    
    url = f"https://api.simkl.com/sync/all-items/"

    request_data = json.loads(requests.get(url, headers=headers).text)

    # with open('data.txt', 'w', encoding='utf-8') as f:
    #    json.dump(request_data, f, indent=4)
    return request_data

def main(simkluser, plexuser):

    try:
        plex = PlexServer(PLEXURL, PLEXTOKEN)
        # Switch plex login to user account
        # plex = plex.switchUser(plexuser)
    except Exception as e: 
        print(e)
        return 0

    # Get Simkl Data
    allItems = getSimklWatched(simkluser)

    # Get Plex Data
    # plexLIB = plex.library.section('TV')
    # guidLookup = {guid.id: item for item in plexLIB.all() for guid in item.guids}
    # print(plexLIB.getGuid("tvdb://362696").episode(season=2, episode=1))

    # print (plex.library.sections())

    for section in plex.library.sections():
        if section.type in ['movie', 'show']:
            print (f"\n\nSYNC {section.title}\n\n")
            guidLookup = {guid.id: item for item in section.all() for guid in item.guids}
            updateWatchedState(guidLookup, section, allItems)
    
    print ("Success.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--simkl', required=True)
    parser.add_argument('--plex', required=False)
    opts = parser.parse_args()
    main(opts.simkl, opts.plex)