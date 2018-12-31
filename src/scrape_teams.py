# Scrape teams from the HLTV world rankings
# Copyright (C) 2018  David Hughes

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import threading
import multiprocessing
import subprocess
import queue
import datetime
import argparse
import math

from bs4 import BeautifulSoup
import common


# globals
logos_path = common.ROOT_DIR + '/logos/'

base_url = 'https://www.hltv.org/ranking/teams/'
dates = []

teams = dict()
team_colors = dict()
teams_lock = threading.Lock()

dates_queue = queue.Queue()

args = None

# human readable mapping from aligned dates to actual dates in hltv
dates_map = {
    '2015-09-28': '2015-10-01',
    '2015-11-02': '2015-11-03',
    '2015-11-23': '2015-11-24',
    '2015-11-30': '2015-12-01',
    '2015-12-07': '2015-12-08',
    '2016-01-04': '2016-01-05',
    '2016-02-08': '2016-02-09',
    '2016-02-29': '2016-03-01',
    '2016-04-04': '2016-04-05',
    '2016-04-17': '2016-04-18',
    '2016-05-16': '2016-05-17',
    '2016-05-30': '2016-06-01',
    '2016-06-20': '2016-06-21',
    '2016-07-18': '2016-07-19',
    '2016-07-25': '2016-07-26',
    '2016-10-31': '2016-11-01',
    '2018-01-15': '2018-01-16',
    '2018-01-22': '2018-01-23',
}

# mapping in the datetime format
fix_dates = {
        datetime.datetime.fromisoformat(k):
        datetime.datetime.fromisoformat(dates_map[k])
        for k in dates_map
}


def thread_work():
    while True:
        date = dates_queue.get()

        if date is None:
            break

        soup = get_page_soup(date)
        process_page(date, soup)

        dates_queue.task_done()


