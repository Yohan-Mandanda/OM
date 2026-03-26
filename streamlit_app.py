from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from om_eticket_downloader import load_accounts_from_file, run_eticket_downloads


st.set_page_config(page_title="Ticketing Analyst Workspace", page_icon="🎫", layout="wide")


COLUMN_ALIASES: Dict[str, List[str]] = {
    "event_date": ["event_date", "date", "show_date", "event day", "jour evenement"],
    "event_name": ["event_name", "event", "show_name", "match", "nom evenement"],
    "city": ["city", "ville", "location"],
    "channel": ["channel", "sales_channel", "source", "canal"],
    "tickets_sold": ["tickets_sold", "sold_tickets", "tickets", "billets_vendus"],
    "capacity": ["capacity", "venue_capacity", "places_disponibles", "capacite"],
    "avg_ticket_price": [
        "avg_ticket_price",
        "ticket_price",
        "average_ticket_price",
        "prix_moyen",
        "price",
    ],
    "gross_revenue": ["gross_revenue", "revenue", "sales", "turnover", "ca"],
    "refunds_amount": ["refunds_amount", "refunds", "remboursements"],
    "marketing_spend": ["marketing_spend", "ads_spend", "marketing_cost", "pub", "acquisition_cost"],
    "venue_cost": ["venue_cost", "location_cost", "stadium_cost"],
    "artist_fee": ["artist_fee", "talent_fee", "lineup_cost", "speaker_fee"],
    "operational_cost": ["operational_cost", "staff_cost", "security_cost", "ops_cost"],
    "total_cost": ["total_cost", "event_cost", "cost", "total_expense"],
    "profit": ["profit", "net_profit", "marge"],
    "roi_pct": ["roi", "roi_pct", "return_on_investment", "return"],
    "social_mentions": ["social_mentions", "social_volume", "mentions"],
    "weather_score": ["weather_score", "meteo_score", "weather_index"],
}

NUMERIC_COLUMNS = [
    "tickets_sold",
    "capacity",
    "avg_ticket_price",
    "gross_revenue",
    "refunds_amount",
    "marketing_spend",
    "venue_cost",
    "artist_fee",
    "operational_cost",
    "total_cost",
    "profit",
    "roi_pct",
    "social_mentions",
    "weather_score",
]


def _normalize_header(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("-", " ").replace("_", " ").split())


def _format_currency(value: float) -> str:
    return f"${value:,.0f}"


def _clean_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace({"": np.nan, "nan": np.nan, "None": np.nan})
    cleaned = cleaned.str.replace(r"[^\d,.\-]", "", regex=True)

    has_dot = cleaned.str.contains(r"\.", regex=True, na=False).any()
    has_comma = cleaned.str.contains(",", regex=False, na=False).any()

    if has_comma and not has_dot:
        cleaned = cleaned.str.replace(",", ".", regex=False)
    else:
        cleaned = cleaned.str.replace(",", "", regex=False)

    return pd.to_numeric(cleaned, errors="coerce")


def _auto_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_lookup = {_normalize_header(col): col for col in df.columns}
    rename_map = {}
    for canonical_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            matching_original = normalized_lookup.get(_normalize_header(alias))
            if matching_original:
                rename_map[matching_original] = canonical_name
                break
    return df.rename(columns=rename_map)


