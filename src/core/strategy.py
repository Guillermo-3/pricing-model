import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt
import lightgbm as lgb
def load_and_merge_data(market_path: str, quotes_path: str) -> pd.DataFrame:
    """
    Loads and merges market (target) and quote (feature) data.
    """
    market = pd.read_json(market_path, lines=True)
    market['ts'] = pd.to_datetime(market['t_log_ns'], unit='ns')
    
    quotes = pd.read_json(quotes_path, lines=True)
    quotes['ts'] = pd.to_datetime(quotes['t_log_ns'], unit='ns')

    df = pd.merge_asof(
        market.sort_values('ts'),
        quotes.sort_values('ts'),
        on='ts',
        by='symbol',
        direction='backward', 
        suffixes=('_mkt','_qt')
    )
    return df

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes features, the primary target, and the sensor target.
    - Primary Target (y): Next-tick mid-price return from the market data.
    - Sensor Target (z): Next-tick L5 imbalance from the quote data.
    """
    df['mid_price'] = df['mid_mkt']
    df['spread'] = df['ask_mkt'] - df['bid_mkt']

    df['y_target'] = df['mid_price'].pct_change().shift(-1)

    df['imbalance5'] = df['imbalance5']

    df['z_target'] = df['imbalance5'].shift(-1)

    df['date'] = df['ts'].dt.date
    final_cols = ['ts', 'date', 'mid_price', 'spread', 'imbalance5', 'y_target', 'z_target']
    return df[final_cols].dropna().reset_index(drop=True)

def train_augmented_model(train_df: pd.DataFrame, test_df: pd.DataFrame, features: list):
    """
    Trains the two-stage augmented model using LightGBM and returns predictions.
    """
    print("\n--- Training with LightGBM ---")
    X_train = train_df[features].values
    y_train = train_df['y_target'].values
    z_train = train_df['z_target'].values
    X_test = test_df[features].values
    y_test = test_df['y_target'].values

   
    lgbm_params = {
        'objective': 'regression_l1', 
        'metric': 'rmse',
        'n_estimators': 1000,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 1,
        'lambda_l1': 0.1,
        'lambda_l2': 0.1,
        'num_leaves': 31,
        'verbose': -1,
        'n_jobs': -1,
        'seed': 42,
        'boosting_type': 'gbdt',
    }


    f_model = lgb.LGBMRegressor(**lgbm_params)
    f_model.fit(X_train, y_train,
                eval_set=[(X_test, y_test)],
                eval_metric='rmse',
                callbacks=[lgb.early_stopping(100, verbose=False)])
    f_pred_train = f_model.predict(X_train)
    f_pred_test = f_model.predict(X_test)

  
    g_model = lgb.LGBMRegressor(**lgbm_params)
    g_model.fit(X_train, z_train) 
    s_train = g_model.predict(X_train)
    s_test = g_model.predict(X_test)

  
    y_residuals = y_train - f_pred_train
    z_residuals = z_train - s_train
   
    beta_model = LinearRegression(fit_intercept=False).fit(z_residuals.reshape(-1, 1), y_residuals)
    beta = beta_model.coef_[0]

    
    y_pred_augmented = f_pred_test + beta * s_test

    
    metrics = pd.DataFrame({
        'Model': ['Direct f(X)', 'Augmented f(X) + β*s'],
        'MSE': [mean_squared_error(y_test, f_pred_test), mean_squared_error(y_test, y_pred_augmented)],
        'R2': [r2_score(y_test, f_pred_test), r2_score(y_test, y_pred_augmented)]
    })

    print(f"\nLearned Augmentation Coefficient (β): {beta:.4f}")
    print("\n--- Model Performance ---")
    print(metrics)
    
    return y_pred_augmented, s_test, metrics

def plot_pnl_backtest(test_df: pd.DataFrame, predictions: np.ndarray):
    """Simple sign-based PnL backtest visualization."""
    pnl_df = test_df.copy()
    pnl_df['signal'] = np.sign(predictions)
    pnl_df['pnl'] = pnl_df['signal'] * pnl_df['y_target']
    pnl_df['cumulative_pnl'] = pnl_df['pnl'].cumsum()
    
    plt.figure(figsize=(12, 5))
    plt.plot(pnl_df['ts'], pnl_df['cumulative_pnl'])
    plt.title('Strategy PnL Backtest (Augmented Model)')
    plt.xlabel('Time')
    plt.ylabel('Cumulative PnL')
    plt.grid(True)
    plt.show()

def plot_sensor_calibration(sensor_values: np.ndarray, realized_returns: np.ndarray, n_bins: int = 20):
    """Bins sensor values and plots average realized return per bin to check calibration."""
    calib_df = pd.DataFrame({'sensor': sensor_values, 'realized': realized_returns})
    calib_df['bin'] = pd.qcut(calib_df['sensor'], q=n_bins, duplicates='drop', labels=False)
    binned_data = calib_df.groupby('bin')[['sensor', 'realized']].mean()
    
    plt.figure(figsize=(10, 5))
    plt.plot(binned_data['sensor'], binned_data['realized'], marker='o', linestyle='-')
    plt.title('Sensor Calibration Plot')
    plt.xlabel('Predicted Imbalance (Sensor Value)')
    plt.ylabel('Average Realized Mid-Price Return')
    plt.grid(True)
    plt.show()

def main():
    """Main execution workflow."""


    QUOTES_PATH = "logs/quotes_20250730.jsonl"
    MARKET_PATH = "logs/market_data_20250730.jsonl"


    try:
        df = load_and_merge_data(MARKET_PATH, QUOTES_PATH)
        df = feature_engineering(df)
        print(f"Loaded and processed {len(df)} aligned data points.")
    except FileNotFoundError:
        print(f"Error: Data file not found. Please check your path: {MARKET_PATH} or {QUOTES_PATH}")
        return
    except ValueError as e:
        print(f"ValueError: Your JSON file might be empty or malformed. Error: {e}")
        return
    
    if df.empty:
        print("Error: No data available after processing. Check your input files and merge logic.")
        return

 
    train_size = int(len(df) * 0.7)
    
    if train_size < 1:
        print("Error: Dataset is too small to create a training set.")
        return

    train_df = df.iloc[:train_size]
    test_df = df.iloc[train_size:]

    print(f"Splitting data by time: {len(train_df)} training points and {len(test_df)} testing points.")


    features = ['spread', 'imbalance5']
    predictions, sensor_output, _ = train_augmented_model(train_df, test_df, features)

    plot_sensor_calibration(sensor_output, test_df['y_target'].values)
    plot_pnl_backtest(test_df, predictions)

if __name__ == '__main__':
    main()