from tabulate import tabulate
import tmdbsimple as tmdb
import requests
import time
import json
import copy
import options
import os
import re

tmdb.API_KEY = options.TMDB_API_KEY


def search_tmdb(query, ismovie=False):
    if type(ismovie) is str:
        ismovie = True if ismovie.upper() == 'MOVIE' else False
    search = tmdb.Search().movie if ismovie else tmdb.Search().tv
    response = search(query=query)['results']
    if len(response) < 1:
        response = search(query=query.split(' ')[0])['results']
    ids = []
    for title in response:
        ids.append([str(title['id']), title['title' if ismovie else 'name']])
    result_dict = {}
    table_list = []
    count = 0
    languages = ['ja', 'cn', 'ko']
    for id_ in ids:
        f = (tmdb.Movies(int(id_[0])).info()) if ismovie else (tmdb.TV(int(id_[0])).info())  # noqa
        if 'original_language' in f:
            if f['original_language'] not in languages:
                continue
        elif 'languages' in f:
            found = False
            for lan in languages:
                if lan in f['languages']:
                    found = True
            if not found:
                continue
        result_dict[id_[0]] = {}
        result_dict[id_[0]]['title'] = id_[1]
        total_seasons = (1 if ismovie else int(f['number_of_seasons'])) + 1
        entry = [count, id_[1], total_seasons-1, id_[0]]
        table_list.append(entry)
        count += 1
        if ismovie:
            result_dict[id_[0]]['1'] = {}
            result_dict[id_[0]]['1']['1'] = {'title': id_[1], 'thumbnail': f"https://image.tmdb.org/t/p/original{f['poster_path']}"}  # noqa
        else:
            for k in range(total_seasons):
                try:
                    season_info = tmdb.TV_Seasons(int(id_[0]), season_number=k).info()  # noqa
                except Exception:
                    continue
                result_dict[id_[0]][str(k)] = {}
                for ep in season_info['episodes']:
                    try:
                        name = ep['name']
                    except KeyError:
                        name = None
                    result_dict[id_[0]][str(k)][str(ep['episode_number'])] = {
                        'title': name,
                        'thumbnail': f"https://image.tmdb.org/t/p/original{ep['still_path']}"  # noqa
                        if ep['still_path'] is not None else None
                    }
    headers = ['SlNo', "Title", "Total Seasons", 'id']
    table = tabulate(table_list, headers, tablefmt='psql')
    table = '\n'.join(table.split('\n')[::-1])
    return table, result_dict


cache_tmdb_requests = {}


def search_tmdb_id(tmdb_id, ismovie):
    if type(ismovie) is str:
        ismovie = True if ismovie.upper() == 'MOVIE' else False
    if '{}_{}'.format(tmdb_id, 'MOVIE' if ismovie else 'TV') not in cache_tmdb_requests:
        tmdb_id = int(tmdb_id)
        tmdbId = tmdb.Movies if ismovie else tmdb.TV
        info = tmdbId(tmdb_id).info() if ismovie else tmdbId(tmdb_id).info()
        result_dict = {}
        result_dict['title'] = info['title' if ismovie else 'name']
        if ismovie:
            result_dict['1'] = {}
            result_dict['1']['1'] = {'title': info['title'], 'thumbnail': f"https://image.tmdb.org/t/p/original{info['poster_path']}"}
        else:
            total_seasons = int(info['number_of_seasons']) + 1
            for k in range(total_seasons):
                try:
                    season_info = tmdb.TV_Seasons(int(tmdb_id), season_number=k).info()  # noqa
                except Exception:
                    continue
                result_dict[str(k)] = {}
                for ep in season_info['episodes']:
                    try:
                        name = ep['name']
                    except KeyError:
                        name = None
                    result_dict[str(k)][str(ep['episode_number'])] = {
                        'title': name,
                        'thumbnail': f"https://image.tmdb.org/t/p/original{ep['still_path']}"  # noqa
                        if ep['still_path'] is not None else None
                    }
            cache_tmdb_requests['{}_{}'.format(
                tmdb_id,
                'MOVIE' if ismovie else 'TV')
            ] = copy.deepcopy(result_dict)
    else:
        result_dict = cache_tmdb_requests[
            '{}_{}'.format(
                tmdb_id,
                'MOVIE' if ismovie else 'TV'
            )
        ]
    return result_dict


