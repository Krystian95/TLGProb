import mysql.connector
from datetime import datetime


class CustomUtils:
    database = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="progetto_ai",
        auth_plugin='mysql_native_password'
    )
    teams_compositions = []

    player_informations = []
    player_names_ordered_by_height = []

    def __init__(self, player_dict):
        # dict_keys(['name', 'from', 'to', 'position', 'height', 'weight', 'birthday', 'url'])

        for i in range(0, len(player_dict["name"])):
            self.player_informations.append(
                (player_dict["name"][i], player_dict["position"][i], player_dict["height"][i]))

        self.player_informations = sorted(self.player_informations, key=lambda x: x[2], reverse=True)
        self.player_names_ordered_by_height = [player for player, position, height in self.player_informations]

    # Rimappa le posizioni dei giocatori, lasciandole inalterate se esiste almeno un giocatore per ogni ruolo.
    # Nel caso in cui ci siano 0 giocatori nel ruolo C, preleva un giocatore in forward (F) con l'altezza più
    # alta e lo sposta (temporaneamente per la gara) nel ruolo C
    def remapping_player_positions(self, match_players, player_to_position_all_players, team, year, month, day):
        position_to_player = {"F": [], "G": [], "C": []}
        player_to_position = {}

        for player in match_players:
            pos = player_to_position_all_players[player]
            position_to_player[pos].append(player)

        if len(position_to_player["C"]) == 0:
            forwards = position_to_player["F"]
            forwards_ordered_by_height = list(set(self.player_names_ordered_by_height) & set(forwards))
            new_center = forwards_ordered_by_height[0]
            # print(player_positions)
            position_to_player["F"].remove(new_center)
            position_to_player["C"].append(new_center)
            # print(player_positions)
            print("(!) Detected no Centers for", team, "on", year, month, day, ": " + new_center,
                  "was temporarily moved from F to C")

        for position in position_to_player:
            # print(position)
            for i in range(0, len(position_to_player[position])):
                player_to_position[position_to_player[position][i]] = position
                # print(position_to_player[position][i])

        return player_to_position

    def save_team_composition(self, year, month, day, team, player, pos, iteration_timestamp, match):
        tuple = (iteration_timestamp, match, str(year) + "-" + str(month) + "-" + str(day), team, player, pos)
        self.teams_compositions.append(tuple) if tuple not in self.teams_compositions else self.teams_compositions
        #print(self.teams_compositions)

    def insert_teams_compositions_to_db(self):
        cursor = self.database.cursor()
        query = """
                INSERT INTO team_composition (
                    generated_timestamp,
                    match_description,
                    match_date,
                    team,
                    player,
                    position
                ) VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.executemany(query, self.teams_compositions)
        self.database.commit()
