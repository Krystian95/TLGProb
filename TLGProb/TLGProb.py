################################################################################
#  TLGProb: Two-Layer Gaussian Process Regression Model For
#           Winning Probability Calculation of Two-Team Sports
#  Github: https://github.com/MaxInGaussian/TLGProb
#  Author: Max W. Y. Lam (maxingaussian@gmail.com)
################################################################################

import sys, os
import csv
import numpy as np
from SSGP import SSGP
from scipy.sparse.linalg.isolve.tests.test_lsqr import n

from .WrappedPredictor import WrappedPredictor

# ADDED [!]
from .CustomUtils import CustomUtils

class TLGProb(object):

    custom_utils = None  # ADDED [!]

    loaded_winning_team_model, loaded_player_models = None, {}
    best_model_rmse, correct_distribution = -1, []
    winning_team_model_dataset, distribution = None, {}
    player_to_date, player_to_attributes = {}, {}
    coming_game_date, coming_game_dict, game_dict = [], {}, {}
    all_player, player_dict = set(), {}
    all_position, player_to_position, position_to_player = set(), {}, {}
    all_team, team_to_player, player_to_team = set(), {}, {}

    def __init__(self, database_path="database/", model_path="trained_models/"):
        fileDir = os.path.dirname(os.path.realpath('__file__'))
        self.database_path = os.path.join(fileDir, database_path)
        self.model_path = os.path.join(fileDir, model_path)

    def load_data(self):
        dir_path = self.database_path
        all_player_csv = dir_path + "all_players.csv"
        self.all_player = set()
        self.all_team = set()
        self.all_position = set()
        self.all_position.add("C")
        self.all_position.add("F")
        self.all_position.add("G")
        self.player_to_position = {}
        self.player_to_attributes = {}
        self.player_to_date, self.player_to_team = {}, {}
        self.distribution = {pos: [] for pos in self.all_position}
        self.position_to_player = {pos: set() for pos in self.all_position}
        with open(all_player_csv, 'rt') as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.player_dict = {h: [] for h in headers}
            for row in reader:
                for h, v in zip(headers, row):
                    if(h.lower() == "from"):
                        self.player_dict[h].append(int(v))
                    elif(h.lower() == "to"):
                        self.player_dict[h].append(int(v))
                    elif(h.lower() == "height"):
                        self.player_dict[h].append(float(v))
                    elif(h.lower() == "weight"):
                        self.player_dict[h].append(float(v))
                    elif(h.lower() == "position"):
                        if("C" in str(v)):
                            pos = "C"
                        elif("F" in str(v)):
                            pos = "F"
                        elif("G" in str(v)):
                            pos = "G"
                        player = self.player_dict["name"][-1]
                        self.player_to_position[player] = pos
                        self.player_dict[h].append(pos)
                    else:
                        self.player_dict[h].append(str(v))

        self.custom_utils = CustomUtils(player_dict=self.player_dict)  # ADDED [!]

        for year_dir in next(os.walk(dir_path))[1]:
            year = 2000 + int(year_dir[-2:])
            print("loading players CSV in", year, "......")
            if(year not in self.player_to_team.keys()):
                self.player_to_team[year] = {}
            if(year not in self.team_to_player.keys()):
                self.team_to_player[year] = {}
            year_dir = dir_path+year_dir+"/"
            all_player_game_csv = []
            for (dirpath, dirnames, filenames) in os.walk(year_dir):
                for filename in filenames:
                    if(".csv" in filename):
                        all_player_game_csv.append(filename)
                break
            for player_game_csv in all_player_game_csv:
                player = player_game_csv[:-4].replace("_", " ")
                self.all_player.add(player)
                self.position_to_player[self.player_to_position[player]].add(player)
                if(player not in self.player_to_date.keys()):
                    self.player_to_date[player] = []
                with open(year_dir+player_game_csv, 'rt') as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    if(player not in self.player_to_attributes.keys()):
                        self.player_to_attributes[player] = {h: [] for h in headers}
                    for row in reader:
                        data_error = False
                        mp = 0.1
                        for h, v in zip(headers, row):
                            if(h == "mp"):
                                mp = max(mp, float(v))
                            if(h == "+/-" and float(v) > 100):
                                data_error = True
                                print(player, date)
                        if(data_error):
                            continue
                        for h, v in zip(headers, row):
                            if(h == "date"):
                                self.player_to_date[player].append(int(v.replace("-", "")))
                            elif(h == "team"):
                                self.player_to_team[year][player] = str(v)
                                if(str(v) not in self.team_to_player[year]):
                                    self.team_to_player[year][v] = set([player])
                                else:
                                    self.team_to_player[year][v].add(player)
                                if(str(v) not in self.all_team):
                                    self.all_team.add(str(v))
                            elif(h == "opp"):
                                self.player_to_attributes[player][h].append(str(v))
                            elif(h == "+/-"):
                                self.player_to_attributes[player][h].append(float(v)/mp)
                                self.distribution[self.player_to_position[player]].append(float(v)/mp)
                            elif(h == "age" or h == "mp" or "%" in h):
                                self.player_to_attributes[player][h].append(float(v))
                            else:
                                self.player_to_attributes[player][h].append(float(v)/mp)
        print("loading All Matches Records......")
        all_game_csv = dir_path + "all_games.csv"
        coming_game_dict_h = ["date", "team1", "team2"]
        with open(all_game_csv, 'rt') as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.coming_game_dict = {h: [] for h in coming_game_dict_h}
            self.game_dict = {h: [] for h in headers}
            self.coming_game_date = [[], []]
            min_date_diff = [21000000, 21000001]
            for row in reader:
                for h, v in zip(headers, row):
                    if(float(row[2]) < 0):  # se il punteggio è negativo lo aggiunge ai "coming_game_dict"
                        if(h == "date"):
                            self.coming_game_dict[h].append(list(map(int, v.split("-"))))
                            yeari, monthi, dayi = self.coming_game_dict[h][-1]
                            date_inti = yeari*10000 + monthi*100 + dayi
                            if(date_inti < min_date_diff[0]):
                                self.coming_game_date[0] = [yeari, monthi, dayi]
                                min_date_diff[0] = date_inti
                            else:
                                if(min_date_diff[0] < date_inti < min_date_diff[1]):
                                    self.coming_game_date[1] = [yeari, monthi, dayi]
                                    min_date_diff[1] = date_inti
                        elif("pts" in h):
                            continue
                        else:
                            self.coming_game_dict[h].append(str(v))
                    else:
                        if(h == "date"):
                            self.game_dict[h].append(list(map(int, v.split("-"))))
                        elif("pts" in h):
                            self.game_dict[h].append(float(v))
                        else:
                            self.game_dict[h].append(str(v))
            self.coming_game_match = [[], []]
            for i, date in enumerate(self.coming_game_dict["date"]):
                if(date == self.coming_game_date[0]):
                    self.coming_game_match[0].append(
                        (self.coming_game_dict["team1"][i],
                         self.coming_game_dict["team2"][i]))
                if(date == self.coming_game_date[1]):
                    self.coming_game_match[1].append(
                        (self.coming_game_dict["team1"][i],
                         self.coming_game_dict["team2"][i]))
        print("All CSV Data is Loaded!")
        self.feature_extraction()
        self.feature_smoothing()

    def feature_extraction(self):
        print("Extracting Featrues from the Data......")
        self.key_to_player_input_id = {"fg%":0, "fg":1, "fga": 2, "3p%":3, "3p": 4, "3pa": 5,
                                       "ft%":6, "ft": 7, "fta": 8, "orb": 9, "drb": 10, "trb": 11,
                                       "ast": 12, "stl": 13, "blk": 14, "tov": 15, "pf": 16, "pts": 17}
        for player in self.all_player:
            n = len(self.player_to_attributes[player]["opp"])
            performance_mat = np.zeros((n, len(self.key_to_player_input_id)))
            opp_list = []
            for t in range(n):
                for (key, vec) in self.player_to_attributes[player].items():
                    if(key not in self.key_to_player_input_id.keys()):
                        continue
                    performance_mat[t, self.key_to_player_input_id[key]] += vec[t]
                opp_list.append(self.player_to_attributes[player]["opp"][t])
            self.player_to_attributes[player]["performance"] = performance_mat
        print("Featrues of all players are extracted!")

    def feature_smoothing(self):
        print("Smoothing Extracted Featrues......")
        for player in self.all_player:
            ori_mp_vec = self.player_to_attributes[player]["mp"]
            ori_performance_mat = self.player_to_attributes[player]["performance"]
            ori_plus_minus_vec = self.player_to_attributes[player]["+/-"]
            dates = self.player_to_date[player]
            n = ori_performance_mat.shape[0]
            if(n==0):
                print(player)
            new_mp_vec = np.zeros(n)
            new_performance_mat = np.zeros((n, len(self.key_to_player_input_id)))
            new_plus_minus_vec = np.zeros(n)
            lq = np.percentile(ori_performance_mat, 25, axis=0)
            rq = np.percentile(ori_performance_mat, 75, axis=0)
            midq = 0.5*lq + 0.5*rq
            dis = np.linalg.norm(lq-midq, ord=0.5)
            res = lq + rq
            count = 2
            for i in range(n):
                if(np.linalg.norm(ori_performance_mat[i]-midq, ord=0.5) < dis):
                    res += ori_performance_mat[i]
                    count += 1
            new_performance_vec_s = res*1./count
            new_mp_s = np.median(ori_mp_vec)
            new_plus_minus_s = np.median(ori_plus_minus_vec)
            for t in range(1, n):
                new_mp_vec[t-1] = new_mp_s.copy()
                new_performance_mat[t-1] = new_performance_vec_s.copy()
                new_plus_minus_vec[t-1] = new_plus_minus_s.copy()
                date_diff = min(abs(dates[t] - dates[t-1]), 6)
                mp_time_weight = (1-np.exp(-1))**(date_diff/2.)
                performance_time_weight = (1-np.exp(-1))**(date_diff/3.)
                plus_minus_time_weight = (1-np.exp(-1))**(date_diff)
                new_mp_s = (1-mp_time_weight)*ori_mp_vec[t]+mp_time_weight*new_mp_s
                if(self.player_to_attributes[player]["mp"][t] > 0):
                    new_performance_vec_s = (1-performance_time_weight)*ori_performance_mat[t] + \
                        performance_time_weight*new_performance_vec_s
                    new_plus_minus_s = (1-plus_minus_time_weight)*ori_plus_minus_vec[t] + \
                        plus_minus_time_weight*new_plus_minus_s
            new_mp_vec[n-1] = new_mp_s.copy()
            new_performance_mat[n-1] = new_performance_vec_s.copy()
            new_plus_minus_vec[n-1] = new_plus_minus_s.copy()
            self.player_to_attributes[player]["smoothed_team_participation"] = new_mp_vec
            self.player_to_attributes[player]["smoothed_performance"] = new_performance_mat
            self.player_to_attributes[player]["smoothed_plus_minus"] = new_plus_minus_vec
        print("Extracted Featrues are smoothed!")

    def generate_next_prediction(self):
        prediction_result = []

        output_str = "\n" + " "*44+"FUTURE PREDICTIONS"+"\r\n\n"
        output_str += "="*109+"\r\n"
        output_str += " "*44+"PREDICTOR ACCURACIES"+"\r\n"
        output_str += "="*109+"\r\n\t"
        year1, month1, day1 = self.coming_game_date[0]
        if len(self.coming_game_date[1]) > 0:  # ADDED
            year2, month2, day2 = self.coming_game_date[1]
        pred_accur_test = [50, 100, 200]
        estimators = ["PLUS/MINUS"]
        pred_accur = {}
        rej, cor, incor = self.eval_accuracy_by_date(year1, month1, day1, pred_accur_test)
        for i, h1 in enumerate(pred_accur_test):
            pred_accur[h1] = cor[i]*1./(cor[i]+incor[i])
        for i, h1 in enumerate(pred_accur_test):
            output_str+="\tACCURACY-LAST-"+str(h1)+"-GAMES"+\
                ("\t" if i<len(pred_accur_test)-1 else "\r\n")
        acc = []
        for j, h2 in enumerate(estimators):
            acc.append(1.)
            output_str+=h2+"\t\t"
            for i, h1 in enumerate(pred_accur_test):
                acc[-1] = min(pred_accur[h1], acc[-1])
                output_str+="%.3f" % (pred_accur[h1])
                output_str+="\t\t\t\t" if i<len(pred_accur_test)-1 else "\r\n"
        output_str += "="*109+"\r\n"
        output_str += " "*34+"PREDICTION OF WINNING TEAMS ON %d/%d/%d"%(day1, month1, year1)+"\r\n"
        output_str += "="*109+"\r\n\t\t"
        output_str +="\tMatch\t\tWinning Team\t\tWinning Probability\t\tPoints Differential 95% C.I.\r\n"
        for team1, team2 in self.coming_game_match[0]:
            output_str += team1+" VS "+team2+"\t\t"
            pred_win_team, prob, y_pred, y_std = self.predict_match(team1, team2, year1, month1, day1)
            prediction_result.append((year1, month1, day1, team1, team2, pred_win_team, prob, y_pred-1.96*y_std, y_pred+1.96*y_std))
            output_str += "%s\t\t\t%.3f\t\t\t\t[%.3f, %.3f]\r\n"%(pred_win_team, prob, y_pred-1.96*y_std, y_pred+1.96*y_std)
        if len(self.coming_game_date[1]) > 0:  # ADDED
            output_str += "="*109+"\r\n"
            output_str += " "*34+"PREDICTION OF WINNING TEAMS ON %d/%d/%d"%(day2, month2, year2)+"\r\n"
            output_str += "="*109+"\r\n\t\t"
            output_str +="\tMatch\t\tWinning Team\t\tWinning Probability\t\tPoints Differential 95% C.I.\r\n"
            for team1, team2 in self.coming_game_match[1]:
                output_str += team1+" VS "+team2+"\t\t"
                if team1 not in self.team_to_player[year2 + 1 if month2 > 8 else year2]:
                    output_str += "Prediction skipped - Team " + team1 + " not known before match's date " + str(year2) + "-" + str(month2) + "-" + str(day2) + "\n"
                    continue
                pred_win_team, prob, y_pred, y_std = self.predict_match(team1, team2, year2, month2, day2)
                prediction_result.append((year2, month2, day2, team1, team2, pred_win_team, prob, y_pred-1.96*y_std, y_pred+1.96*y_std))
                output_str += "%s\t\t\t%.3f\t\t\t\t[%.3f, %.3f]\r\n"%(pred_win_team, prob, y_pred-1.96*y_std, y_pred+1.96*y_std)
        print(output_str)
        return prediction_result

    def eval_accuracy_by_date(self, year, month, day,
        test_nums=[20, 50, 100], regression_methods=["SSGPR", "SSGPR"]):
        self.load_player_models(regression_methods[0])  
        self.load_winning_team_model(regression_methods[1])
        test_ind = {h:{} for h in test_nums}
        count_reject, count_correct, count_incorrect = [0]*len(test_nums), [0]*len(test_nums), [0]*len(test_nums)
        date_int = year*10000 + month*100 + day
        for i in range(len(self.game_dict["date"])):
            yeari, monthi, dayi = self.game_dict["date"][i]
            date_inti = yeari*10000 + monthi*100 + dayi
            cost = date_int if (date_inti > date_int) else date_int-date_inti
            for test_num in test_nums:
                if(len(test_ind[test_num]) < test_num):
                    test_ind[test_num][i] = cost
                else:
                    maxi = max(test_ind[test_num], key=test_ind[test_num].get)
                    if(cost < test_ind[test_num][maxi]):
                        del test_ind[test_num][maxi]
                        test_ind[test_num][i] = cost
        for i in test_ind[max(test_nums)].keys():
            team1 = self.game_dict["team1"][i]
            team2 = self.game_dict["team2"][i]
            team1pts = self.game_dict["team1pts"][i]
            team2pts = self.game_dict["team2pts"][i]
            year, month, day = self.game_dict["date"][i]
            print("\nIf", team1, "meets", team2, "on", year, month, day, "then...")
            pred_win_team, prob, y_pred, y_std = self.predict_match(team1, team2, year, month, day)
            true_win_team = team1 if team1pts > team2pts else team2
            print("In reality,", true_win_team, "win!")
            if(pred_win_team == "---"):
                print("The predictor rejected the result.")
                for j, test_num in enumerate(test_nums):
                    if(i in test_ind[test_num].keys()):
                        count_reject[j] += 1
            else:
                if(pred_win_team == true_win_team):
                    print("So, the prediction is correct!")
                    for j, test_num in enumerate(test_nums):
                        if(i in test_ind[test_num].keys()):
                            count_correct[j] += 1
                else:
                    print("So, the prediction is incorrect!")
                    for j, test_num in enumerate(test_nums):
                        if(i in test_ind[test_num].keys()):
                            count_incorrect[j] += 1
                print("Accuracy for", str(test_num),\
                    "= %.3f"%(count_correct[j]*1./(count_incorrect[j]+count_correct[j])))
        return count_reject, count_correct, count_incorrect

    # ADDED [!] param "test_set"
    def eval_accuracy(self, eval_season=None, threshold=0.5, regression_methods=["SSGPR", "SSGPR"], test_set=None):
        self.eval_results = []
        self.load_player_models(regression_methods[0])  
        self.load_winning_team_model(regression_methods[1])
        self.correct_distribution, self.incorrect_distribution = [], []

        # ADDED [!] - START
        is_custom_test_set = False if test_set is None else True
        if is_custom_test_set:
            self.game_dict = test_set.copy()
        # ADDED [!] - END

        test_size = len(self.game_dict["team1"])
        count_reject, count_correct, count_incorrect = 0, 0, 0
        for i in range(test_size):
            team1 = self.game_dict["team1"][i]
            team2 = self.game_dict["team2"][i]
            team1pts = self.game_dict["team1pts"][i]
            team2pts = self.game_dict["team2pts"][i]
            year, month, day = self.game_dict["date"][i]
            date = year*10000+month*100+day
            season = year + 1 if month > 8 else year
            if(eval_season is not None and eval_season != season):
                continue
            print("\nIf", team1, "meets", team2, "on", year, month, day,"then...")
            pred_win_team, prob, y_pred, y_std = self.predict_match(
                team1, team2, year, month, day, threshold, regression_methods)
            y_true = team1pts-team2pts
            self.eval_results.append([prob, np.sign(y_pred)==np.sign(y_true), y_pred, y_true])
            true_win_team = team1 if team1pts > team2pts else team2
            print("In reality,", true_win_team, "win!")
            if(pred_win_team == "---"):
                print("The predictor rejected the result.")
                count_reject += 1
            else:
                if(pred_win_team == true_win_team):
                    print("So, the prediction is correct!")
                    count_correct += 1
                    self.correct_distribution.append(prob)
                elif(pred_win_team != true_win_team):
                    print("So, the prediction is incorrect!")
                    count_incorrect += 1
                    self.incorrect_distribution.append(prob)
                print("Current accuracy =", (count_correct*1./(count_correct+count_incorrect)))
        print("\nWe have", count_reject, "rejections,",\
            count_correct, "correct prediction and,",\
            count_incorrect, "incorrect prediction.")
        file_dir = os.path.dirname(os.path.realpath('__file__'))
        evaluation_log_csv = self.model_path + "evaluation_log.csv"
        first_save = not os.path.isfile(evaluation_log_csv)
        headers = ["Date", "Team Model", "Center Model", "Forward Model", "Guard Model",
                   "Num of Test Case", "Num of Reject", "Num of Correct", "Num of Incorrect", "Accuracy"]
        with open(evaluation_log_csv, 'wt' if first_save else 'at') as f:
            csv_writer = csv.DictWriter(f, fieldnames=headers)
            if(first_save):
                csv_writer.writeheader()
            csv_dict = dict.fromkeys(headers)
            from datetime import datetime
            csv_dict[headers[0]] = datetime.today().strftime("%Y-%m-%d %H:%M:%S") # MODIFIED [!] (added timestamp)
            csv_dict[headers[1]] = self.loaded_winning_team_model.regression_method+"-"+self.loaded_winning_team_model.hashed_name
            csv_dict[headers[2]] = self.loaded_player_models["C"].regression_method+"-"+self.loaded_player_models["C"].hashed_name
            csv_dict[headers[3]] = self.loaded_player_models["F"].regression_method+"-"+self.loaded_player_models["F"].hashed_name
            csv_dict[headers[4]] = self.loaded_player_models["G"].regression_method+"-"+self.loaded_player_models["G"].hashed_name
            csv_dict[headers[5]] = test_size
            csv_dict[headers[6]] = count_reject
            csv_dict[headers[7]] = count_correct
            csv_dict[headers[8]] = count_incorrect
            csv_dict[headers[9]] = 0 if (count_correct+count_incorrect) == 0 else (count_correct*1./(count_correct+count_incorrect))
            csv_writer.writerow(csv_dict)
        return self.eval_results

    def model_selection(self, regression_method="SSGPR"):
        import glob
        model_path = self.get_player_model_path_by_pos(pos, regression_method)
        model_dir = '/'.join(model_path.split('/')[:-1])
        C_models = glob.glob(model_dir+"Center*.pkl")
        F_models = glob.glob(model_dir+"Forward*.pkl")
        G_models = glob.glob(model_dir+"Guard*.pkl")
        WIN_models = glob.glob(model_dir+"Team*.pkl")
        self.load_player_models(regression_method)
        self.load_winning_team_model(regression_method)
        best_models, models, accuracy = [None]*4, [None]*4, 0
        for C_model in C_models:
            self.loaded_player_models["C"] = SSGP()
            self.loaded_player_models["C"].load(C_model)
            models[0] = C_model
            for F_model in F_models:
                self.loaded_player_models["F"] = SSGP()
                self.loaded_player_models["F"].load(F_model)
                models[1] = F_model
                for G_model in G_models:
                    self.loaded_player_models["G"] = SSGP()
                    self.loaded_player_models["G"].load(G_model)
                    models[2] = G_model
                    for WIN_model in WIN_models:
                        self.loaded_winning_team_model = SSGP()
                        self.loaded_winning_team_model.load(WIN_model)
                        models[3] = WIN_model
                        _accuracy = self.eval_accuracy()
                        if(_accuracy > accuracy):
                            accuracy = _accuracy
                            best_models = models
        import shutil
        shutil.copy2(best_models[0], self.get_player_model_path_by_pos("C", regression_method))
        shutil.copy2(best_models[1], self.get_player_model_path_by_pos("F", regression_method))
        shutil.copy2(best_models[2], self.get_player_model_path_by_pos("G", regression_method))
        shutil.copy2(best_models[3], self.get_winning_team_model_path())

    def predict_match(self, team1, team2, year, month, day,
        threshold=0.5, regression_methods=["SSGPR", "SSGPR"]):
        assert (team1 in self.all_team and team2 in self.all_team), "Unknown Team Name! ('" + team1 + "' or '" + team2 +"')"
        X = self.get_winning_team_model_input(team1, team2, year, month, day)
        y_pred, y_std = self.loaded_winning_team_model.predict(X)
        y_pred, y_std = np.double(y_pred), np.double(y_std)
        print("Predicted", team1, "-", team2, "= [", y_pred-1.96*y_std, ",", y_pred+1.96*y_std, "]")
        from scipy.stats import norm
        prob = 1-norm.cdf(-y_pred/y_std)
        print(team1 + "'s winning probability =", prob)
        print(team2 + "'s winning probability =", 1-prob)
        sys.stdout.flush()
        if(prob > threshold):
            return team1, prob, y_pred, y_std
        elif(1-prob > threshold):
            return team2, 1-prob, y_pred, y_std
        return "---", prob, y_pred, y_std

    def check_trained_models(self, regression_methods=["SSGPR", "SSGPR"]):
        import glob
        models = glob.glob(self.get_winning_team_model_path(
            regression_method=regression_methods[1]))
        if(len(models) != 1):
            return False
        for pos in ["C", "F", "G"]:
            models = glob.glob(self.get_player_model_path_by_pos(pos,
                regression_method=regression_methods[0]))
            if(len(models) != 1):
                return False
        return True

    def load_winning_team_model(self, regression_method="SSGPR"):
        print("loading trained TEAM model......")
        self.loaded_winning_team_model = WrappedPredictor(regression_method)
        self.loaded_winning_team_model.load(self.get_winning_team_model_path(regression_method))
        print("loaded", regression_method, "model", self.loaded_winning_team_model.hashed_name)

    def load_player_models(self, regression_method="SSGPR"):
        print("loading trained POSITION models......")
        self.loaded_player_models = {}
        for pos in ["C", "F", "G"]:
            self.loaded_player_models[pos] = WrappedPredictor(regression_method)
            self.loaded_player_models[pos].load(self.get_player_model_path_by_pos(pos, regression_method))
            print("loaded", regression_method, "model", self.loaded_player_models[pos].hashed_name)
        
    def get_winning_team_model_path(self, regression_method="SSGPR", name=""):
        model_dir = self.model_path+regression_method+"/"
        if(name == ""):
            model_dir = model_dir
        else:
            model_dir = model_dir+"predictors/"
        return model_dir + "Team" + name + ".pkl"

    def get_player_model_path_by_pos(self, pos, regression_method="SSGPR", name=""):
        #print("[get_player_model_path_by_pos] pos = "+pos+ ", regression_method = "+regression_method+", name = "+name)
        model_dir = self.model_path+regression_method+"/"
        if(name == ""):
            model_dir = model_dir
        else:
            model_dir = model_dir+"predictors/"
        pos_pred = "G"
        if("C" in pos):
            pos_pred = "Center"
        elif("F" in pos):
            pos_pred = "Forward"
        elif("G" in pos):
            pos_pred = "Guard"
        return model_dir + pos_pred + name + ".pkl"

    def get_team_players_by_date(self, team, year, month, day, num_of_players=10):
        players = self.team_to_player[year+1 if month > 8 else year][team]
        # Salva una priorità per ogni giocatore
        date_int = year*10000 + month*100 + day
        players_priority = {}
        for p in players:
            dates = self.player_to_date[p]
            date_diff = date_int - min(dates, key=lambda x:date_int if (x>date_int) else date_int-x)
            players_priority[p] = date_diff
        import operator
        sorted_players = sorted(players_priority.items(), key=operator.itemgetter(1))
        sieved_players_priority = {}
        for i in range(len(sorted_players)):
            p, date_diff = sorted_players[i]
            date_id = self.get_player_date_id_by_date(p, year, month, day)
            parti = self.player_to_attributes[p]["smoothed_team_participation"][date_id]
            sieved_players_priority[p] = parti
        sorted_sieved_players = sorted(sieved_players_priority.items(), key=operator.itemgetter(1), reverse=True)[:num_of_players]
        predicted_players = [p for p, parti in sorted_sieved_players]
        count_position = {pos:0 for pos in self.all_position}
        for p in predicted_players:
            count_position[self.player_to_position[p]] += 1
        # ADDED [!] disabled count_position check (allow exists one position with zero players, but always having 10 players per match -> fix next)
        '''if(min(count_position.values()) == 0):
            # Se un ruolo ha zero giocatori: prova a recuperare un giocatore della squadra con il ruolo mancante.
            missed_pos = min(count_position, key=count_position.get)
            find_player = list(set(self.position_to_player[missed_pos]).intersection(set(dict(sorted_players).keys())))
            if(len(find_player) == 0):
                print("MISSING ROLE:",missed_pos, team, year, month, day, players)
                for p in predicted_players:
                    print(p, self.player_to_position[p], end=" ")
                sys.exit()
            predicted_players.pop()
            predicted_players.append(find_player[0])'''
        return predicted_players

    def get_player_date_id_by_date(self, player, year, month, day):
        date_int = year*10000 + month*100 + day
        dates = self.player_to_date[player]
        date_id = dates.index(
            min(dates, key=lambda x:date_int if (x>date_int) else date_int-x))
        return date_id

    def get_player_date_by_date_id(self, player, date_id):
        dates = self.player_to_date[player]
        date_int = dates[date_id]
        return int(str(date_int)[:4]), int(str(date_int)[4:6]), int(str(date_int)[6:])

    def get_inferred_player_team_performance_by_date(self, player, team, year, month, day):
        players = self.get_team_players_by_date(team, year, month, day)
        team_player_vec = np.zeros(len(self.key_to_player_input_id))
        sum_weights = 0
        for team_player in players:
            if(team_player == player):
                continue
            date_id = self.get_player_date_id_by_date(team_player, year, month, day)
            weight = self.player_to_attributes[team_player]["smoothed_team_participation"][date_id]
            vec = self.player_to_attributes[team_player]["smoothed_performance"][date_id]
            team_player_vec += weight * vec
            sum_weights += weight
        return team_player_vec/sum_weights

    def decode_performance_vector(self, vec):
        print("-"*30)
        print("Attribute\tValue")
        print("-"*30)
        for k in self.key_to_player_input_id.keys():
            print("   %s\t%.3f"%(k, vec[self.key_to_player_input_id[k]]))
        print("-"*30)

    def get_inferred_player_performance_by_date(self, player, year, month, day):
        assert (player in self.all_player), "Unknown Player Name!"
        date_id = self.get_player_date_id_by_date(player, year, month, day)
        return self.get_player_models_input(player, date_id)[0, :len(self.key_to_player_input_id)]

    def get_player_models_input(self, player, date_id):
        year, month, day = self.get_player_date_by_date_id(player, date_id)
        team = self.player_to_team[year+1 if month > 8 else year][player]
        opp_team = self.player_to_attributes[player]["opp"][date_id]
        x_player = self.player_to_attributes[player]["smoothed_performance"][date_id]
        x_team = self.get_inferred_player_team_performance_by_date(player, team, year, month, day)
        x_opp = self.get_inferred_player_team_performance_by_date(player, opp_team, year, month, day)
        x = x_player+(x_team-x_opp)/2.
        return  x[None, :]

    def get_player_models_dataset(self):
        print("Generating Training and Testing Dataset For Player Models......")
        res = {}
        for pos in self.all_position:
            X, y = None, None
            for player in self.position_to_player[pos]:
                plus_minus_vec = self.player_to_attributes[player]["smoothed_plus_minus"]
                for date_id in range(len(plus_minus_vec)-1):
                    x_i = self.get_player_models_input(player, date_id)
                    y_i = np.array([[plus_minus_vec[date_id+1]]])
                    if(X is None):
                        X = x_i
                        y = y_i
                    else:
                        X = np.vstack((X, x_i))
                        y = np.vstack((y, y_i))
            res[pos] = [X, y]
        print("Training and Testing Dataset For Player Models are Generated!")
        return res

    def train_player_models(self, regression_method="SSGPR"):
        #print("[train_player_models] regression_method = "+regression_method)
        import random
        print("Start Training Player Models......")
        data = self.get_player_models_dataset()
        np.random.seed(np.random.randint(1001))
        rand_permu = np.random.permutation(len(self.all_position))
        for i in rand_permu:
            pos = list(self.all_position)[i]
            dataset = data[pos]
            if("-" in pos):
                pos = pos[0]
            n = dataset[1].shape[0]
            X = dataset[0].copy()
            y = dataset[1].copy()
            print("Next POSITION to train is", pos + ",", "Size =", n)
            model_path = self.get_player_model_path_by_pos(pos, regression_method)
            best_model_path = self.get_player_model_path_by_pos(pos)
            self.train_regression(X, y, model_path, best_model_path, regression_method)

    def get_winning_team_model_input(self, team1, team2, year, month, day, train=False):
        players = self.get_team_players_by_date(team1, year, month, day)
        sum_all_scores, sum_weights = 0, 0
        sum_C_scores, sum_C_weights = 0, 0
        sum_F_scores, sum_F_weights = 0, 0
        sum_G_scores, sum_G_weights = 0, 0
        sorted_scores = []

        # ADDED
        player_positions = self.custom_utils.remapping_player_positions(match_players=players,
                                                                        player_to_position_all_players=self.player_to_position,
                                                                        team=team1, year=year, month=month, day=day)

        for player in players:
            # pos = self.player_to_position[player]
            pos = player_positions[player]  # ADDED
            date_id = self.get_player_date_id_by_date(player, year, month, day)
            if(train):
                score_pred = self.player_to_attributes[player]["smoothed_plus_minus"][date_id]
            else:
                X = self.get_player_models_input(player, date_id)
                score_pred = np.double(self.loaded_player_models[pos].predict(X)[0])
            weight = self.player_to_attributes[player]["smoothed_team_participation"][date_id]
            sorted_scores.append((score_pred, weight))
            sum_all_scores += weight * score_pred
            sum_weights += weight
            if(pos == "C"):
                sum_C_scores += weight * score_pred
                sum_C_weights += weight
            elif(pos == "F"):
                sum_F_scores += weight * score_pred
                sum_F_weights += weight
            elif(pos == "G"):
                sum_G_scores += weight * score_pred
                sum_G_weights += weight
        sorted_scores = sorted(sorted_scores, key=lambda x:x[1], reverse=True)[:6]
        tx = [ss[0] for ss in sorted_scores]
        tx.extend([sum_all_scores/sum_weights, sum_C_scores/sum_C_weights,
                   sum_F_scores/sum_F_weights, sum_G_scores/sum_G_weights])
        x = np.asarray(tx, dtype=np.float64)
        players = self.get_team_players_by_date(team2, year, month, day)
        sum_all_scores, sum_weights = 0, 0
        sum_C_scores, sum_C_weights = 0, 0
        sum_F_scores, sum_F_weights = 0, 0
        sum_G_scores, sum_G_weights = 0, 0
        sorted_scores = []

        # ADDED
        player_positions = self.custom_utils.remapping_player_positions(match_players=players,
                                                                        player_to_position_all_players=self.player_to_position,
                                                                        team=team2, year=year, month=month, day=day)

        for player in players:
            # pos = self.player_to_position[player]
            pos = player_positions[player]  # ADDED
            date_id = self.get_player_date_id_by_date(player, year, month, day)
            score_pred = self.player_to_attributes[player]["smoothed_plus_minus"][date_id]
            weight = self.player_to_attributes[player]["smoothed_team_participation"][date_id]
            sorted_scores.append((score_pred, weight))
            sum_all_scores += weight * score_pred
            sum_weights += weight
            if(pos == "C"):
                sum_C_scores += weight * score_pred
                sum_C_weights += weight
            elif(pos == "F"):
                sum_F_scores += weight * score_pred
                sum_F_weights += weight
            elif(pos == "G"):
                sum_G_scores += weight * score_pred
                sum_G_weights += weight
        sorted_scores = sorted(sorted_scores, key=lambda x:x[1], reverse=True)[:6]
        tx = [ss[0] for ss in sorted_scores]
        tx.extend([0 if sum_weights == 0 else sum_all_scores/sum_weights,
                    0 if sum_C_weights == 0 else sum_C_scores/sum_C_weights,
                    0 if sum_F_weights == 0 else sum_F_scores/sum_F_weights,
                    0 if sum_G_weights == 0 else sum_G_scores/sum_G_weights])
        x -= np.asarray(tx, dtype=np.float64)
        return x[None, :]

    def get_winning_team_model_dataset(self, regression_method="SSGPR"):
        print("Generating Training and Testing Dataset For Winning Team Model......")
        #n = len(self.game_dict["team1"]) - 200  # Ultime 200 gare
        n = len(self.game_dict["team1"])  # ADDED (prova)

        self.load_player_models(regression_method)
        X, y = None, None

        for i in range(n):
            '''team1 = self.game_dict["team1"][i+200]
            team2 = self.game_dict["team2"][i+200]
            team1pts = self.game_dict["team1pts"][i+200]
            team2pts = self.game_dict["team2pts"][i+200]
            year, month, day = self.game_dict["date"][i+200]'''
            # ADDED (prova)
            team1 = self.game_dict["team1"][i]
            team2 = self.game_dict["team2"][i]
            team1pts = self.game_dict["team1pts"][i]
            team2pts = self.game_dict["team2pts"][i]
            year, month, day = self.game_dict["date"][i]
            print("Get -> ", team1, "vs", team2, "on", year, month, day)
            x_i = self.get_winning_team_model_input(team1, team2, year, month, day, True)
            y_i = np.array([[team1pts-team2pts]])
            if(X is None):
                X = x_i
                y = y_i
            else:
                X = np.vstack((X, x_i))
                y = np.vstack((y, y_i))
        print("Training and Testing Dataset For Winning Team Model are Generated!")
        self.winning_team_model_dataset = [X, y]

    def train_winning_team_model(self, regression_method="SSGPR"):
        print("Start Training Winning Team Model......")
        if(self.winning_team_model_dataset is None):
            self.get_winning_team_model_dataset(regression_method)
        dataset = self.winning_team_model_dataset
        np.random.seed(np.random.randint(1001))
        n = dataset[1].shape[0]
        X = dataset[0].copy()
        y = dataset[1].copy()
        print("Training Data Size =", n)
        model_path = self.get_winning_team_model_path(regression_method)
        best_model_path = self.get_winning_team_model_path()
        self.train_regression(X, y, model_path, best_model_path, regression_method)
    
    def train_regression(self, X, y, model_path, best_model_path, regression_method):
        #print("[train_regression] model_path = "+model_path+", best_model_path = "+best_model_path+", regression_method = "+regression_method)
        import glob
        import random
        from sklearn.model_selection import GridSearchCV
        model_dir = '/'.join(model_path.split('/')[:-1])
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
        if(regression_method == "SSGPR"):
            freq_noisy = random.choice([True, False])
            model = SSGP(int(np.random.randint(n/15)+n/20), freq_noisy)
            print("TRY NEW MODEL [SSGP %d (%s)]......" % (model.m,
                ("NOISY" if freq_noisy else "NOT_NOISY")))
            model.fit(X.copy(), y.copy())
        elif(regression_method == "KernelRidge"):
            from sklearn.kernel_ridge import KernelRidge
            model = GridSearchCV(
                KernelRidge(kernel='rbf', gamma=0.1),
                cv=5,
                n_jobs=2,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    "alpha": [1, 1e-1, 1e-2, 1e-3],
                    "gamma": np.logspace(-3, 3, 10)
                }
            )
            model.fit(X, y.ravel())
            model = model.best_estimator_
        elif(regression_method == "DecisionTreeRegressor"):
            from sklearn.tree import DecisionTreeRegressor
            model = GridSearchCV(
                DecisionTreeRegressor(max_depth=10),
                cv=5,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    "min_samples_split": list(range(2, 16)),
                    'criterion':['mse', 'mae']
                }
            )
            model.fit(X, y.ravel())
            model = model.best_estimator_
        elif(regression_method == "AdaBoostDecisionTreeRegressor"):
            from sklearn.ensemble import AdaBoostRegressor
            from sklearn.tree import DecisionTreeRegressor
            boost_model = GridSearchCV(
                DecisionTreeRegressor(max_depth=10),
                cv=5,
                n_jobs=2,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    "min_samples_split": list(range(2, 16)),
                    'criterion':['mse', 'mae']
                }
            )
            boost_model.fit(X, y.ravel())
            boost_model = boost_model.best_estimator_
            boost_model.set_params(max_depth=5)
            model = GridSearchCV(
                AdaBoostRegressor(boost_model),
                cv=5,
                n_jobs=2,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    "n_estimators": list(range(10, 31, 10)),
                    "loss": ["linear", "square", "exponential"]
                }
            )
            model.fit(X, y.ravel())
            model = model.best_estimator_
        elif(regression_method == "GradientBoostingRegressor"):
            from sklearn.ensemble import GradientBoostingRegressor
            model = GridSearchCV(
                GradientBoostingRegressor(),
                cv=5,
                n_jobs=2,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    "min_samples_split": list(range(2, 16)),
                    'loss':['ls', 'lad', 'huber', 'quantile'],
                    "n_estimators": list(range(100, 301, 50)),
                }
            )
            model.fit(X, y.ravel())
            model = model.best_estimator_
        elif(regression_method == "RandomForestRegressor"):
            from sklearn.ensemble import RandomForestRegressor
            model = GridSearchCV(
                RandomForestRegressor(max_depth=6),
                cv=5,
                n_jobs=2,
                verbose=True,
                scoring='neg_mean_squared_error',
                param_grid={
                    'criterion':['mse', 'mae'],
                    "n_estimators": list(range(5, 26, 5)),
                }
            )
            model.fit(X, y.ravel())
            model = model.best_estimator_
        model = WrappedPredictor(regression_method, model, X, y)
        model.save(model_path) # potrebbe dover essere messa dopo model.predict() alla riga successiva
        mse, nmse, mnlp = model.predict(X.copy(), y.copy())
        print("RESULT OF %s MODEL (%s):" % (regression_method, model.hashed_name))
        print("\tMSE = %.5f\n\tNMSE = %.5f\n\tMNLP = %.5f"%(mse, nmse, mnlp))
        existed = glob.glob(model_path)
        if(len(existed) == 1):
            try:
                best_model = WrappedPredictor()
                best_model.load(best_model_path)
            except:
                best_model = WrappedPredictor('SSGPR')
                best_model.load(best_model_path)
            min_mse, min_nmse, min_mnlp = best_model.predict(X.copy(), y.copy())
            print("RESULT OF BEST MODEL (%s-%s):" % (regression_method, model.hashed_name))
            print("\tMSE = %.5f\n\tNMSE = %.5f\n\tMNLP = %.5f"%(min_mse, min_nmse, min_mnlp))
            if(nmse*mnlp < min_nmse*min_mnlp):
                os.remove(best_model_path)
                model.save(best_model_path)
                self.eval_accuracy()
            if(nmse < min_nmse or mnlp < min_mnlp or nmse*mnlp*0.95 < min_nmse*min_mnlp):
                model.save(model_path[:-4]+model.hashed_name+".pkl")
        else:
            print("NO BEST MODEL IS STROED")
            model.save(best_model_path)
            model.save(model_path[:-4]+model.hashed_name+".pkl")
    
    
    
    
    
    
    