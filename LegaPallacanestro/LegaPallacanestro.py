import os
import shutil

import mysql.connector
import numpy as np
import pandas as pd
from SinglePlayers import SinglePlayers
from TLGProb import TLGProb

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

giornate = ['1° Giornata', '2° Giornata', '3° Giornata', '4° Giornata', '5° Giornata', '6° Giornata', '7° Giornata',
            '8° Giornata', '9° Giornata', '10° Giornata', '11° Giornata', '12° Giornata', '13° Giornata',
            '14° Giornata', '15° Giornata', '16° Giornata', '17° Giornata', '18° Giornata', '19° Giornata',
            '20° Giornata', '21° Giornata', '22° Giornata', '23° Giornata', '24° Giornata', '25° Giornata',
            '26° Giornata', '27° Giornata', '28° Giornata', '29° Giornata', '30° Giornata']


def get_all_games():
    cursor = database.cursor(dictionary=True)
    query = '''
                SELECT 
                    `tlgprob_all_games`.`date`,
                    `tlgprob_all_games`.`team1`,
                    `tlgprob_all_games`.`team1pts`,
                    `tlgprob_all_games`.`team2`,
                    `tlgprob_all_games`.`team2pts`,
                    `tlgprob_all_games`.`StagioneSportiva`,
                    `tlgprob_all_games`.`Fase`,
                    `tlgprob_all_games`.`Giornata`
                FROM `progetto_ai`.`tlgprob_all_games`
            '''
    cursor.execute(query)
    return cursor.fetchall()


def generate_single_players_stats(stagione_sportiva, fino_a_giornata_index=None):
    stagione_sportiva_tiny = stagione_sportiva[2] + stagione_sportiva[3] + "-" + stagione_sportiva[7] + \
                             stagione_sportiva[8]  # 18-19
    folder_path = "Predictor/database/" + stagione_sportiva_tiny

    giornate_input = None
    if fino_a_giornata_index is not None:
        giornate_input = "'" + "','".join(giornate[:fino_a_giornata_index + 1]) + "'"

    single_players = SinglePlayers(database)
    single_players.generate_csv(folder_path=folder_path, stagione_sportiva=stagione_sportiva,
                                giornate=giornate_input)


stagioni_sportive = ['2018/2019', '2019/2020']

all_games = pd.DataFrame(get_all_games())
all_games["date"] = all_games["date"].astype(str)

previous_season_games = all_games.loc[all_games['StagioneSportiva'] == stagioni_sportive[0]].iloc[:, :5]
# previous_season_games = all_games.loc[(all_games['StagioneSportiva'] == '2016/2017') | (all_games['StagioneSportiva'] == '2017/2018') | (all_games['StagioneSportiva'] == '2018/2019')].iloc[:, :5]
training_games = previous_season_games.copy()
current_season_games = all_games.loc[all_games['StagioneSportiva'] == stagioni_sportive[1]]

training_games.to_csv("Predictor/database/all_games.csv", index=False)

# generate_single_players_stats(stagione_sportiva='2016/2017')
# generate_single_players_stats(stagione_sportiva='2017/2018')
generate_single_players_stats(stagione_sportiva=stagioni_sportive[0])

prediction_results = []
prediction_match_difficulty = pd.DataFrame(columns=["points_diff", "Winnning Probability"])

predictor = TLGProb(database_path="Predictor/database/", model_path="Predictor/trained_models/")

