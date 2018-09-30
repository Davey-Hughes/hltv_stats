# Scrape all teams from the HLTV world rankings
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

import sys
import threading
import multiprocessing
import subprocess
import queue
import datetime
import re

from bs4 import BeautifulSoup
import psycopg2

# globals
base_url = 'https://www.hltv.org/ranking/teams/'
dates = []

teams = dict()
teams_lock = threading.Lock()

dates_queue = queue.Queue()

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


# parse page for team name, rank, and points
def process_page(date, soup):
    teams_div = soup.select('div.ranked-team.standard-box')

    teams_lock.acquire()
    for team in teams_div:
        name = team.find(class_='name').text
        rank = int(team.find(class_='position').text.strip('#'))
        points = int(team.find(class_='points').text.strip('()').split(' ')[0])
        href = team.find(
            attrs={
                'data-link-tracking-destination': 'Click on HLTV Team profile [button]'
            }
        )['href']

        team_id = href.split('/')[2]

        if name not in teams:
            teams[name] = dict()

        teams[name][date] = {
            'rank': rank,
            'points': points,
            'href': href,
            'team_id': team_id
        }

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
    cur.execute('SELECT to_regclass(%s)', ('public.ranks',))
    if cur.fetchone() != ('ranks',):
        cur.execute('CREATE TABLE ranks (date date, team varchar, rank int, points int, PRIMARY KEY(date, team))')


def insert_ranks(cur, teams):
    for team in teams:
        for date in teams[team]:
            row = teams[team][date]
            cur.execute(
                'INSERT INTO public.ranks VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                (date.isoformat(), team, row['rank'], row['points'],)
            )


def main():
    if len(sys.argv) != 3:
        print('Must include dbname and role as arguments')

    dbname = sys.argv[1]
    role = sys.argv[2]

    try:
        conn = psycopg2.connect('dbname=%s user=%s' % (dbname, role))
    except psycopg2.OperationalError:
        print('Make sure input database and role exist!\n')
        raise

    cur = conn.cursor()

    create_tables(cur)

    num_threads = multiprocessing.cpu_count()
    threads = []

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

    if latest is not None:
        index = dates.index(latest) + 1
    else:
        index = 0

    for date in dates[index:]:
        dates_queue.put(date)

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

    insert_ranks(cur, teams)

    conn.commit()
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
