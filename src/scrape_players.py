# Scrape players from the HLTV world rankings
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

import threading
import multiprocessing
import subprocess
import queue
import argparse

from bs4 import BeautifulSoup
import psycopg2

players = dict()
players_lock = threading.Lock()

teams_queue = queue.Queue()

args = []


def thread_work():
    while True:
        team = teams_queue.get()

        if team is None:
            break

        team_soup = get_page_soup(team)
        players_soup = process_team_page(team_soup)
        process_players_page(players_soup, team[1])

        teams_queue.task_done()


def process_players_page(soup, team):
    players_lock.acquire()
    for player in soup:
        name = player['title']
        href = player['href']
        hltv_id = href.split('/')[2]

        print('Processing data for %s' % (name))

        if name not in players:
            players[name] = dict()
            players[name]['hltv_id'] = hltv_id
            players[name]['team'] = team
    players_lock.release()


def process_team_page(soup):
    team_links = soup.find(class_='bodyshot-team')
    players = team_links.findAll('a', href=True)

    return players


def get_page_soup(team):
    print('Getting data for %s' % (team[1]))

    url = 'https://www.hltv.org/team/' + str(team[0]) + '/' +\
        str(team[1].replace(' ', '-').replace('?', '-'))
    print(url)
    p = subprocess.run(['curl', url],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)

    page = p.stdout
    soup = BeautifulSoup(page, 'html.parser')

    return soup


def create_tables(cur):
    cur.execute('SELECT to_regclass(%s)', ('public.players',))
    if cur.fetchone() != ('players',):
        cur.execute(
            'CREATE TABLE players (\
                hltv_id bigint PRIMARY KEY,\
                name varchar,\
                team varchar\
            )'
        )


def insert_data(cur, players):
    for player in players:
        row = players[player]

        if args.force_update:
            cur.execute(
                'INSERT INTO public.players VALUES (%s, %s, %s) \
                    ON CONFLICT (hltv_id) DO UPDATE \
                    SET hltv_id = excluded.hltv_id,\
                        name = excluded.name,\
                        team = excluded.team',
                (row['hltv_id'], player, row['team'])
            )
        else:
            cur.execute(
                'INSERT INTO public.players VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                (row['hltv_id'], player, row['team'])
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

    try:
        conn = psycopg2.connect('dbname=%s user=%s' % (args.dbname, args.role))
    except (NameError, psycopg2.OperationalError):
        print('Make sure input database and role exist!\n')
        raise

    cur = conn.cursor()

    create_tables(cur)
    conn.commit()

    cur.execute('SELECT * FROM teams')
    teams = cur.fetchall()

    for team in teams:
        teams_queue.put(team)

    num_threads = multiprocessing.cpu_count()
    threads = []

    # launch threads
    for i in range(num_threads):
        thread = threading.Thread(target=thread_work)
        thread.start()
        threads.append(thread)

    # wait for all the dates to be processed
    teams_queue.join()

    # tell threads to exit
    for i in range(num_threads):
        teams_queue.put(None)

    # wait for threads to finish
    for t in threads:
        t.join()

    insert_data(cur, players)

    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
