import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Sales Analysis Dashboard",
    page_icon="📊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = Path(
    os.getenv("SALES_DATA_PATH", str(BASE_DIR / "sales_dataset.csv"))
).expanduser()
REQUIRED_COLUMNS = {"order_id", "revenue"}
DATE_COLUMN = "_dashboard_order_date"
REVENUE_COLUMN = "_dashboard_revenue"
QUANTITY_COLUMN = "_dashboard_quantity"


@st.cache_data(show_spinner="Loading sales data...")
def load_dataset(file_path: str, modified_time: float) -> pd.DataFrame:
    del modified_time
    data = pd.read_csv(file_path)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing_columns:
        raise ValueError(
            "The CSV is missing required column(s): "
            + ", ".join(missing_columns)
            + ". Required for the dashboard: order_id and revenue."
        )

    data[REVENUE_COLUMN] = pd.to_numeric(data["revenue"], errors="coerce")
    if "quantity" in data:
        data[QUANTITY_COLUMN] = pd.to_numeric(data["quantity"], errors="coerce")
    if "order_date" in data:
        data[DATE_COLUMN] = pd.to_datetime(
            data["order_date"], errors="coerce", format="mixed"
        )
    return data


def currency(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${value:,.2f}"


st.title("Sales Analysis Dashboard")
st.caption(
    "Business overview of sales performance, product categories, markets, "
    "payment methods, and customers."
)

try:
    modified_time = DATA_PATH.stat().st_mtime
    data = load_dataset(str(DATA_PATH.resolve()), modified_time)
except FileNotFoundError:
    st.error(
        f"Sales data file not found: `{DATA_PATH}`. Place `sales_dataset.csv` "
        "next to this script or set the `SALES_DATA_PATH` environment variable."
    )
    st.stop()
except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
    st.error(f"Could not read the sales CSV at `{DATA_PATH}`: {error}")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

if data.empty:
    st.info("The sales dataset contains no records.")
    st.stop()

st.caption(f"Showing all {len(data):,} records from `{DATA_PATH.name}`.")

if "order_date" in data:
    valid_date_count = int(data[DATE_COLUMN].notna().sum())
    invalid_date_count = len(data) - valid_date_count
    if invalid_date_count:
        st.warning(
            f"{invalid_date_count:,} record(s) have missing or invalid order dates "
            "and are excluded from date-based charts."
        )
else:
    st.info("Sales trend charts are unavailable because the dataset has no order_date column.")

invalid_revenue_count = int(data[REVENUE_COLUMN].isna().sum())
if invalid_revenue_count:
    st.warning(
        f"{invalid_revenue_count:,} record(s) have missing or invalid revenue. "
        "They are excluded from revenue totals and charts."
    )

if QUANTITY_COLUMN in data:
    invalid_quantity_count = int(data[QUANTITY_COLUMN].isna().sum())
    if invalid_quantity_count:
        st.warning(
            f"{invalid_quantity_count:,} record(s) have missing or invalid quantity. "
            "They are excluded from the units-sold KPI."
        )

total_revenue = data[REVENUE_COLUMN].sum(min_count=1)
total_orders = int(data["order_id"].nunique())
average_order_value = (
    total_revenue / total_orders
    if total_orders and pd.notna(total_revenue)
    else float("nan")
)
total_units = (
    data[QUANTITY_COLUMN].sum(min_count=1)
    if QUANTITY_COLUMN in data
    else None
)

with st.container(border=True):
    st.subheader("Key performance indicators")
    primary_metrics = st.columns(4)
    primary_metrics[0].metric("Total revenue", currency(total_revenue))
    primary_metrics[1].metric("Total orders", f"{total_orders:,}")
    primary_metrics[2].metric("Average order value", currency(average_order_value))
    primary_metrics[3].metric(
        "Units sold",
        f"{total_units:,.0f}"
        if total_units is not None and pd.notna(total_units)
        else "N/A",
    )

    secondary_metrics = st.columns(3)
    if "customer_rating" in data:
        average_rating = pd.to_numeric(
            data["customer_rating"], errors="coerce"
        ).mean()
        secondary_metrics[0].metric(
            "Average customer rating",
            f"{average_rating:.2f} / 5" if pd.notna(average_rating) else "N/A",
        )
    if "discount" in data:
        average_discount = pd.to_numeric(data["discount"], errors="coerce").mean()
        secondary_metrics[1].metric(
            "Average discount",
            f"{average_discount:.1%}" if pd.notna(average_discount) else "N/A",
        )
    if "delivery_days" in data:
        average_delivery = pd.to_numeric(
            data["delivery_days"], errors="coerce"
        ).mean()
        secondary_metrics[2].metric(
            "Average delivery time",
            f"{average_delivery:.1f} days" if pd.notna(average_delivery) else "N/A",
        )

st.subheader("Sales trends")
if DATE_COLUMN in data and data[DATE_COLUMN].notna().any():
    dated_data = data.dropna(subset=[DATE_COLUMN]).copy()
    dated_data["_dashboard_month"] = (
        dated_data[DATE_COLUMN].dt.to_period("M").dt.to_timestamp()
    )
    monthly_revenue = (
        dated_data.groupby("_dashboard_month", as_index=False)[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna(subset=[REVENUE_COLUMN])
    )
    monthly_orders = (
        dated_data.groupby("_dashboard_month")["order_id"]
        .nunique()
        .rename("Orders")
        .reset_index()
    )

    trend_columns = st.columns(2)
    if not monthly_revenue.empty:
        revenue_chart = px.line(
            monthly_revenue,
            x="_dashboard_month",
            y=REVENUE_COLUMN,
            markers=True,
            title="Monthly revenue",
            labels={
                "_dashboard_month": "Month",
                REVENUE_COLUMN: "Revenue ($)",
            },
            template="plotly_white",
        )
        revenue_chart.update_yaxes(tickprefix="$", tickformat=",.0f")
        trend_columns[0].plotly_chart(revenue_chart, width="stretch")
    else:
        trend_columns[0].info("No valid revenue values are available for the trend.")

    order_chart = px.bar(
        monthly_orders,
        x="_dashboard_month",
        y="Orders",
        title="Monthly order volume",
        labels={"_dashboard_month": "Month"},
        template="plotly_white",
    )
    trend_columns[1].plotly_chart(order_chart, width="stretch")
else:
    st.info("No valid order dates are available for trend analysis.")

st.subheader("Revenue breakdown")
breakdown_columns = st.columns(2)

if "product_category" in data:
    category_data = data.assign(
        _dashboard_category=data["product_category"].fillna("(missing)")
    )
    category_revenue = (
        category_data.groupby("_dashboard_category")[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna()
        .sort_values()
        .rename("Revenue")
        .reset_index()
    )
    if not category_revenue.empty:
        category_chart = px.bar(
            category_revenue,
            x="Revenue",
            y="_dashboard_category",
            orientation="h",
            title="Revenue by product category",
            labels={"_dashboard_category": "Category"},
            template="plotly_white",
            color="Revenue",
            color_continuous_scale="Blues",
        )
        category_chart.update_xaxes(tickprefix="$", tickformat=",.0f")
        category_chart.update_layout(coloraxis_showscale=False)
        breakdown_columns[0].plotly_chart(category_chart, width="stretch")

if "region" in data:
    region_data = data.assign(
        _dashboard_region=data["region"].fillna("(missing)")
    )
    region_revenue = (
        region_data.groupby("_dashboard_region")[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna()
        .sort_values(ascending=False)
        .rename("Revenue")
        .reset_index()
    )
    if not region_revenue.empty:
        region_chart = px.bar(
            region_revenue,
            x="_dashboard_region",
            y="Revenue",
            title="Revenue by region",
            labels={"_dashboard_region": "Region"},
            template="plotly_white",
            color="Revenue",
            color_continuous_scale="Teal",
        )
        region_chart.update_yaxes(tickprefix="$", tickformat=",.0f")
        region_chart.update_layout(coloraxis_showscale=False)
        breakdown_columns[1].plotly_chart(region_chart, width="stretch")

additional_columns = st.columns(2)

if "payment_method" in data:
    payment_data = data.assign(
        _dashboard_payment_method=data["payment_method"].fillna("(missing)")
    )
    payment_revenue = (
        payment_data.groupby("_dashboard_payment_method")[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna()
        .rename("Revenue")
        .reset_index()
    )
    if not payment_revenue.empty:
        payment_chart = px.pie(
            payment_revenue,
            names="_dashboard_payment_method",
            values="Revenue",
            hole=0.48,
            title="Revenue mix by payment method",
            template="plotly_white",
        )
        payment_chart.update_layout(showlegend=True)
        additional_columns[0].plotly_chart(payment_chart, width="stretch")

if "customer_id" in data:
    customer_revenue = (
        data.groupby("customer_id")[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna()
        .nlargest(10)
        .sort_values()
        .rename("Revenue")
        .reset_index()
    )
    if not customer_revenue.empty:
        customer_chart = px.bar(
            customer_revenue,
            x="Revenue",
            y="customer_id",
            orientation="h",
            title="Top 10 customers by revenue",
            labels={"customer_id": "Customer ID"},
            template="plotly_white",
        )
        customer_chart.update_xaxes(tickprefix="$", tickformat=",.0f")
        additional_columns[1].plotly_chart(customer_chart, width="stretch")

st.subheader("Business insights")
insights: list[str] = []

if "product_category" in data:
    category_totals = data.groupby("product_category", dropna=False)[
        REVENUE_COLUMN
    ].sum(min_count=1).dropna()
    if not category_totals.empty:
        best_category = category_totals.idxmax()
        insights.append(
            f"**Top category:** {best_category} generated "
            f"{currency(category_totals.max())} in revenue."
        )

if "region" in data:
    region_totals = data.groupby("region", dropna=False)[REVENUE_COLUMN].sum(
        min_count=1
    ).dropna()
    if not region_totals.empty:
        best_region = region_totals.idxmax()
        insights.append(
            f"**Leading region:** {best_region} contributed "
            f"{currency(region_totals.max())} in revenue."
        )

if DATE_COLUMN in data and data[DATE_COLUMN].notna().any():
    monthly_totals = (
        data.dropna(subset=[DATE_COLUMN])
        .assign(
            _dashboard_month=lambda rows: rows[DATE_COLUMN]
            .dt.to_period("M")
            .dt.to_timestamp()
        )
        .groupby("_dashboard_month")[REVENUE_COLUMN]
        .sum(min_count=1)
        .dropna()
    )
    if not monthly_totals.empty:
        best_month = monthly_totals.idxmax().strftime("%B %Y")
        insights.append(
            f"**Highest-revenue month:** {best_month} "
            f"({currency(monthly_totals.max())})."
        )

if "payment_method" in data and pd.notna(total_revenue) and total_revenue > 0:
    payment_totals = data.groupby("payment_method", dropna=False)[
        REVENUE_COLUMN
    ].sum(min_count=1).dropna()
    if not payment_totals.empty:
        best_payment_method = payment_totals.idxmax()
        payment_share = payment_totals.max() / total_revenue
        insights.append(
            f"**Leading payment method:** {best_payment_method} accounted for "
            f"{payment_share:.1%} of revenue "
            f"({currency(payment_totals.max())})."
        )

if insights:
    for insight in insights:
        st.markdown(f"- {insight}")
else:
    st.info("There is not enough valid data to generate business insights.")

st.caption(
    "Order count uses distinct order IDs; average order value is total revenue "
    "divided by distinct orders. Profit and profit margin are not shown because "
    "the dataset has no cost or profit field."
)