def search_anilist(search, max_results=50):
    query = """
    query($id:Int,$page:Int,$search:String,$type:MediaType){
        Page(page:$page,perPage:50){
            media(id:$id,search:$search,type:$type){
                id
                title {
                    english
                    romaji
                }
                format
            }
        }
    }
    """
    variables = {
        'search': search,
        'page': 1,
        'perPage': max_results,
        'type': 'ANIME'
    }
    url = 'https://graphql.anilist.co'

    results = requests.post(
        url, json={'query': query, 'variables': variables}).json()

    result_list = results['data']['Page']['media']
    final_result = []
    result = []
    count = 0

    for anime in result_list:
        jp_title = anime['title']['romaji']
        ani_id = anime['id']
        _type = anime['format']

        entry = [count, jp_title, _type, ani_id]
        final_result.append(entry)
        count += 1

    headers = ['SlNo', "Title", 'format', "id"]
    table = tabulate(final_result, headers, tablefmt='psql')
    table = '\n'.join(table.split('\n')[::-1])
    return table, final_result


def search_anilist_id(item_id):
    query_string = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                title {
                    romaji
                    english
                }
                format
            }
        }
    """
    _vars = {"id": item_id}
    url = 'https://graphql.anilist.co'
    r = requests.post(url, json={'query': query_string, 'variables': _vars})
    jsd = r.text
    try:
        jsd = json.loads(jsd)
    except ValueError:
        return None
    else:
        return jsd


def extract_info(filename, directory):
    if not options.useRegex:
        try:
            title = filename.split(' ')
            misc = title.pop(-1).split('.')[0].strip()
            season_num, episode_num = misc[1:].split('E')

            title = ' '.join(title)
            ep = {
                'ep': episode_num,
                'file': os.path.abspath(os.path.join(directory.replace('\\', '/'), filename)).replace('\\', '/'),
                'directory': os.path.abspath(directory).replace('\\', '/')
            }
        except IndexError:
            return
    else:
        try:
            groups = re.search("\s+[Ss](\d+)[Ee](\d+)\.",
                               filename.replace('\\', '/')).groups()
        except Exception:
            return

        title = ' '.join(filename.split(' ')[:-1])
        season_num = groups[0]
        ep = {
            'ep': groups[1],
            'file': os.path.abspath(os.path.join(directory.replace('\\', '/'), filename)).replace('\\', '/'),
            'directory': os.path.abspath(directory).replace('\\', '/')
        }
    return title, season_num, ep


default_config = options.jsonConfig


def write_to_config(data, config=default_config):
    with open(config, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)


def read_config(config=default_config):
    if not os.path.isfile(default_config):
        write_to_config({"Known-Anime": {}})
    with open(config, 'r') as f:
        return json.load(f)


def save_to_json(data, path=options.jsonPath):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


pretty_print = []
updated_config = {}


def add_json(files, dictionary):
    thumbnails_dict = {}

    for file in files:
        info = extract_info(file[0], file[1])

        if info is None:
            continue

        title, season, ep = info
        identifier = title + '.' + str(season)

        if title not in pretty_print:
            print('Parsing: {}'.format(title.strip()))
            pretty_print.append(title)

        ep['season_num'] = season
        id_to_anime = read_config()

        try:
            anime = id_to_anime["Known-Anime"][identifier]

            anilist_id = anime['ani_id']
            _type = anime['format']
            tmdb_dict = anime['tmdb_dict']
            tmdb_id = anime['tmdb_id']
            pretty_title = anime['pretty_title']

            if 'last_modified' not in id_to_anime["Known-Anime"][identifier]:
                anime['last_modified'] = time.time()
                write_to_config(id_to_anime)

            last_modified = anime['last_modified']

            if last_modified - time.time() <= -options.TMDB_METADATA_UPDATE_INTERVAL:  # noqa
                uniqueId = str(anilist_id) + str(season) + str(tmdb_id)

                if uniqueId not in updated_config:
                    updated_config[uniqueId] = time.time()
                    print('Fetching new metadata for {} from theMovieDB.'.format(pretty_title))  # noqa
                    anime_info = search_tmdb_id(tmdb_id.split('_')[0], _type)

                    if str(int(season)) in anime_info:
                        tmdb_dict = {str(int(season)): anime_info[str(int(season))]}  # noqa
                    else:
                        tmdb_dict = anime_info

                    anime['tmdb_dict'] = tmdb_dict
                    anime['last_modified'] = time.time()

                write_to_config(id_to_anime)

        except KeyError:
            table1, anilist_data = search_anilist(title)

            print(f'Anilist results for: {title} Season: {season}')
            print(table1)
            num = input("Select number: [0]: ")

            try:
                if 'e' in num:
                    value_bool = True
                else:
                    value_bool = False
                num = int(num.replace('e', '') if value_bool else num)
            except ValueError:
                num = 0

            if num <= 50 and not value_bool:
                choice = anilist_data[num]
                anilist_id = str(choice[-1])
                _type = str(choice[-2])
            else:
                anilist_id = num
                anilist_dat = search_anilist_id(anilist_id)
                _type = anilist_dat['data']['Media']['format']

            table2, tmdb_dict = search_tmdb(title, _type)
            print('\n')
            ids = [x for x, i in tmdb_dict.items()]
            print(f'theMovieDB results for: {title}.')
            print(table2)
            num1 = input("Select number: [0]: ")
            print('\n----------------------------------------\n')
            try:
                if 'm' in num1:
                    _type = 'MOVIE'
                    num1 = int(num1.replace('m', ''))
                elif 't' in num1:
                    _type = 'TV'
                    num1 = int(num1.replace('t', ''))
                else:
                    num1 = int(num1)
            except ValueError:
                num1 = 0

            if num1 > 20:
                tmdb_dict = search_tmdb_id(num1, _type)
                tmdb_id = f'{num1}_{_type}'
            else:
                tmdb_dict = tmdb_dict[ids[num1]]
                tmdb_id = ids[num1]

            pretty_title = tmdb_dict['title']

            id_to_anime["Known-Anime"][identifier] = {}
            anime = id_to_anime["Known-Anime"][identifier]
            anime['last_modified'] = time.time()
            anime['ani_id'] = anilist_id
            anime['tmdb_id'] = tmdb_id
            anime['format'] = _type

            if str(int(season)) in tmdb_dict:
                tmdb_dict = {str(int(season)): tmdb_dict[str(int(season))]}

            anime['tmdb_dict'] = tmdb_dict
            id_to_anime['Known-Anime'][identifier]['pretty_title'] = pretty_title  # noqa
            write_to_config(id_to_anime)

        if anilist_id not in dictionary:
            dictionary[anilist_id] = {}
        if 'Seasons' not in dictionary[anilist_id]:
            dictionary[anilist_id]['Seasons'] = {}
        if season not in dictionary[anilist_id]['Seasons']:
            dictionary[anilist_id]['Seasons'][season] = {}
        if 'Episodes' not in dictionary[anilist_id]['Seasons'][season]:
            dictionary[anilist_id]['Seasons'][season]['Episodes'] = []

        for key, value in tmdb_dict.items():
            if key == 'title':
                continue

            if int(season) == int(key):
                if int(ep['ep']) in [
                    int(x)
                    for x, y in tmdb_dict[key].items()
                ]:
                    dat = value[str(int(ep['ep']))]
                    ep['title'] = dat['title']

        dictionary[anilist_id]['Seasons'][season]['Episodes'].append(ep)
        dictionary[anilist_id]['Seasons'][season]['pretty_title'] = pretty_title  # noqa


def conv_list(data):
    for anime in data:
        seasons = data[anime]['Seasons']
        seasons = [seasons[x] for x in sorted(seasons, key=lambda x: int(x))]
        data[anime]['Seasons'] = seasons


if __name__ == '__main__':
    dictionary = {}

    if options.FULL_SCAN:
        files_list = []

    for directory, __, files in os.walk(options.SCAN_DIR, topdown=True):
        for file in files:
            if file.endswith(options.fileFormat):
                if options.FULL_SCAN:
                    files_list.append([file, directory])
                else:
                    add_json([[file, directory]], dictionary)

    if options.FULL_SCAN:
        add_json(files_list, dictionary)
    conv_list(dictionary)
    save_to_json(dictionary)