def _load_sales_data(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(uploaded_file)
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file format. Use CSV or XLSX/XLSM.")


def _generate_demo_data(row_count: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    event_names = [
        "Summer Beats",
        "Urban Night",
        "Retro Festival",
        "Electro Dome",
        "Live Sessions",
        "City Arena Show",
    ]
    cities = ["Paris", "Lyon", "Marseille", "Lille", "Nantes", "Bordeaux"]
    channels = ["Online", "Partner", "Box Office", "Reseller"]

    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=row_count, freq="D")
    capacity = rng.integers(800, 10000, size=row_count)
    tickets_sold = (capacity * rng.uniform(0.4, 0.98, size=row_count)).astype(int)
    avg_price = rng.normal(52, 14, size=row_count).clip(12, 180)

    marketing_spend = rng.uniform(1500, 30000, size=row_count)
    venue_cost = rng.uniform(4000, 35000, size=row_count)
    artist_fee = rng.uniform(6000, 60000, size=row_count)
    operational_cost = rng.uniform(1200, 14000, size=row_count)
    refunds_amount = tickets_sold * avg_price * rng.uniform(0.01, 0.08, size=row_count)
    social_mentions = rng.integers(800, 70000, size=row_count)
    weather_score = rng.uniform(0.1, 1.0, size=row_count)

    gross_revenue = tickets_sold * avg_price
    total_cost = marketing_spend + venue_cost + artist_fee + operational_cost
    profit = (
        gross_revenue
        - refunds_amount
        - total_cost
        + 0.03 * social_mentions
        + 1800 * (weather_score - 0.5)
    )
    roi_pct = np.where(total_cost > 0, (profit / total_cost) * 100, np.nan)

    return pd.DataFrame(
        {
            "event_date": dates,
            "event_name": rng.choice(event_names, size=row_count),
            "city": rng.choice(cities, size=row_count),
            "channel": rng.choice(channels, size=row_count, p=[0.56, 0.2, 0.14, 0.1]),
            "tickets_sold": tickets_sold,
            "capacity": capacity,
            "avg_ticket_price": avg_price,
            "gross_revenue": gross_revenue,
            "refunds_amount": refunds_amount,
            "marketing_spend": marketing_spend,
            "venue_cost": venue_cost,
            "artist_fee": artist_fee,
            "operational_cost": operational_cost,
            "total_cost": total_cost,
            "social_mentions": social_mentions,
            "weather_score": weather_score,
            "profit": profit,
            "roi_pct": roi_pct,
        }
    )


def _prepare_sales_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    df = _auto_rename_columns(df)

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = _clean_numeric(df[col])

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    else:
        # Fallback to synthetic chronology so users can still inspect trends.
        df["event_date"] = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(df), freq="D")

    if "event_name" not in df.columns:
        df["event_name"] = [f"Event {idx + 1}" for idx in range(len(df))]
    if "city" not in df.columns:
        df["city"] = "Unknown"
    if "channel" not in df.columns:
        df["channel"] = "Unknown"

    if "gross_revenue" not in df.columns and {"tickets_sold", "avg_ticket_price"}.issubset(df.columns):
        df["gross_revenue"] = df["tickets_sold"] * df["avg_ticket_price"]
    if "refunds_amount" not in df.columns:
        df["refunds_amount"] = 0.0

    if "total_cost" not in df.columns:
        cost_parts = [c for c in ["marketing_spend", "venue_cost", "artist_fee", "operational_cost"] if c in df.columns]
        if cost_parts:
            df["total_cost"] = df[cost_parts].fillna(0).sum(axis=1)

    if "profit" not in df.columns and {"gross_revenue", "refunds_amount", "total_cost"}.issubset(df.columns):
        df["profit"] = df["gross_revenue"] - df["refunds_amount"] - df["total_cost"]

    if "roi_pct" not in df.columns and {"profit", "total_cost"}.issubset(df.columns):
        df["roi_pct"] = np.where(df["total_cost"] > 0, (df["profit"] / df["total_cost"]) * 100, np.nan)

    if "fill_rate" not in df.columns and {"tickets_sold", "capacity"}.issubset(df.columns):
        df["fill_rate"] = np.where(df["capacity"] > 0, df["tickets_sold"] / df["capacity"], np.nan)

    df = df.sort_values("event_date").reset_index(drop=True)
    return df


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    filtered = df.copy()

    if "event_date" in filtered.columns and filtered["event_date"].notna().any():
        min_date = filtered["event_date"].dropna().min().date()
        max_date = filtered["event_date"].dropna().max().date()
        date_range = st.sidebar.date_input("Event date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered = filtered[
                (filtered["event_date"].dt.date >= start_date) & (filtered["event_date"].dt.date <= end_date)
            ]

    for col in ["city", "channel", "event_name"]:
        if col in filtered.columns:
            options = sorted(filtered[col].dropna().astype(str).unique().tolist())
            selected = st.sidebar.multiselect(col.replace("_", " ").title(), options=options, default=options)
            if selected:
                filtered = filtered[filtered[col].astype(str).isin(selected)]

    return filtered


