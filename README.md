# HLTV World Rankings Plotter

<img src="https://media.githubusercontent.com/media/Davey-Hughes/hltv_stats/master/img/points.png" width="1000"/>

## Usage
### Viewing the Plots
The interactive plots can be downloaded and then run locally on your browser,
or using [this html preview site](https://htmlpreview.github.io/). You must
specify the raw file url (a https://media.githubusercontent.com/ url) for the
html preview site to show the content.

### Running the Code
Before running any of the files in this project, you must setup a postgres
cluster on your machine. You should create the database for this HLTV data, and
then the database name and role are passed in as command-line arguments. If
your database requires a password, when the script is run a secure password
prompt will be shown courtesy of getpass.

```
python3 src/scrape_teams.py --dbname=dbname --role=role
```
will scrape the world rankings data from HLTV and store the output in the
database specified by dbname. The arguments `--update-all` and `--force-update`
also can be specified. Without `--update-all`, the script will look at the
database and only scrape dates past the latest date in the database.
`--force-update` will replace any conflicting rows with the newly scraped
data- the default is to preserve the database information.

```
python3 src/scrape_players.py --dbname=dbname --role=role
```
will get a list of all teams stored in the database and insert into the
database the current player information for those teams. Currently there is no
other functionality in this repository that uses the player information, only
database storage.

```
python3 src/plot_ranks.py --dbname=dbname --role=role
```
will produce a plotly plot of the information in the database specified.
Currently this script can create two plots: one of the HLTV ranks by rank, and
one of the HLTV ranks by the points HLTV uses to actually calculate the
rankings. Two other arguments can be specified for this script: `--by_rank` and
`--by_points`. These flags specify which plots to create (both can be created
at the same time). If neither are specified, `--by_rank` is turned on by
default.

These plots are saved in the `project_root/plots/ranks.html` and
`project_root/plots/points.html` and _will_ overwrite any files of the same name
without asking first.

## Dependencies
`psycopg2` is used to communicate with a postgres database and can be installed
with pip

`Beautiful Soup` is used to parse the scraped HTML information and can be
installed with pip

`imagemagick` command line tools are used. On MacOS they can be installed with
homebrew:

```
brew install imagemagick
```

Other platforms can install imagemagick similarly with their respective package
managers.

## Limitations
### Team Continuity
Often is the case in Counter Strike where the core (or entirety) of a team
changes their team name or moves to a different organization. It would be
reasonable, then, for the lines from these two teams to be connected, however
currently this is not the case. A mapping from a previous team name to the
current team name could be constructed manually, as would be the case for TSM
-> ? -> Astralis, however since in many cases it is important to know the date
the team members changed (LG -> SK -> MiBR), this would also have to be taken
into account.

With the interactive plotly plots, it is possible to select a single team's
line to show by double-clicking on the team name in the legend. From there,
other teams' lines can be made visible by single-clicking on their name in the
legend.

## Data Display
The colors for the lines are decided by analyzing the team's logo from HLTV and
determining a non-white dominant color. For all the current teams, the
implementation seems to find a good color for the team, however there may be
some mistakes. Additionally, new team logos may be created in the future that
show edge-cases with the dominant color picking logic.

## Future
In addition to the world rankings, this project could be expanded to scrape and
analyze other information on HLTV. There are no explicit plans currently in
mind, but requests are welcome.
