################################################################################
#  TLGProb: Two-Layer Gaussian Process Regression Model For
#           Winning Probability Calculation of Two-Team Sports
#  Github: https://github.com/MaxInGaussian/TLGProb
#  Author: Max W. Y. Lam (maxingaussian@gmail.com)
################################################################################

try:
    from TLGProb import TLGProb
except:
    print("TLGProb is not installed yet! Trying to call directly from source...")
    from sys import path
    path.append("../")
    from TLGProb import TLGProb
    print("done.")

def performance_given_threshold(res, thre):
    corr, incorr, rej = 0, 0, 0
    for prob, corr_pred, y_pred, y_true in res:
        if(prob > thre):
            if(corr_pred):
                corr += 1
            else:
                incorr += 1
        else:
            rej += 1
    return corr, incorr, rej

TLGProb_NBA = TLGProb()
TLGProb_NBA.load_data()
res = TLGProb_NBA.eval_accuracy(2019)

## Visualize Result of Evaluation
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
n = len(res)
thres, corrs, incorrs = [], [], []
line_x, line_y, line_z = [], [], []
for i in range(501):
    thre = 0.5+i*1./1000
    line_x.append(thre)
    corr, incorr, rej = performance_given_threshold(res, thre)
    acc = 100 if corr+incorr == 0 else corr*100./(corr+incorr)
    thres.append(thre)
    corrs.append(corr)
    incorrs.append(incorr)
    line_y.append(acc)
    rejp = rej*100./n
    line_z.append(rejp)
fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
ax.stackplot(thres, [incorrs, corrs], colors=["red", "green"], alpha=0.5)
ax.set_xlim([0.5, 1])
plt.xlabel("Acceptance Threshold of Winning Probability", fontsize=18)
plt.ylabel("Number of Matches", fontsize=18)
p1 = Rectangle((0, 0), 1, 1, fc="green", alpha=0.5)
p2 = Rectangle((0, 0), 1, 1, fc="red", alpha=0.5)
plt.legend([p1, p2], ['Correct Prediction', 'Incorrect Prediction'], prop={'size':15})
plt.tight_layout(True)
fig.savefig('../correct_vs_incorrect.eps')
fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
ax.plot(line_x, line_y, 'b-', label="Accuracy")
plt.xlim([0.5, 1.0])
plt.ylim([line_y[0], 100.])
plt.xlabel("Acceptance Threshold of Winning Probability", fontsize=18)
plt.ylabel("Accuracy (%)", fontsize=18)
plt.tight_layout(True)
fig.savefig('../accuracy.eps')
fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
ax.plot(line_x, line_z, 'r--', label="Rejection percentage")
plt.xlim([0.5, 1.0])
plt.ylim([0., 100.])
plt.xlabel("Acceptance Threshold of Winning Probability", fontsize=18)
plt.ylabel("Rejection Percentage (%)", fontsize=18)
plt.tight_layout(True)
fig.savefig('../rejection.eps')
fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 8), dpi=300)
ax[0].stackplot(line_x, line_y, colors=['blue'], alpha=0.5)
ax[0].set_xlim([0.5, 1.0])
ax[0].set_ylim([line_y[0], 100.])
ax[0].set_ylabel("Accuracy (%)", fontsize=18)
ax[1].stackplot(line_x, line_z, colors=['red'], alpha=0.5)
ax[1].set_xlim([0.5, 1.0])
ax[1].set_ylim([0., 100.])
ax[1].set_xlabel("Acceptance Threshold of Winning Probability", fontsize=18)
ax[1].set_ylabel("Rejection Percentage (%)", fontsize=18)
plt.tight_layout(True)
fig.savefig('../accuracy_vs_rejection.eps')