def _render_kpis(df: pd.DataFrame) -> None:
    total_revenue = float(df["gross_revenue"].sum()) if "gross_revenue" in df.columns else 0.0
    total_profit = float(df["profit"].sum()) if "profit" in df.columns else 0.0
    avg_roi = float(df["roi_pct"].mean()) if "roi_pct" in df.columns else np.nan
    tickets = float(df["tickets_sold"].sum()) if "tickets_sold" in df.columns else 0.0
    avg_fill_rate = float(df["fill_rate"].mean() * 100) if "fill_rate" in df.columns else np.nan

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Revenue", _format_currency(total_revenue))
    c2.metric("Total Profit", _format_currency(total_profit))
    c3.metric("Average ROI", f"{avg_roi:.1f}%" if pd.notna(avg_roi) else "N/A")
    c4.metric("Tickets Sold", f"{tickets:,.0f}")
    c5.metric("Average Fill Rate", f"{avg_fill_rate:.1f}%" if pd.notna(avg_fill_rate) else "N/A")


def _render_charts(df: pd.DataFrame) -> None:
    st.subheader("Performance Trends")
    left, right = st.columns(2)

    if {"event_date", "gross_revenue", "profit"}.issubset(df.columns):
        trend_df = (
            df.dropna(subset=["event_date"])
            .groupby(pd.Grouper(key="event_date", freq="W"), as_index=False)[["gross_revenue", "profit"]]
            .sum()
        )
        fig_trend = px.line(
            trend_df,
            x="event_date",
            y=["gross_revenue", "profit"],
            labels={"value": "Amount", "event_date": "Week", "variable": "Metric"},
            title="Weekly Revenue vs Profit",
        )
        left.plotly_chart(fig_trend, use_container_width=True)

    if {"event_name", "roi_pct"}.issubset(df.columns):
        roi_rank = (
            df.groupby("event_name", as_index=False)["roi_pct"]
            .mean()
            .sort_values("roi_pct", ascending=False)
            .head(12)
        )
        fig_roi = px.bar(
            roi_rank,
            x="event_name",
            y="roi_pct",
            title="Top Events by Average ROI (%)",
            labels={"roi_pct": "ROI (%)", "event_name": "Event"},
        )
        right.plotly_chart(fig_roi, use_container_width=True)

    c1, c2 = st.columns(2)
    if {"marketing_spend", "gross_revenue", "roi_pct"}.issubset(df.columns):
        scatter = px.scatter(
            df,
            x="marketing_spend",
            y="gross_revenue",
            color="roi_pct",
            hover_data=["event_name", "city", "channel"],
            title="Marketing Spend vs Revenue (colored by ROI)",
            color_continuous_scale="Viridis",
        )
        c1.plotly_chart(scatter, use_container_width=True)

    corr_inputs = [
        col
        for col in [
            "tickets_sold",
            "capacity",
            "avg_ticket_price",
            "gross_revenue",
            "marketing_spend",
            "venue_cost",
            "artist_fee",
            "operational_cost",
            "social_mentions",
            "weather_score",
            "profit",
            "roi_pct",
        ]
        if col in df.columns
    ]
    if len(corr_inputs) >= 2:
        corr = df[corr_inputs].corr(numeric_only=True)
        fig_corr = px.imshow(
            corr,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale="RdBu",
            zmin=-1,
            zmax=1,
            title="Factor Correlation Matrix",
        )
        c2.plotly_chart(fig_corr, use_container_width=True)