for i in range(len(giornate)-1):
    print("\nTRAINING model with", stagioni_sportive[0], "and", stagioni_sportive[1], "until", giornate[i], "\n")

    # Create training dataset
    # Games
    partial_games = current_season_games.loc[current_season_games['Giornata'] == giornate[i]].iloc[:, :5]
    if partial_games.shape[0] == 0:
        print("Skip training because there are no new games to train with")
        continue
    training_games = pd.concat([training_games, partial_games])
    training_games.to_csv("Predictor/database/all_games.csv", index=False)
    # print("Training dataset")
    # print(temp)

    # Players
    generate_single_players_stats(stagione_sportiva=stagioni_sportive[1], fino_a_giornata_index=i)

    # Delete trained models
    shutil.rmtree("Predictor/trained_models", ignore_errors=True)

    predictor.load_data()
    predictor.train_player_models()
    predictor.train_winning_team_model()

    # Prediction dataset
    print("PREDICTING", stagioni_sportive[1], "(", giornate[i+1], ")\n")

    future_games = current_season_games.loc[current_season_games['Giornata'] == giornate[i+1]].iloc[:, :5]
    if future_games.shape[0] == 0:
        print("Skip prediction because there are no games to predict")
        continue

    future_games_temp = future_games.copy()
    future_games_temp["team1pts"] = -1
    future_games_temp["team2pts"] = -1
    temp = pd.concat([training_games, future_games_temp])
    temp.to_csv("Predictor/database/all_games.csv", index=False)
    # print("Prediction dataset")
    # print(temp)

    predictor.load_data()
    prediction_result = predictor.generate_next_prediction()
    predicted_games = pd.DataFrame(prediction_result,
                                   columns=['year', 'month', 'day', 'team1', 'team2', 'Pred Winnning Team',
                                            'Winnning Probability', 'Points Differential 95% C.I. team1',
                                            'Points Differential 95% C.I. team2'])

    predicted_games['month'] = predicted_games['month'].astype(str)
    predicted_games['month'] = predicted_games['month'].str.zfill(2)
    predicted_games['day'] = predicted_games['day'].astype(str)
    predicted_games['day'] = predicted_games['day'].str.zfill(2)
    predicted_games['date'] = predicted_games['year'].astype(str) + "-" + predicted_games['month'].astype(str) + "-" + predicted_games['day'].astype(str)
    predicted_games['date'] = predicted_games['date'].astype(str)
    predicted_games.drop(['year', 'month', 'day'], axis=1, inplace=True)

    prediction_evaluation = pd.merge(left=future_games, right=predicted_games, how='left', left_on=["date", "team1", "team2"], right_on=["date", "team1", "team2"])
    prediction_evaluation["points_diff"] = abs(prediction_evaluation["team1pts"] - prediction_evaluation["team2pts"])
    for index, row in prediction_evaluation.iterrows():
        if row["Pred Winnning Team"] is np.NaN:
            prediction_evaluation.at[index, 'correct'] = np.NaN
            continue
        real_winner = row["team1"] if int(row["team1pts"]) > int(row["team2pts"]) else row["team2"]
        prediction_evaluation.at[index, "correct"] = True if row["Pred Winnning Team"] == real_winner else False

    evaluations = prediction_evaluation["correct"].value_counts().to_dict()
    n_matches = evaluations[True] + (0 if False not in evaluations else evaluations[False])
    correct_predictions = evaluations[True]
    avg_accuracy = correct_predictions / n_matches
    result = {
        "StagioneSportiva": stagioni_sportive[1],
        "Giornata": giornate[i+1],
        "correct_predictions": correct_predictions,
        "n_matches": n_matches,
        "avg_accuracy": avg_accuracy
    }
    prediction_results.append(result)

    print("prediction_evaluation")
    print(prediction_evaluation)
    print("result")
    print(pd.DataFrame([result]))
    print("general result")
    df_prediction_result = pd.DataFrame(prediction_results)
    print(df_prediction_result)
    print("total avg = ", df_prediction_result["avg_accuracy"].mean())

    prediction_match_difficulty.reset_index(drop=True, inplace=True)
    prediction_match_difficulty = pd.concat([prediction_match_difficulty, prediction_evaluation[["points_diff", "Winnning Probability"]]])
    print(prediction_match_difficulty.sort_values(by=["points_diff", "Winnning Probability"]))


print("Predictions ended!")
