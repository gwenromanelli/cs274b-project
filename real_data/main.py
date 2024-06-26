from scipy import stats
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import torch
import os
import pyreadr
from sklearn.datasets import make_sparse_spd_matrix
import utils_mcf, utils_plot
import argparse

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--epochs', metavar='e', type=int, default=10_000,
                    help='number of epochs')
parser.add_argument('--seed', metavar='s', type=int, default=1234,
                    help='random seed')
parser.add_argument('--p_min', metavar='p_min', type=float, default=0.5,
                    help='p min')
parser.add_argument('--p_max', metavar='p_max', type=float, default=1.5,
                    help='p max')
parser.add_argument('--lambda_min', metavar='l_min', type=float, default=1.,
                    help='lambda min')
parser.add_argument('--lambda_max', metavar='l_max', type=float, default=2.,
                    help='lambda max')
parser.add_argument('--T0', metavar='T0', type=float, default=5.,
                    help='initial temperature')
parser.add_argument('--Tn', metavar='Tn', type=float, default=1., # set to 1e-2 to obtain MAP limit
                    help='final temperature')
parser.add_argument('--eval', action='store_true', default=False)

args = parser.parse_args()

def set_random_seeds (seed=1234):
    np.random.seed(seed)
    torch.manual_seed(seed)

def main():
    # set random seed for reproducibility
    set_random_seeds(args.seed)

    # load dataset
    df_X = pd.read_csv('./data/TCGA_small.csv')
    X = df_X.to_numpy()
    X = X[:,1:]

    # standardize dataset
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    n = X.shape[0]  # number of patients
    N = X.shape[1]  # total number of features
    P = 4  # clinical variables
    Q = N - P  # gene expression measurements
    print(f"The data consists of {P} clinical variables and {Q} gene expression measurements for {n} patients")
    S = np.cov(X, rowvar=False)

    # Flow Variational Inference for Bayesian GLASSO
    S_torch = torch.from_numpy(S).float().cuda()
    flow = utils_mcf.build_cond_psd_uncontrained_vector(P, Q, context_features=64, hidden_features=256, n_layers=10)

    # train model
    file_name = f'e{args.epochs}_pmin{args.p_min:.2f}_pmax{args.p_max:.2f}_lmin{args.lambda_min:.1f}_lmax{args.lambda_max:.1f}_seed{args.seed}_T{args.Tn:.3f}'
    if not args.eval:
        if os.path.isfile(f"./models/cmf_{file_name}"):
            flow.load_state_dict(torch.load(f"./models/cmf_{file_name}"))
        else:
            flow, loss, loss_T = utils_mcf.train_model(flow, S_torch, P, Q, n, p_min=args.p_min, p_max=args.p_max, lr=1e-3,
                                                       epochs=args.epochs, context_size=400, lambda_min_exp=args.lambda_min,
                                                       lambda_max_exp=args.lambda_max, T0=args.T0, Tn=args.Tn, iter_per_cool_step=100, file_name=file_name,)
            utils_plot.plot_loss (loss, loss_T)

    p_values = [1.0, 0.9, 0.8, 0.7, 0.6]
    if args.Tn == 1e-2: # plot MAP for different l_p norms
        for p_value in p_values:
            print(f"p = {p_value}")
            p = S_torch.new_ones(1) * p_value
            utils_plot.plot_full_comparison(flow, S=S_torch, P=P, Q=Q, n=n, T=args.Tn, p=p, lambda_min=args.lambda_min,
                                            lambda_max=args.lambda_max, file_name=file_name, plot_full_matrix=True, plot_mll=True)
    elif args.Tn == 1.:
            utils_plot.plot_credibility_interval(p_values, file_name, n=n, n_values=4)

if __name__ == "__main__":
    main()
