from datetime import datetime
import csv
import shutil
import os


class SinglePlayers:
    database = None

    def __init__(self, database):
        self.database = database

    def days_between(self, d1, d2):
        d1 = datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.strptime(d2, "%Y-%m-%d")
        return abs((d2 - d1).days)

    def format_file_name(self, string):
        return string.replace(" ", "_")

    def get_players(self, stagione_sportiva=None, giornate=None):
        cursor = self.database.cursor(dictionary=True)
        query = '''
            SELECT 
                `player`,
                `date`,
                `team`,
                `opp`,
                `date_birth`,
                `gs`,
                `mp`,
                `fg`,
                `fga`,
                `fg%`,
                `3p`,
                `3pa`,
                `3p%`,
                `ft`,
                `fta`,
                `ft%`,
                `orb`,
                `drb`,
                `trb`,
                `ast`,
                `stl`,
                `blk`,
                `tov`,
                `pf`,
                `pts`,
                `+/-`
        FROM `tlgprob_single_players`
        WHERE StagioneSportiva = \'''' + stagione_sportiva + '''\'
        '''

        if giornate is not None:
            query += ''' AND Giornata IN (''' + giornate + ''')'''

        cursor.execute(query)
        players = cursor.fetchall()
        return players

    def generate_csv(self, folder_path, stagione_sportiva, giornate=None):

        print("Inizio scrittura file CSV giocatori", stagione_sportiva, "...")

        headers = ['date', 'team', 'opp', 'age', 'gs', 'mp', 'fg', 'fga', 'fg%', '3p', '3pa', '3p%', 'ft', 'fta', 'ft%',
                   'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts', 'gmsc', '+/-']

        age_by_year_day = 1 / 365
        players_csv = {}

        players = self.get_players(stagione_sportiva=stagione_sportiva, giornate=giornate)

        for player in players:
            if player["player"] not in players_csv:
                players_csv[player["player"]] = []

            player["date_birth"] = str(player["date_birth"])
            player["date"] = str(player["date"])

            diff_days = self.days_between(player["date_birth"], player["date"])
            # print(str(player["date_birth"]) + " - " + str(player["date"]) + " = " + str(diff_days))
            age_at_1st_feb = str(diff_days * age_by_year_day)

            gmsc = player["pts"] + 0.4 * player["fg"] - 0.7 * player["fga"] - 0.4 * (
                        player["fta"] - player["ft"]) + 0.7 * \
                   player["orb"] + 0.3 * player["drb"] + player["stl"] + 0.7 * player["ast"] + 0.7 * player[
                       "blk"] - 0.4 * \
                   player["pf"] - player["tov"]

            # Must follow the order of "headers"
            players_csv[player["player"]].append([
                player["date"],
                player["team"],
                player["opp"],
                age_at_1st_feb,
                player["gs"],
                player["mp"],
                player["fg"],
                player["fga"],
                player["fg%"],
                player["3p"],
                player["3pa"],
                player["3p%"],
                player["ft"],
                player["fta"],
                player["ft%"],
                player["orb"],
                player["drb"],
                player["trb"],
                player["ast"],
                player["stl"],
                player["blk"],
                player["tov"],
                player["pf"],
                player["pts"],
                gmsc,
                player["+/-"]
            ])

        # Create CSV files
        shutil.rmtree(folder_path, ignore_errors=True)
        os.mkdir(folder_path)

        print("Sto scrivendo in", folder_path)

        for player_name, player_matches in players_csv.items():
            # print(player_name)
            file_name = self.format_file_name(player_name)
            with open(folder_path + '/' + file_name + '.csv', 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
                for i in range(len(player_matches)):
                    # print(player_matches[i])
                    writer.writerow(player_matches[i])

        print("Scrittura file CSV giocatori", stagione_sportiva, "completata!\n")
