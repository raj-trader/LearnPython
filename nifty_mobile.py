__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')   
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Mobile-optimized page configuration
st.set_page_config(
    page_title="Nifty Analyzer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Mobile CSS for better touch experience
st.markdown("""
<style>
    /* Better touch targets for mobile */
    .stButton button {
        min-height: 44px;
        font-size: 16px;
    }
    
    .stSelectbox div {
        font-size: 16px;
    }
    
    /* Improve tab touch area */
    .stTab label {
        padding: 12px 8px;
        font-size: 14px;
    }
    
    /* Better chart interaction */
    .js-plotly-plot .plotly .modebar {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Your existing database functions
def get_available_dates_from_db(db_path='nifty_data.db'):
    conn = sqlite3.connect(db_path)
    query = "SELECT DISTINCT date FROM ohlc_data ORDER BY date DESC"
    dates_df = pd.read_sql_query(query, conn)
    conn.close()
    
    available_dates = []
    for date_str in dates_df['date']:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        if date_obj.weekday() < 5:
            available_dates.append(date_obj)
    
    return available_dates

def get_daily_levels_from_db(date, db_path='nifty_data.db'):
    """Get daily levels for Nifty from database"""
    conn = sqlite3.connect(db_path)
    query = """
    SELECT level1, level2, level3, level4, level5, level6, level7, level8,
           level9, level10, level11, level12, level13, level14, diff
    FROM daily_levels 
    WHERE date = ? AND symbol = 'NIFTY'
    """
    result = pd.read_sql_query(query, conn, params=(date.strftime('%Y-%m-%d'),))
    conn.close()
    return result.iloc[0] if not result.empty else None

def get_option_levels_from_db(date, option_name, db_path='nifty_data.db'):
    """Get option levels for specific option from database"""
    conn = sqlite3.connect(db_path)
    query = """
    SELECT level1, level2, level3, level4, level5, level6, level7, level8,
           level9, level10, level11, level12, level13, level14, diff
    FROM option_levels 
    WHERE date = ? AND option_name = ?
    """
    result = pd.read_sql_query(query, conn, params=(date.strftime('%Y-%m-%d'), option_name))
    conn.close()
    return result.iloc[0] if not result.empty else None

def load_nifty_data_from_db(date, db_path='nifty_data.db'):
    conn = sqlite3.connect(db_path)
    query = "SELECT timestamp, datetime, date, open, high, low, close, volume FROM ohlc_data WHERE date = ? ORDER BY timestamp"
    nifty_df = pd.read_sql_query(query, conn, params=(date.strftime('%Y-%m-%d'),))
    conn.close()
    
    if not nifty_df.empty:
        nifty_df['datetime'] = pd.to_datetime(nifty_df['datetime'])
        
        # Load levels for Nifty
        daily_levels = get_daily_levels_from_db(date, db_path)
        if daily_levels is not None:
            level_cols = ['level1', 'level2', 'level3', 'level4', 'level5', 'level6', 'level7', 
                         'level8', 'level9', 'level10', 'level11', 'level12', 'level13', 'level14']
            for i, col in enumerate(level_cols):
                nifty_df[col] = daily_levels[i]
            nifty_df['diff'] = daily_levels['diff']
    
    return nifty_df if not nifty_df.empty else None

def load_options_data_from_db(date, db_path='nifty_data.db'):
    conn = sqlite3.connect(db_path)
    query = "SELECT option_name, timestamp, datetime, date, open, high, low, close, vwap, volume FROM options_data WHERE date = ? ORDER BY option_name, timestamp"
    options_df = pd.read_sql_query(query, conn, params=(date.strftime('%Y-%m-%d'),))
    conn.close()
    
    if not options_df.empty:
        options_df['datetime'] = pd.to_datetime(options_df['datetime'])
        options_data = {}
        for option_name, group in options_df.groupby('option_name'):
            # Load levels for each option
            option_levels = get_option_levels_from_db(date, option_name, db_path)
            if option_levels is not None:
                level_cols = ['level1', 'level2', 'level3', 'level4', 'level5', 'level6', 'level7', 
                             'level8', 'level9', 'level10', 'level11', 'level12', 'level13', 'level14']
                for i, col in enumerate(level_cols):
                    group[col] = option_levels[i]
                group['diff'] = option_levels['diff']
            
            options_data[option_name] = group
        return options_data
    return {}

def identify_call_put_options(options_data):
    call_options = {}
    put_options = {}
    
    for option_name, option_data in options_data.items():
        option_upper = option_name.upper()
        if any(pattern in option_upper for pattern in ['CE', 'CALL', 'C']):
            call_options[option_name] = option_data
        elif any(pattern in option_upper for pattern in ['PE', 'PUT', 'P']):
            put_options[option_name] = option_data
    
    return call_options, put_options

# EXACT SAME CHART FUNCTION AS DESKTOP VERSION (just with mobile height)
def create_tradingview_chart(data, title, show_levels=True, risk_value=None, height=500):
    """Create a TradingView-style chart without volume but with VWAP indicators"""
    # Light theme colors
    bg_color = "white"
    grid_color = "#E5ECF6"
    text_color = "black"
    candle_increasing_color = "#26a69a"
    candle_decreasing_color = "#ef5350"

    fig = go.Figure()

    # Add candlestick chart
    candlestick = go.Candlestick(
        x=data['datetime'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='Price',
        increasing_line_color=candle_increasing_color,
        decreasing_line_color=candle_decreasing_color,
        increasing_fillcolor=candle_increasing_color,
        decreasing_fillcolor=candle_decreasing_color,
    )

    fig.add_trace(candlestick)

    # Calculate VWAP with low as source
    if 'volume' in data.columns and 'low' in data.columns:
        # VWAP with low as source
        data['typical_price_low'] = (data['low'] + data['low'] + data['close']) / 3  # Using low twice to emphasize low
        data['cumulative_typical_volume_low'] = (data['typical_price_low'] * data['volume']).cumsum()
        data['cumulative_volume'] = data['volume'].cumsum()
        data['vwap_low'] = data['cumulative_typical_volume_low'] / data['cumulative_volume']

        # Add VWAP low line
        vwap_low_line = go.Scatter(
            x=data['datetime'],
            y=data['vwap_low'],
            name='VWAP (Low Source)',
            line=dict(color='#FF6B9D', width=1),
            opacity=0.8
        )
        fig.add_trace(vwap_low_line)

    # Calculate VWAP with high as source
    if 'volume' in data.columns and 'high' in data.columns:
        # VWAP with high as source
        data['typical_price_high'] = (data['high'] + data['high'] + data['close']) / 3  # Using high twice to emphasize high
        data['cumulative_typical_volume_high'] = (data['typical_price_high'] * data['volume']).cumsum()
        data['vwap_high'] = data['cumulative_typical_volume_high'] / data['cumulative_volume']

        # Add VWAP high line
        vwap_high_line = go.Scatter(
            x=data['datetime'],
            y=data['vwap_high'],
            name='VWAP (High Source)',
            line=dict(color='#4ECDC4', width=1),
            opacity=0.8
        )
        fig.add_trace(vwap_high_line)

    # Set the x-axis range to start at 9:15 and end at 15:30
    start_time = pd.Timestamp(data['datetime'].iloc[0].date()).replace(hour=9, minute=15, second=0)
    end_time = pd.Timestamp(data['datetime'].iloc[0].date()).replace(hour=15, minute=30, second=0)

    # Calculate y-axis range
    price_min = data['low'].min()
    price_max = data['high'].max()

    # Include VWAP values in y-axis range calculation if they exist
    if 'vwap_low' in data.columns:
        price_min = min(price_min, data['vwap_low'].min())
        price_max = max(price_max, data['vwap_low'].max())
    if 'vwap_high' in data.columns:
        price_min = min(price_min, data['vwap_high'].min())
        price_max = max(price_max, data['vwap_high'].max())

    padding = (price_max - price_min) * 0.05
    y_range = [price_min - padding, price_max + padding]

    # Update title to include risk value if provided
    if risk_value is not None:
        title = f"{title} (Risk: {risk_value})"

    # Update layout for TradingView style
    layout_updates = dict(
        title=title,
        xaxis_title=None,
        yaxis_title=None,
        xaxis_rangeslider_visible=False,
        height=height,
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font_color=text_color,
        xaxis=dict(
            showgrid=False,
            gridwidth=1,
            gridcolor=grid_color,
            rangeslider=dict(visible=False),
            range=[start_time, end_time]
        ),
        yaxis=dict(
            showgrid=False,
            gridwidth=1,
            gridcolor=grid_color,
            type="linear",
            range=y_range
        ),
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        dragmode="pan"
    )

    fig.update_layout(**layout_updates)

    # Format x-axis to show time only
    fig.update_xaxes(tickformat="%H:%M")

    # Add levels if enabled and available
    level_cols = ['level1', 'level2', 'level3', 'level4', 'level5', 'level6', 'level7',
                  'level8', 'level9', 'level10', 'level11', 'level12', 'level13', 'level14']

    if show_levels and all(col in data.columns for col in level_cols) and not pd.isna(data[level_cols].iloc[0]).any():
        # Define colors for all 14 levels
        level_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF',
            '#5F27CD', '#FF9F43', '#10AC84', '#EE5A24', '#0652DD', '#EA2027', '#A3CB38'
        ]

        for i, col in enumerate(level_cols):
            if col in data.columns and i < len(data[level_cols].iloc[0]):  # Check if level exists in data
                level_value = int(data[col].iloc[0])
                fig.add_hline(
                    y=level_value,
                    line_dash="solid",
                    line_color=level_colors[i],
                    line_width=1,
                    annotation_text=level_value,
                    annotation_position="right",
                    annotation_font_size=10,
                    opacity=0.8
                )

    return fig

# Main app
def main():
    # Database configuration
    DB_FILE_PATH = "nifty_data.db"
    
    try:
        available_dates = get_available_dates_from_db(DB_FILE_PATH)
        if not available_dates:
            st.error("No data available in database")
            return
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return

    # Initialize session state
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = available_dates[0]

    # Date selection - mobile optimized
    #st.subheader("📅 Select Date")
    
    date_options = {date.strftime("%Y-%m-%d"): date for date in available_dates}
    current_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")
    
    col_label, col_dropdown = st.columns([1, 10])
    with col_label:
        st.subheader("📅 Select Date")
        #st.markdown("**Select Date:**")
    with col_dropdown:
        selected_date_str = st.selectbox(
                ":",
            options=list(date_options.keys()),
            index=list(date_options.keys()).index(current_date_str) if current_date_str in date_options else 0,
            label_visibility="collapsed"
        )
    
    # Update selected date
    selected_date = date_options[selected_date_str]
    if selected_date != st.session_state.selected_date:
        st.session_state.selected_date = selected_date

    # Load data
    nifty_data = load_nifty_data_from_db(st.session_state.selected_date, DB_FILE_PATH)
    options_data = load_options_data_from_db(st.session_state.selected_date, DB_FILE_PATH)

    # Risk info at top for mobile
    risk_value = None
    if nifty_data is not None:
        if 'diff' in nifty_data.columns and not pd.isna(nifty_data['diff'].iloc[0]):
            risk_value = int(nifty_data['diff'].iloc[0])
        
    # Mobile-optimized tabs
    tab1, tab2, tab3 = st.tabs(["📊 Nifty", "📈 Calls", "📉 Puts"])
    
    with tab1:
        if nifty_data is not None:
            fig = create_tradingview_chart(nifty_data, "Nifty 50", True, risk_value, height=500)
            st.plotly_chart(fig, use_container_width=True, 
                           config={'modeBarButtonsToRemove': ['zoom', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'select2d', 'lasso2d'], 'displaylogo': False})
        else:
            st.warning("No Nifty data available")
    
    with tab2:
        if options_data:
            call_options, _ = identify_call_put_options(options_data)
            if call_options:
                for option_name, option_data in call_options.items():
                    # Get risk value for this specific option
                    option_risk = None
                    if 'diff' in option_data.columns and not pd.isna(option_data['diff'].iloc[0]):
                        option_risk = int(option_data['diff'].iloc[0])
                    
                    fig = create_tradingview_chart(option_data, option_name, True, option_risk, height=450)
                    st.plotly_chart(fig, use_container_width=True, 
                                  config={'modeBarButtonsToRemove': ['zoom', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'select2d', 'lasso2d'], 'displaylogo': False})
                    st.markdown("---")  # Separator between charts
            else:
                st.info("No call options available")
        else:
            st.info("No options data available")
    
    with tab3:
        if options_data:
            _, put_options = identify_call_put_options(options_data)
            if put_options:
                for option_name, option_data in put_options.items():
                    # Get risk value for this specific option
                    option_risk = None
                    if 'diff' in option_data.columns and not pd.isna(option_data['diff'].iloc[0]):
                        option_risk = int(option_data['diff'].iloc[0])
                    
                    fig = create_tradingview_chart(option_data, option_name, True, option_risk, height=450)
                    st.plotly_chart(fig, use_container_width=True, 
                                  config={'modeBarButtonsToRemove': ['zoom', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'select2d', 'lasso2d'], 'displaylogo': False})
                    st.markdown("---")  # Separator between charts
            else:
                st.info("No put options available")
        else:
            st.info("No options data available")

    # Simple navigation
    st.markdown("---")

    chronological_dates = sorted(available_dates)
    current_index = chronological_dates.index(st.session_state.selected_date)

    col1, col2 = st.columns(2)
    with col1:
        if current_index > 0:
            if st.button("◀ Previous Day", use_container_width=True, 
                        on_click=lambda: st.session_state.update(selected_date=chronological_dates[current_index - 1])):
                pass
        else:
            st.button("◀ Previous Day", disabled=True, use_container_width=True)

    with col2:
        if current_index < len(chronological_dates) - 1:
            if st.button("Next Day ▶", use_container_width=True,
                        on_click=lambda: st.session_state.update(selected_date=chronological_dates[current_index + 1])):
                pass
        else:
            st.button("Next Day ▶", disabled=True, use_container_width=True)

if __name__ == "__main__":
    main()
