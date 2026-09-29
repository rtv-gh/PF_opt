# 🎯 Portfolio Optimizer

An interactive financial tool built in Python to demonstrate **Modern Portfolio Theory (MPT)** and **Efficient Frontier** optimization using real-market data.

## 🚀 Live Demo
streamlit run app/app.py

https://rtv-gh-port.streamlit.app/  <<-- added 15/02/2026

## 🛠️ The Financial Logic
This project uses **Mean-Variance Optimization** to solve for the "Optimal" portfolio weights. 

* **Data Source:** Real-time equity data via `yfinance`.
* **Risk Model:** Ledoit-Wolf shrinkage to estimate the covariance matrix, reducing noise in financial data.
* **Objective Function:** Maximizing the **Sharpe Ratio** ($S_p$):
  $$S_p = \frac{R_p - R_f}{\sigma_p}$$
  Where $R_p$ is the expected portfolio return, $R_f$ is the risk-free rate, and $\sigma_p$ is the portfolio volatility.

## 💻 Technical Stack
* **Python 3.13**
* **Streamlit**: For the interactive web interface.
* **PyPortfolioOpt**: For the quadratic programming optimization.
* **Plotly**: For dynamic data visualization and risk-return plots.

## Equity Markets
The sidebar supports USA and UK universes. UK constituents are sourced from the FTSE 100 and FTSE 250 constituent tables; Yahoo Finance sector and industry metadata is mapped to GICS sector names for the sector picker. The UK snapshot is fetched and cached on first selection. To refresh it manually, run `python -m utils.update_FTSE350_tickers`.

## 📂 Project Structure
- `app.py`: The Streamlit UI and user input handling.
- `backend.py`: The backend engine for data cleaning and optimization math.
- `requirements.txt`: Environment dependencies for cloud deployment.


## Future Enhancements
1) Currency conversion
2) Map tickers to issuer names
3) Output weights in table
4) Create precanned baskets of stocks

## 👤 Contact
[Robert Trenado-Valle] - [www.linkedin.com/in/robert-trenado-valle-56a77641]