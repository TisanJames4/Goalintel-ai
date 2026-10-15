import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import math
import requests
import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(page_title="GoalIntel AI", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container{padding-top:1.1rem;padding-bottom:3rem;max-width:1250px}
[data-testid="stSidebar"]{background:#0c1424}
.hero{padding:1.25rem 1.35rem;border-radius:20px;background:linear-gradient(120deg,#102b36,#14213d 65%,#25204a);border:1px solid #2b4957;margin-bottom:1rem}
.hero h1{margin:0;font-size:2.1rem;letter-spacing:-.04em}.hero p{margin:.4rem 0 0;color:#c5d4e5}
</style>
""", unsafe_allow_html=True)

WAT = ZoneInfo("Africa/Lagos")
API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE = "https://v3.football.api-sports.io"
TRACKER_FILE = "goalintel_results.csv"

def api_get(endpoint, params=None):
    if not API_KEY:
        return None, "API key not configured"
    try:
        r=requests.get(BASE+endpoint,headers={"x-apisports-key":API_KEY},params=params or {},timeout=20)
        if r.status_code!=200: return None,f"Provider returned HTTP {r.status_code}: {r.text[:150]}"
        p=r.json()
        if p.get("errors"): return None,f"Provider error: {p['errors']}"
        return p.get("response",[]),None
    except Exception as e: return None,f"Connection error: {e}"

def local_dt(s):
    try:return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(WAT)
    except Exception:return None

def fixture_rows(items):
    rows=[]
    for x in items or []:
        fx=x.get("fixture",{}); teams=x.get("teams",{}); goals=x.get("goals",{})
        dt=local_dt(fx.get("date",""))
        rows.append({
            "Date":dt.date().isoformat() if dt else "",
            "Kickoff (WAT)":dt.strftime("%a %d %b, %H:%M") if dt else "—",
            "Fixture":f"{teams.get('home',{}).get('name','Home')} vs {teams.get('away',{}).get('name','Away')}",
            "League":x.get("league",{}).get("name","—"),
            "Status":fx.get("status",{}).get("short","—"),
            "Score":f"{goals.get('home') if goals.get('home') is not None else '-'} - {goals.get('away') if goals.get('away') is not None else '-'}",
            "Home goals":goals.get("home"),"Away goals":goals.get("away"),
            "Fixture ID":fx.get("id"),"League ID":x.get("league",{}).get("id")
        })
    return pd.DataFrame(rows)

def poisson_cdf(lam, kmax):
    return sum(math.exp(-lam)*(lam**k)/math.factorial(k) for k in range(kmax+1))

def estimates(home_xg, away_xg):
    total=max(.05,home_xg+away_xg)
    half=total*.45
    return {
        "1st Half Under 2.5 Goals":poisson_cdf(half,2),
        "1st Half Under 0.5 Goals":poisson_cdf(half,0),
        "Full-time Over 1.5 Goals":1-poisson_cdf(total,1),
        "Full-time Under 2.5 Goals":poisson_cdf(total,2),
        "Full-time Under 3.5 Goals":poisson_cdf(total,3),
        "Full-time Under 4.5 Goals":poisson_cdf(total,4)
    }

def load_results():
    try:
        if os.path.exists(TRACKER_FILE):
            return pd.read_csv(TRACKER_FILE).fillna("")
    except Exception:
        pass
    return pd.DataFrame(columns=["Date","Sport","Fixture","Market","Prediction","Estimated probability %","Actual result","Outcome","Source","Notes"])

def save_results(df):
    df.to_csv(TRACKER_FILE,index=False)

def ensure_cols(df):
    cols=["Date","Sport","Fixture","Market","Prediction","Estimated probability %","Actual result","Outcome","Source","Notes"]
    for c in cols:
        if c not in df.columns: df[c]=""
    return df[cols]

st.sidebar.markdown("## ⚽ GoalIntel AI")
page=st.sidebar.radio("Navigate",[
    "Dashboard","Daily Results & Chart","Next-Day Predictions","Next 7 Days",
    "Football Markets","Ice Hockey Markets","Basketball Markets","Live Scores",
    "Research a Match","Prediction Tracker","Data & Settings"
])
st.markdown('<div class="hero"><h1>GoalIntel <span style="color:#71e1b1">AI</span></h1><p>Market-by-market research · daily results · probability tracking</p></div>',unsafe_allow_html=True)
if not API_KEY:
    st.info("Demo mode: live football fixtures and scores require a privately configured API-Football key.")
else:
    st.caption("Football provider: API-Football · display timezone: Nigeria (WAT).")

if "results_df" not in st.session_state:
    st.session_state["results_df"]=ensure_cols(load_results())

def result_data():
    return ensure_cols(st.session_state["results_df"].copy())

def save_result_data(df):
    st.session_state["results_df"]=ensure_cols(df)
    try: save_results(st.session_state["results_df"])
    except Exception: pass

def get_fixture_day(day):
    return api_get("/fixtures",{"date":day.isoformat(),"timezone":"Africa/Lagos"})

def show_daily_chart(df, day):
    d=df[df["Date"].astype(str)==day.isoformat()] if not df.empty else df
    settled=d[d["Outcome"].astype(str).str.lower().isin(["win","lost","loss"])] if not d.empty else d
    wins=(settled["Outcome"].astype(str).str.lower()=="win").sum() if not settled.empty else 0
    losses=settled["Outcome"].astype(str).str.lower().isin(["lost","loss"]).sum() if not settled.empty else 0
    total=wins+losses
    win_pct=(wins/total*100) if total else 0
    loss_pct=(losses/total*100) if total else 0
    a,b,c=st.columns(3)
    a.metric("Wins",int(wins))
    b.metric("Lost",int(losses))
    c.metric("Settled picks",int(total))
    chart=pd.DataFrame({"Outcome":["Wins","Lost"],"Percentage":[win_pct,loss_pct]}).set_index("Outcome")
    st.bar_chart(chart, y="Percentage", height=220)
    st.caption(f"{day.strftime('%A, %d %B %Y')} · Win rate {win_pct:.1f}% · Loss rate {loss_pct:.1f}%")
    if total==0: st.info("No settled predictions recorded for this date yet. The chart will populate after results are entered.")

if page=="Dashboard":
    st.subheader("Your workspace")
    a,b,c=st.columns(3)
    a.metric("Sports sections","3","Football · Ice hockey · Basketball")
    b.metric("Fixture scan","Next 7 days","Daily date-based scan")
    c.metric("Result history","3 days","Two previous days + today / next day")
    st.write("Choose a market from the sidebar. Each market has its own page and probability filter.")
    st.warning("Probabilities are estimates, not guarantees. Daily charts use recorded, settled outcomes—not predictions.")
    st.markdown("#### Daily performance preview")
    res=result_data()
    for d in [date.today()-timedelta(days=2),date.today()-timedelta(days=1),date.today()]:
        with st.expander(d.strftime("%A %d %B"),expanded=(d==date.today())):
            show_daily_chart(res,d)

elif page=="Daily Results & Chart":
    st.subheader("Previous days — wins and losses")
    res=result_data()
    today=date.today()
    days=[today-timedelta(days=2),today-timedelta(days=1),today]
    labels=["Day before yesterday","Yesterday","Today"]
    for d,label in zip(days,labels):
        st.markdown(f"### {label} · {d.strftime('%d %b %Y')}")
        show_daily_chart(res,d)
        subset=res[res["Date"].astype(str)==d.isoformat()]
        if not subset.empty:
            st.dataframe(subset[["Sport","Fixture","Market","Prediction","Estimated probability %","Actual result","Outcome"]],use_container_width=True,hide_index=True)
    st.markdown("### Record a settled result")
    with st.form("settle_result"):
        d=st.date_input("Prediction date",value=today)
        fixture=st.text_input("Fixture")
        sport=st.selectbox("Sport",["Football","Ice hockey","Basketball"])
        market=st.text_input("Market type")
        prediction=st.text_input("Prediction")
        prob=st.number_input("Estimated probability (%)",min_value=0,max_value=100,value=80)
        actual=st.text_input("Actual score/result")
        outcome=st.selectbox("Outcome",["Win","Lost"])
        source=st.text_input("Source (optional)")
        notes=st.text_area("Notes (optional)")
        submitted=st.form_submit_button("Save settled result",type="primary",use_container_width=True)
    if submitted:
        new=pd.DataFrame([{"Date":d.isoformat(),"Sport":sport,"Fixture":fixture,"Market":market,"Prediction":prediction,"Estimated probability %":prob,"Actual result":actual,"Outcome":outcome,"Source":source,"Notes":notes}])
        save_result_data(pd.concat([res,new],ignore_index=True))
        st.success("Result saved. Daily chart updated.")
        st.rerun()
    st.download_button("Download all recorded results (CSV)",res.to_csv(index=False).encode(), "goalintel_daily_results.csv","text/csv")

elif page=="Next-Day Predictions":
    tomorrow=date.today()+timedelta(days=1)
    st.subheader(f"Next-day predictions · {tomorrow.strftime('%A, %d %B %Y')}")
    st.write("This view is reserved for tomorrow's fixtures and market-specific estimates. Predictions should be saved before kickoff, then settled after the match.")
    if st.button("Scan tomorrow's football fixtures",type="primary",use_container_width=True):
        items,err=get_fixture_day(tomorrow)
        if err: st.error(err)
        else:
            df=fixture_rows(items)
            st.session_state["tomorrow_fixtures"]=df
            st.session_state["tomorrow_scanned"]=datetime.now(WAT).strftime("%H:%M WAT")
    if "tomorrow_fixtures" in st.session_state:
        df=st.session_state["tomorrow_fixtures"]
        st.caption("Last scan: "+st.session_state.get("tomorrow_scanned","—"))
        if df.empty: st.info("No fixtures returned for tomorrow.")
        else:
            st.dataframe(df.drop(columns=["Home goals","Away goals","Fixture ID","League ID"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("Download tomorrow's fixtures",df.to_csv(index=False).encode(),"goalintel_tomorrow.csv","text/csv")
    st.info("Automated pick recommendations require verified team averages and a market-specific model. This starter does not fabricate predictions where those inputs are missing.")

elif page=="Next 7 Days":
    st.subheader("Next 7 days — fixture scanner")
    start=st.date_input("Start date",value=date.today(),key="week_start")
    end=st.date_input("End date",value=date.today()+timedelta(days=6),key="week_end")
    sport=st.selectbox("Sport to scan",["Football","Ice hockey","Basketball"])
    if end<start: st.error("End date must be on or after start date.")
    elif sport!="Football": st.info(f"{sport} requires its own connected data provider before fixture scanning can work.")
    elif st.button("Scan fixture dates",type="primary",use_container_width=True):
        items=[]; errors=[]; total_days=(end-start).days+1; prog=st.progress(0)
        for i in range(total_days):
            day=start+timedelta(days=i); one,err=get_fixture_day(day)
            if err: errors.append(f"{day.isoformat()}: {err}")
            else: items.extend(one)
            prog.progress((i+1)/total_days)
        df=fixture_rows(items); st.session_state["week_fixtures"]=df
        if errors: st.warning("Some dates could not be loaded: "+"; ".join(errors[:3]))
    if "week_fixtures" in st.session_state:
        df=st.session_state["week_fixtures"]
        search=st.text_input("Search fixture or league")
        if search: df=df[df.apply(lambda r:search.lower() in " ".join(map(str,r.values)).lower(),axis=1)]
        st.metric("Fixtures found",len(df))
        st.dataframe(df.drop(columns=["Home goals","Away goals","Fixture ID","League ID"],errors="ignore"),use_container_width=True,hide_index=True)
        st.download_button("Export fixtures CSV",df.to_csv(index=False).encode(),"goalintel_week.csv","text/csv")

elif page=="Football Markets":
    st.subheader("Football — select one market")
    market=st.selectbox("Market type",["1st Half Under 2.5 Goals","1st Half Under 0.5 Goals","Full-time Over 1.5 Goals","Full-time Under 2.5 Goals","Full-time Under 3.5 Goals","Full-time Under 4.5 Goals","Second-half Over 0.5 Goals","Team Over 0.5 Goals","Double Chance (1X / X2 / 12)","Total Shots","Total Shots on Target","Total Corners","1st Half Corners"])
    threshold=st.slider("Minimum estimated probability",50,95,80,5)
    st.markdown(f"### {market}")
    st.caption("This screen only covers the selected market. Other markets are kept separate.")
    if market in ["1st Half Under 2.5 Goals","1st Half Under 0.5 Goals","Full-time Over 1.5 Goals","Full-time Under 2.5 Goals","Full-time Under 3.5 Goals","Full-time Under 4.5 Goals"]:
        x,y=st.columns(2)
        home=x.number_input("Home expected goals (manual baseline)",0.0,6.0,1.25,.05)
        away=y.number_input("Away expected goals (manual baseline)",0.0,6.0,1.05,.05)
        p=estimates(home,away)[market]
        st.metric("Baseline estimated probability",f"{p*100:.1f}%")
        st.caption("Manual assumptions are not verified statistics. First-half estimates use a rough goal-share assumption and are not calibrated.")
        st.write("Filter result:", "Passes threshold" if p*100>=threshold else "Below threshold")
    else:
        st.info("This market's estimator remains inactive until the matching data fields and historical validation are connected.")
    st.markdown("#### Research checklist")
    st.write("Recent form · home/away split · half-time trends · league profile · verified lineups/context · backtest sample size")

elif page=="Ice Hockey Markets":
    st.subheader("Ice hockey")
    market=st.selectbox("Market type",["Full-game total goals Over/Under","Team total goals Over/Under","1st Period Over/Under"])
    threshold=st.slider("Minimum estimated probability",50,95,80,5,key="hk")
    st.info("Dedicated hockey data feed and historical validation are needed before fixture scans or estimates are activated.")
    st.write("Selected market:",market,"· Threshold:",threshold,"%")

elif page=="Basketball Markets":
    st.subheader("Basketball")
    market=st.selectbox("Market type",["Full-game total points Over/Under","Home team total points","Away team total points","1st-half total points Over/Under","Quarter total points Over/Under"])
    threshold=st.slider("Minimum estimated probability",50,95,80,5,key="bk")
    st.info("Dedicated basketball data, pace/team efficiency, player availability and historical validation are needed before predictions are activated.")
    st.write("Selected market:",market,"· Threshold:",threshold,"%")

elif page=="Live Scores":
    st.subheader("Live football scores")
    refresh=st.selectbox("Auto-refresh",["15 seconds","30 seconds","60 seconds","120 seconds"],index=1)
    if st_autorefresh: st_autorefresh(interval=int(refresh.split()[0])*1000,key="live_refresh")
    items,err=api_get("/fixtures",{"live":"all","timezone":"Africa/Lagos"})
    if err: st.warning(err)
    else:
        df=fixture_rows(items); st.caption("Last fetched "+datetime.now(WAT).strftime("%H:%M:%S WAT"))
        if df.empty: st.info("No live fixtures returned right now.")
        else: st.dataframe(df[["Kickoff (WAT)","Fixture","League","Status","Score"]],use_container_width=True,hide_index=True)

elif page=="Research a Match":
    st.subheader("Save one market prediction")
    with st.form("research"):
        d=st.date_input("Prediction date",value=date.today())
        sport=st.selectbox("Sport",["Football","Ice hockey","Basketball"])
        home=st.text_input("Home / first team")
        away=st.text_input("Away / second team")
        kickoff=st.text_input("Kickoff time (WAT)")
        market=st.text_input("Exact market type")
        prediction=st.text_input("Prediction")
        prob=st.number_input("Estimated probability (%)",1,99,80)
        source=st.text_input("Data source")
        notes=st.text_area("Evidence and reasoning")
        submitted=st.form_submit_button("Save prediction",type="primary",use_container_width=True)
    if submitted:
        res=result_data()
        new=pd.DataFrame([{"Date":d.isoformat(),"Sport":sport,"Fixture":f"{home} vs {away}","Market":market,"Prediction":prediction,"Estimated probability %":prob,"Actual result":"","Outcome":"","Source":source,"Notes":notes+" | kickoff WAT: "+kickoff}])
        save_result_data(pd.concat([res,new],ignore_index=True))
        st.success("Prediction saved. Settle it after the match in Daily Results & Chart.")
        st.rerun()

elif page=="Prediction Tracker":
    st.subheader("Prediction history")
    res=result_data()
    if res.empty: st.info("No predictions/results recorded yet.")
    else:
        st.dataframe(res,use_container_width=True,hide_index=True)
        settled=res[res["Outcome"].astype(str).str.lower().isin(["win","lost","loss"])]
        if not settled.empty:
            wins=(settled["Outcome"].astype(str).str.lower()=="win").sum()
            losses=len(settled)-wins
            c1,c2,c3=st.columns(3); c1.metric("Wins",wins); c2.metric("Lost",losses); c3.metric("Observed win rate",f"{wins/len(settled)*100:.1f}%")
        st.download_button("Export tracker CSV",res.to_csv(index=False).encode(),"goalintel_tracker.csv","text/csv")

elif page=="Data & Settings":
    st.subheader("Data sources & status")
    st.write("Football source: API-Football / API-Sports, key configured privately as `API_FOOTBALL_KEY`.")
    st.write("Daily result charts calculate win/loss percentages from results you record. They do not invent missing past results.")
    st.write("Football fixture/live-score hooks are included. Hockey and basketball data connections are not included yet.")
    st.write("Probabilities in this starter are baselines only; a verified historical dataset and calibration are required for trustworthy confidence estimates.")
    st.warning("Never put API keys in public code, screenshots, or chat.")

st.markdown("---")
st.caption("GoalIntel AI · Separate markets · Daily result tracking · Estimates are not guarantees.")