def _render_roi_prediction(df: pd.DataFrame) -> None:
    st.subheader("ROI Prediction Model")

    if "roi_pct" not in df.columns or df["roi_pct"].notna().sum() < 12:
        st.info("Not enough ROI history to train a model. Provide at least 12 rows with ROI/cost data.")
        return

    feature_pool = [
        "tickets_sold",
        "capacity",
        "avg_ticket_price",
        "marketing_spend",
        "venue_cost",
        "artist_fee",
        "operational_cost",
        "refunds_amount",
        "social_mentions",
        "weather_score",
    ]
    features = [col for col in feature_pool if col in df.columns and df[col].notna().sum() >= 8]
    if len(features) < 2:
        st.info("Not enough input factors to train ROI prediction. Include at least two numeric factor columns.")
        return

    train_df = df[features + ["roi_pct"]].dropna(subset=["roi_pct"])
    if len(train_df) < 12:
        st.info("Not enough cleaned rows after preprocessing to train the model.")
        return

    X = train_df[features]
    y = train_df["roi_pct"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("regressor", LinearRegression()),
        ]
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    m1, m2 = st.columns(2)
    m1.metric("Model R²", f"{r2_score(y_test, y_pred):.3f}")
    m2.metric("Model MAE", f"{mean_absolute_error(y_test, y_pred):.2f} ROI pts")

    coefficients = pd.DataFrame(
        {"feature": features, "coefficient": model.named_steps["regressor"].coef_}
    ).assign(abs_coefficient=lambda d: d["coefficient"].abs())
    coef_fig = px.bar(
        coefficients.sort_values("abs_coefficient", ascending=False),
        x="feature",
        y="coefficient",
        title="Model Factor Impact (Linear Coefficients)",
    )
    st.plotly_chart(coef_fig, use_container_width=True)

    st.markdown("#### Predict ROI for a new event scenario")
    scenario = {}
    with st.form("roi_scenario_form"):
        form_cols = st.columns(2)
        for idx, feature in enumerate(features):
            default_value = float(train_df[feature].median()) if train_df[feature].notna().any() else 0.0
            scenario[feature] = form_cols[idx % 2].number_input(
                feature.replace("_", " ").title(),
                value=default_value,
                step=1.0,
            )
        submitted = st.form_submit_button("Predict Event ROI")

    if submitted:
        scenario_df = pd.DataFrame([scenario])
        predicted_roi = float(model.predict(scenario_df)[0])
        st.success(f"Predicted ROI: {predicted_roi:.2f}%")

        if {"tickets_sold", "avg_ticket_price"}.issubset(scenario):
            scenario_revenue = scenario["tickets_sold"] * scenario["avg_ticket_price"]
            cost_columns = [c for c in ["marketing_spend", "venue_cost", "artist_fee", "operational_cost"] if c in scenario]
            scenario_cost = float(sum(scenario[c] for c in cost_columns))
            if scenario_cost > 0:
                projected_profit = (predicted_roi / 100.0) * scenario_cost
                formula_roi = ((scenario_revenue - scenario_cost) / scenario_cost) * 100
                p1, p2, p3 = st.columns(3)
                p1.metric("Scenario Revenue", _format_currency(scenario_revenue))
                p2.metric("Scenario Cost", _format_currency(scenario_cost))
                p3.metric("Model-Projected Profit", _format_currency(projected_profit))
                st.caption(
                    f"Simple formula ROI from provided revenue/cost inputs: {formula_roi:.2f}% "
                    "(model ROI can differ because it learns historical factor patterns)."
                )


