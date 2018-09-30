# Initializes a postgres database to prepare for hltv scraping
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

import psycopg2


def main():
    if len(sys.argv) != 3:
        print('argv must have dbname and role')
        return

    dbname = sys.argv[1]
    role = sys.argv[2]

    try:
        conn = psycopg2.connect('dbname=%s user=%s' % (dbname, role))
    except psycopg2.OperationalError:
        print('Make sure input database and role exist!\n')
        raise

    cur = conn.cursor()

    # create schemas

    # commit changes
    conn.commit()

    # close connection
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
