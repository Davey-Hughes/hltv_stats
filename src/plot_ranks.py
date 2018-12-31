# Plots the HLTV team rankings over time
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
import argparse
import collections

import plotly as py
import plotly.graph_objs as go
from plotly.offline import plot
import common


# globals
args = []

plot_path = common.ROOT_DIR + '/plots/'


# make plotly html files from the rankings
def plot_teams(cur):
    # get list of all unique dates
    cur.execute('SELECT DISTINCT date FROM ranks ORDER BY date')
    all_dates = [date for date, in cur.fetchall()]

    # get ordered list of teams from the most recent ranking
    cur.execute('SELECT * FROM ranks WHERE date=(%s) ORDER BY rank', (all_dates[-1],))
    teams_recent_ranking = [team for _, team, _, _ in cur.fetchall()]

    # get list of all teams except those from recent ranking
    cur.execute('SELECT * FROM teams')
    teams_except_recent = \
        set([name for _, name, _ in cur.fetchall()]) - set(teams_recent_ranking)

    teams = teams_recent_ranking + sorted(teams_except_recent, key=lambda s: s.casefold())

    data_ranks = []
    data_points = []

    for i, team in enumerate(teams):
        cur.execute('SELECT * FROM ranks WHERE team=(%s) ORDER BY date', (team,))
        records = cur.fetchall()

        cur.execute('SELECT color FROM teams WHERE team=(%s)', (team,))
        team_color = cur.fetchone()
        if team_color is not None:
            team_color = team_color[0]

        # for both ranks and points plots, any dates missing for a team are
        # marked as None so that gaps show up in the graph
        #
        # the OrderedDict is important for making sure the x and y values in
        # the plot are ordered by date
        if args.by_rank:
            ranks = {date: rank for date, _, rank, _ in records}

            first_date = min(ranks)
            last_date = max(ranks)

            for date in all_dates:
                if date not in ranks:
                    ranks[date] = None

            ranks = collections.OrderedDict(sorted(ranks.items()))

            xs = [date for date in ranks]
            ys = [ranks[date] for date in ranks]

            team_plot = go.Scatter(
                x=xs,
                y=ys,
                name=team + ' (' + str(i + 1) + ')' if i < 30 else team,
                connectgaps=False,
                line=dict(
                    color=team_color
                )
            )

            data_ranks.append(team_plot)

        if args.by_points:
            points = {date: point for date, _, _, point in records}

            for date in all_dates:
                if date not in points:
                    points[date] = None

            points = collections.OrderedDict(sorted(points.items()))

            xs = [date for date in points]
            ys = [points[date] for date in points]

            team_plot = go.Scatter(
                x=xs,
                y=ys,
                name=team + ' (' + str(i + 1) + ')' if i < 30 else team,
                connectgaps=False,
                line=dict(
                    color=team_color
                )
            )

            data_points.append(team_plot)

    if args.by_rank:
        # manually sets the range so rank 1 is at the top
        # ticks start at 1 and go by 5s
        layout = go.Layout(
            yaxis=dict(
                range=[31, 1],
                tickvals=list(range(1, 30, 5)),
                zeroline=False
            )
        )

        fig = go.Figure(data=data_ranks, layout=layout)
        plot(fig, filename=plot_path + 'ranks.html')

    if args.by_points:
        layout = go.Layout()

        fig = go.Figure(data=data_points, layout=layout)
        plot(fig, filename=plot_path + 'points.html')


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dbname', help='name of the database to connect to')
    parser.add_argument('--role', help='role to access this database with')

    parser.add_argument(
        '--by_points',
        help='create a plot using the HLTV points',
        action='store_true',
        default=False
    )

    parser.add_argument(
        '--by_rank',
        help='create a plot using the HLTV rank',
        action='store_true',
        default=False
    )

    global args
    args = parser.parse_args()


def main():
    parse_arguments()

    # if neither plot by points or rank is set, only set plot by rank
    if not args.by_rank and not args.by_points:
        args.by_rank = True

    conn = common.connect_to_db(args)

    cur = conn.cursor()

    if not os.path.exists(plot_path):
        os.mkdir(plot_path)

    plot_teams(cur)

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