def dominant_color_url(url):
    num_colors = 5

    if not os.path.exists(logos_path):
        os.makedirs(logos_path)

    filepath = logos_path + 'temp.svg'

    subprocess.run(['wget', url, '-O', filepath],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

    info = subprocess.run([
            'convert', filepath, '+dither', '-colors', str(num_colors),
            '-format', '%c', '-depth', '8', 'histogram:info:',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)

    colors = []

    for line in info.stdout.split(b'\n'):
        lst = line.decode('utf-8').strip().split(': ')
        if lst != ['']:
            colors.append(lst)

    colors = list(filter(lambda x: x[1].split(' ')[-1] != 'white', colors))

    color_ranks = [int(x[0]) for x in colors]
    total_pixels = sum(color_ranks)

    # filter out any colors that appear less than 5% of the time
    colors = list(filter(lambda x: int(x[0]) > total_pixels * 0.05, colors))

    # extract RGB values from hex color string
    hex_colors = [color[1].split(' ')[-2][1:-2] for color in colors]
    split_hex_colors = [[int(c[i:i + 2], 16) for i in range(0, 6, 2)] for c in hex_colors]

    dist_mins = []
    # find minimum of distances to black and white for each color
    for color in split_hex_colors:
        bdist = math.sqrt(color[0] ** 2 + color[1] ** 2 + color[2] ** 2)
        wdist = math.sqrt((255 - color[0]) ** 2 + (255 - color[1]) ** 2 + (255 - color[2]) ** 2)

        if wdist < 60:
            dist_mins.append(0)
        else:
            dist_mins.append(min(bdist, wdist))

    index_max = max(range(len(dist_mins)), key=dist_mins.__getitem__)

    return '#' + hex_colors[index_max]


# parse page for team name, rank, and points
def process_page(date, soup):
    teams_div = soup.select('div.ranked-team.standard-box')

    for team in teams_div:
        name = team.find(class_='name').text
        rank = int(team.find(class_='position').text.strip('#'))
        points = int(team.find(class_='points').text.strip('()').split(' ')[0])
        href = team.find(
            attrs={
                'data-link-tracking-destination': 'Click on HLTV Team profile [button]'
            }
        )['href']

        hltv_id = href.split('/')[2]

        logo_url = team.find(class_='team-logo').find('img')['src']

        teams_lock.acquire()
        if name not in teams:
            teams[name] = dict()

        teams[name][date] = {
            'rank': rank,
            'points': points,
            'href': href
        }
        teams[name]['logo_url'] = logo_url
        teams[name]['hltv_id'] = hltv_id
        teams_lock.release()


# fetch page source for a given date
def get_page_soup(date):
    print('Getting data for %s-%s-%s' % (date.year, date.month, date.day))
    url = base_url + str(date.year) + '/' + date.strftime("%B").lower() + '/' + str(date.day)

    p = subprocess.run(['curl', url],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)

    page = p.stdout
    soup = BeautifulSoup(page, 'html.parser')

    return soup


def create_tables(cur):
    # create ranks table if not exists
    cur.execute('SELECT to_regclass(%s)', ('public.ranks',))
    if cur.fetchone() != ('ranks',):
        cur.execute(
            'CREATE TABLE ranks (\
                date date,\
                team varchar,\
                rank int,\
                points int,\
                PRIMARY KEY(date, team)\
            )'
        )

    # create teams table if not exists
    cur.execute('SELECT to_regclass(%s)', ('public.teams',))
    if cur.fetchone() != ('teams',):
        cur.execute(
            'CREATE TABLE teams (\
                hltv_id integer PRIMARY KEY,\
                team varchar,\
                color varchar\
            )'
        )


def insert_data(cur, teams):
    for team in teams:
        if args.force_update:
            cur.execute(
                'INSERT INTO public.teams VALUES (%s, %s, %s) \
                        ON CONFLICT (hltv_id) DO UPDATE \
                    SET hltv_id = excluded.hltv_id,\
                        team = excluded.team,\
                        color = excluded.color',
                (teams[team]['hltv_id'], team, teams[team]['color'])
            )
        else:
            cur.execute(
                'INSERT INTO public.teams VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                (teams[team]['hltv_id'], team, teams[team]['color'])
            )

        for date in teams[team]:
            if type(date) != datetime.date:
                continue

            row = teams[team][date]

            if args.force_update:
                cur.execute(
                    'INSERT INTO public.ranks VALUES (%s, %s, %s, %s) \
                        ON CONFLICT (date, team) DO UPDATE \
                        SET date = excluded.date,\
                            team = excluded.team,\
                            rank = excluded.rank,\
                            points = excluded.points',
                    (date.isoformat(), team, row['rank'], row['points'])
                )

            else:
                cur.execute(
                    'INSERT INTO public.ranks VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                    (date.isoformat(), team, row['rank'], row['points'])
                )


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dbname', help='name of the database to connect to')
    parser.add_argument('--role', help='role to access this database with')

    parser.add_argument(
        '--update-all',
        help='do not try to skip data that is already in the database',
        action='store_true',
        default=False
    )

    parser.add_argument(
        '--force-update',
        help='use scraped data for any conflicts in database',
        action='store_true',
        default=False
    )

    global args
    args = parser.parse_args()


def main():
    parse_arguments()

    conn = common.connect_to_db(args)

    cur = conn.cursor()

    create_tables(cur)
    conn.commit()

    prev = datetime.date.fromisoformat('2015-09-28')
    end = datetime.date.today()

    # generate all dates
    while (prev <= end):
        adjust_date = prev
        if prev in fix_dates:
            adjust_date = fix_dates[prev]

        dates.append(adjust_date)

        week_after = prev + datetime.timedelta(days=7)
        prev = week_after

    cur.execute('SELECT MAX(date) FROM ranks')
    latest = cur.fetchone()[0]

    if not args.update_all and latest is not None:
        index = dates.index(latest) + 1
    else:
        index = 0

    # i = 0
    # index = 60
    for date in dates[index:]:
        # if i > 10:
            # break
        dates_queue.put(date)
        # i += 1

    num_threads = multiprocessing.cpu_count()
    threads = []

    # launch threads
    for i in range(num_threads):
        thread = threading.Thread(target=thread_work)
        thread.start()
        threads.append(thread)

    # wait for all the dates to be processed
    dates_queue.join()

    # tell threads to exit
    for i in range(num_threads):
        dates_queue.put(None)

    # wait for threads to finish
    for t in threads:
        t.join()

    # get team colors
    for team in teams:
        print('Getting color for %s' % (team))
        color = dominant_color_url(teams[team]['logo_url'])
        teams[team]['color'] = color

    # remove logos folder
    if os.path.exists(logos_path):
        shutil.rmtree(logos_path)

    insert_data(cur, teams)

    conn.commit()
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