def _render_sales_dashboard() -> None:
    st.title("Ticketing Sales Analytics & ROI Dashboard")
    st.caption("Analyze event performance, identify ROI drivers, and forecast return on future events.")

    sample_template = _generate_demo_data(5)
    st.download_button(
        "Download CSV template",
        data=sample_template.to_csv(index=False).encode("utf-8"),
        file_name="ticketing_sales_template.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("Upload your sales dataset (CSV or XLSX)", type=["csv", "xlsx", "xlsm"])
    use_demo = st.toggle("Use demo data", value=uploaded is None)

    try:
        if uploaded is not None and not use_demo:
            raw_df = _load_sales_data(uploaded)
        elif uploaded is not None and use_demo:
            raw_df = _generate_demo_data(180)
        elif use_demo:
            raw_df = _generate_demo_data(180)
        else:
            st.info("Upload a file or enable demo data to start.")
            return
    except Exception as exc:
        st.error(f"Could not parse input data: {exc}")
        return

    df = _prepare_sales_data(raw_df)
    if df.empty:
        st.warning("No rows available after preprocessing.")
        return

    filtered = _apply_filters(df)
    if filtered.empty:
        st.warning("No data matches the selected filters.")
        return

    _render_kpis(filtered)
    _render_charts(filtered)
    _render_roi_prediction(filtered)

    with st.expander("View cleaned dataset"):
        st.dataframe(filtered, use_container_width=True)
        st.download_button(
            "Download cleaned data",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="cleaned_ticketing_sales_data.csv",
            mime="text/csv",
        )


def _render_downloader_ui() -> None:
    st.title("OM E-Ticket Downloader")
    st.caption("Automate login + e-ticket download for multiple OM billetterie accounts.")

    with st.form("run_form"):
        spreadsheet = st.file_uploader("Accounts file (CSV or XLSX)", type=["csv", "xlsx", "xlsm"])
        match_name = st.text_input("Match to download", placeholder="Ex: Lille, Auxerre, Metz")
        output_dir = st.text_input("Output folder", value="downloads")
        headless = st.checkbox("Headless mode", value=False)
        login_wait_seconds = st.number_input(
            "Max wait for login / captcha solve (seconds)",
            min_value=30,
            max_value=600,
            value=120,
            step=15,
        )
        slow_mo_ms = st.number_input(
            "Slow motion per browser action (ms)",
            min_value=0,
            max_value=2000,
            value=0,
            step=50,
        )
        submitted = st.form_submit_button("Start download")

    if not submitted:
        return

    if spreadsheet is None:
        st.error("Please upload a CSV or XLSX file first.")
        return

    if not match_name.strip():
        st.error("Please enter the match name.")
        return

    logs_placeholder = st.empty()
    live_logs = []

    def log(msg: str) -> None:
        live_logs.append(msg)
        logs_placeholder.code("\n".join(live_logs[-25:]), language="text")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(spreadsheet.name).suffix) as tmp:
        tmp.write(spreadsheet.getbuffer())
        tmp_path = Path(tmp.name)

    try:
        accounts = load_accounts_from_file(tmp_path)
    except Exception as exc:
        st.error(f"Could not read account file: {exc}")
        return
    finally:
        tmp_path.unlink(missing_ok=True)

    if not accounts:
        st.warning("No valid accounts found (need email + password for each row).")
        return

    st.info(f"Loaded {len(accounts)} account(s). Running automation...")

    try:
        results = run_eticket_downloads(
            accounts=accounts,
            match_name=match_name.strip(),
            output_dir=Path(output_dir).expanduser(),
            headless=headless,
            login_wait_seconds=int(login_wait_seconds),
            slow_mo_ms=int(slow_mo_ms),
            progress_cb=log,
        )
    except Exception as exc:
        st.error(f"Automation crashed: {exc}")
        return

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    if success_count:
        st.success(f"{success_count} account(s) completed successfully.")
    if fail_count:
        st.error(f"{fail_count} account(s) failed.")

    for result in results:
        if result.success:
            st.write(f"✅ **{result.email}** — {len(result.saved_files)} file(s) downloaded")
            if result.saved_files:
                st.code("\n".join(str(p) for p in result.saved_files), language="text")
        else:
            st.write(f"❌ **{result.email}** — {result.error}")


st.sidebar.title("Ticketing Workspace")
workspace = st.sidebar.radio(
    "Module",
    options=["Sales analytics dashboard", "E-ticket downloader"],
    index=0,
)

if workspace == "Sales analytics dashboard":
    _render_sales_dashboard()
else:
    _render_downloader_ui()
