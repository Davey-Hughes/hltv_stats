# Common functions for the HLTV scraper and plotter
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

import psycopg2


def connect_to_db(args):
    # try without supplying password
    try:
        conn = psycopg2.connect('dbname=%s user=%s' %
                                (args.dbname, args.role,))
        return conn
    except psycopg2.OperationalError as e:
        if 'no password supplied' not in str(e):
            raise

    # try again asking for password
    try:
        conn = psycopg2.connect('dbname=%s user=%s password=%s' %
                                (args.dbname, args.role,
                                 getpass.getpass(prompt='DB Password: ')))
        return conn
    except (NameError, psycopg2.OperationalError):
        raise
