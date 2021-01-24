import mysql.connector
import pandas as pd

from LegaPallacanestro.SinglePlayers import SinglePlayers

pd.set_option('display.max_rows', 50000)
pd.set_option('display.max_columns', 50)
pd.set_option('display.width', 1000)

database = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="progetto_ai",
    auth_plugin='mysql_native_password'
)

single_players = SinglePlayers(database)
single_players.generate_csv(
    folder_path="/Applications/XAMPP/xamppfiles/htdocs/TLGProb/experiment-fip-2019-2020/database/19-20",
    stagione_sportiva="2019/2020")
