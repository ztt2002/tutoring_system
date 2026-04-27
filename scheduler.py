import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import json
from supabase import create_client, Client

# ========== 粉色可爱风格CSS ==========
st.markdown("""
<style>
    .stApp { background: linear-gradient(145deg, #FFF0F5 0%, #FFE4E8 100%); }
    .main > div { background-color: rgba(255, 245, 250, 0.85); border-radius: 28px; padding: 1rem; box-shadow: 0 8px 20px rgba(255, 105, 180, 0.1); }
    h1, h2, h3, .stMarkdown h1 { color: #D46284 !important; font-family: 'Comic Sans MS', 'Chalkboard SE', 'cursive' !important; font-weight: 600; border-left: 5px solid #FFB6C1; padding-left: 15px; }
    .stButton button { background-color: #FFB7C5 !important; color: white !important; border-radius: 40px !important; border: none !important; padding: 0.5rem 1.5rem !important; font-weight: bold !important; box-shadow: 0 4px 8px #FFD0D8; transition: 0.2s; }
    .stButton button:hover { background-color: #FF9EB0 !important; transform: scale(1.02); }
    input, textarea, .stTextInput>div>div>input, .stSelectbox>div>div { border-radius: 25px !important; border-color: #FFCCD5 !important; background-color: #FFFCFC !important; }
    .dataframe { border-radius: 20px !important; overflow: hidden; }
    .dataframe th { background-color: #FFE0E8 !important; color: #B24C6A !important; }
    .streamlit-expanderHeader { background-color: #FFEFF2 !important; border-radius: 30px !important; color: #D46284 !important; }
    .stAlert { background-color: #FFE4EC !important; border-radius: 20px !important; color: #C25A7A !important; }
    [data-testid="stMetricValue"] { color: #E67A9F !important; font-size: 2rem !important; }
    .cal-table { width: 100%; border-collapse: collapse; background-color: #FFF9FB; border-radius: 20px; overflow: hidden; }
    .cal-table th { background-color: #FFE0E8; color: #B24C6A; padding: 8px; text-align: center; font-size: 1rem; }
    .cal-table td { border: 1px solid #FFCCD5; vertical-align: top; padding: 6px; height: 100px; }
    .cal-day-number { font-weight: bold; font-size: 1rem; color: #D46284; margin-bottom: 3px; }
    .course-tag { display: inline-block; border-radius: 20px; padding: 2px 5px; margin: 1px; font-size: 0.7rem; white-space: nowrap; }
    .daily-income { margin-top: 5px; font-size: 0.75rem; color: #E67A9F; font-weight: bold; border-top: 1px dashed #FFB7C5; padding-top: 3px; text-align: right; }
</style>
""", unsafe_allow_html=True)

st.title("🎀 家教排课统计系统  ✨")

# ---------- Supabase 初始化 ----------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ---------- 数据加载函数 ----------
def load_courses():
    response = supabase.table("courses").select("*").execute()
    data = response.data
    if not data:
        return pd.DataFrame(columns=["id", "日期", "学生", "科目", "开始时间", "结束时间", "时长(小时)", "课时费(元/小时)", "本次收入"])
    df = pd.DataFrame(data)
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    return df

def save_courses(df):
    # 清空表后批量插入（简单可靠）
    supabase.table("courses").delete().neq("id", 0).execute()
    if df.empty:
        return
    records = df.to_dict(orient="records")
    for rec in records:
        # 移除 id 字段让数据库自动生成
        rec.pop("id", None)
        supabase.table("courses").insert(rec).execute()

def load_students():
    response = supabase.table("students").select("*").execute()
    data = response.data
    if not data:
        return pd.DataFrame(columns=["学生", "科目", "课时费", "每周课表"])
    return pd.DataFrame(data)

def save_students(df):
    supabase.table("students").delete().neq("学生", "").execute()
    if df.empty:
        return
    records = df.to_dict(orient="records")
    for rec in records:
        supabase.table("students").insert(rec).execute()

# ---------- 辅助函数 ----------
def calculate_hours(start, end):
    try:
        start_dt = datetime.strptime(start, "%H:%M")
        end_dt = datetime.strptime(end, "%H:%M")
        delta = (end_dt - start_dt).seconds / 3600
        return round(delta, 1)
    except:
        return 0.0

def get_color_by_subject(subject_text):
    text = str(subject_text)
    if "数学" in text: return "#FFB3B3"
    elif "英语" in text: return "#B3D9FF"
    elif "语文" in text: return "#B3FFB3"
    elif "物理" in text: return "#FFD9B3"
    elif "化学" in text: return "#E6B3FF"
    else: return "#D9D9D9"

def parse_weekly_schedule(schedule_str):
    if pd.isna(schedule_str) or schedule_str == '':
        return {}
    try:
        data = json.loads(schedule_str)
        result = {}
        for day, time_ranges in data.items():
            day = int(day)
            result[day] = []
            for tr in time_ranges:
                start, end = tr.split('-')
                result[day].append((start.strip(), end.strip()))
        return result
    except:
        return {}

def generate_courses_for_student(student_name, student_row, start_date, end_date):
    subject = student_row['科目']
    hourly_rate = student_row['课时费']
    weekly = parse_weekly_schedule(student_row['每周课表'])
    if not weekly:
        return []
    courses = []
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.isoweekday()
        if weekday in weekly:
            for (start_time, end_time) in weekly[weekday]:
                hours = calculate_hours(start_time, end_time)
                income = hours * hourly_rate
                courses.append({
                    "日期": current_date.strftime("%Y-%m-%d"),
                    "学生": student_name,
                    "科目": subject,
                    "开始时间": start_time,
                    "结束时间": end_time,
                    "时长(小时)": hours,
                    "课时费(元/小时)": hourly_rate,
                    "本次收入": income
                })
        current_date += timedelta(days=1)
    return courses

# ---------- 加载数据 ----------
if 'df_courses' not in st.session_state:
    st.session_state.df_courses = load_courses()
if 'df_students' not in st.session_state:
    st.session_state.df_students = load_students()

courses_df = st.session_state.df_courses
students_df = st.session_state.df_students

# ---------- 侧边栏：学生管理 ----------
with st.sidebar:
    st.header("👩‍🎓 学生管理")
    with st.expander("➕ 添加/编辑学生", expanded=True):
        stu_name = st.text_input("学生姓名", key="stu_name_input")
        stu_subject = st.text_input("科目 (例如 高一数学)", key="stu_subject_input")
        stu_rate = st.number_input("课时费 (元/小时)", min_value=0.0, value=100.0, step=10.0, key="stu_rate_input")
        st.markdown("**每周固定课表**")
        weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
        weekday_map = {w:i+1 for i,w in enumerate(weekdays)}
        selected_days = st.multiselect("选择上课星期", weekdays, key="selected_days")
        time_slots = []
        for day in selected_days:
            c1, c2 = st.columns(2)
            with c1:
                start_t = st.text_input(f"{day} 开始时间", "14:00", key=f"start_{day}_add")
            with c2:
                end_t = st.text_input(f"{day} 结束时间", "15:30", key=f"end_{day}_add")
            time_slots.append((weekday_map[day], start_t, end_t))
        if st.button("保存学生"):
            if stu_name and stu_subject:
                schedule_dict = {}
                for d, s, e in time_slots:
                    if s and e:
                        if d not in schedule_dict:
                            schedule_dict[d] = []
                        schedule_dict[d].append(f"{s}-{e}")
                schedule_json = json.dumps(schedule_dict, ensure_ascii=False)
                if stu_name in students_df['学生'].values:
                    students_df.loc[students_df['学生'] == stu_name, ['科目','课时费','每周课表']] = [stu_subject, stu_rate, schedule_json]
                else:
                    new_row = pd.DataFrame([[stu_name, stu_subject, stu_rate, schedule_json]], columns=students_df.columns)
                    students_df = pd.concat([students_df, new_row], ignore_index=True)
                save_students(students_df)
                st.session_state.df_students = students_df
                st.success(f"学生 {stu_name} 已保存")
                st.rerun()
            else:
                st.error("请填写学生姓名和科目")
    st.subheader("📋 学生列表")
    if not students_df.empty:
        for idx, row in students_df.iterrows():
            st.write(f"**{row['学生']}** - {row['科目']} (¥{row['课时费']}/h)")
            if st.button(f"🗑️ 删除 {row['学生']}", key=f"del_stu_{idx}"):
                students_df = students_df[students_df['学生'] != row['学生']]
                save_students(students_df)
                st.session_state.df_students = students_df
                st.success(f"已删除学生 {row['学生']}")
                st.rerun()
    else:
        st.info("暂无学生，请添加")

# ---------- 批量排课 ----------
st.header("📆 快速排课（按周期生成）")
if not students_df.empty:
    col_stu, col_start, col_end = st.columns(3)
    with col_stu:
        selected_student = st.selectbox("选择学生", students_df['学生'].tolist(), key="batch_student")
    with col_start:
        start_date = st.date_input("开始日期", value=datetime.today(), key="batch_start")
    with col_end:
        end_date = st.date_input("结束日期", value=datetime.today() + timedelta(days=30), key="batch_end")
    if st.button("✨ 生成周期课程 ✨"):
        student_row = students_df[students_df['学生'] == selected_student].iloc[0]
        new_courses = generate_courses_for_student(selected_student, student_row, start_date, end_date)
        if new_courses:
            new_df = pd.DataFrame(new_courses)
            max_id = courses_df['id'].max() if not courses_df.empty else 0
            new_df.insert(0, 'id', range(max_id+1, max_id+1+len(new_df)))
            courses_df = pd.concat([courses_df, new_df], ignore_index=True)
            save_courses(courses_df)
            st.session_state.df_courses = courses_df
            st.success(f"成功生成 {len(new_courses)} 节课")
            st.rerun()
        else:
            st.warning("该学生没有设置每周课表或周期内无课程")
else:
    st.info("请先在侧边栏添加学生")

# ---------- 单独添加课程 ----------
with st.expander("➕ 添加单条课程（用于调课/补课）", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        date_single = st.date_input("日期", value=pd.Timestamp.today(), key="single_date")
        student_single = st.text_input("学生姓名", key="single_student")
        subject_single = st.text_input("科目", key="single_subject")
    with c2:
        start_single = st.text_input("开始时间", "14:00", key="single_start")
        end_single = st.text_input("结束时间", "15:30", key="single_end")
    with c3:
        rate_single = st.number_input("课时费", min_value=0.0, value=100.0, step=10.0, key="single_rate")
    if st.button("➕ 添加单条课程"):
        if student_single and subject_single:
            hours = calculate_hours(start_single, end_single)
            if hours <= 0:
                st.error("时间格式错误或结束时间不晚于开始时间")
            else:
                income = hours * rate_single
                new_id = courses_df['id'].max() + 1 if not courses_df.empty else 1
                new_row = pd.DataFrame([{
                    'id': new_id,
                    "日期": date_single.strftime("%Y-%m-%d"),
                    "学生": student_single,
                    "科目": subject_single,
                    "开始时间": start_single,
                    "结束时间": end_single,
                    "时长(小时)": hours,
                    "课时费(元/小时)": rate_single,
                    "本次收入": income
                }])
                courses_df = pd.concat([courses_df, new_row], ignore_index=True)
                save_courses(courses_df)
                st.session_state.df_courses = courses_df
                st.success("添加成功")
                st.rerun()
        else:
            st.error("请填写学生和科目")

# ---------- 编辑课程 ----------
st.header("✏️ 编辑课程")
if not courses_df.empty:
    edit_id = st.selectbox("选择要编辑的课程ID", courses_df['id'].tolist(), key="edit_id")
    original = courses_df[courses_df['id'] == edit_id].iloc[0]
    with st.expander(f"编辑课程 ID {edit_id}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            new_date = st.date_input("新日期", value=pd.to_datetime(original['日期']), key="edit_date")
            new_student = st.text_input("学生", value=original['学生'], key="edit_student")
            new_subject = st.text_input("科目", value=original['科目'], key="edit_subject")
        with col2:
            new_start = st.text_input("开始时间", value=original['开始时间'], key="edit_start")
            new_end = st.text_input("结束时间", value=original['结束时间'], key="edit_end")
            new_rate = st.number_input("课时费(元/小时)", value=float(original['课时费(元/小时)']), step=10.0, key="edit_rate")
        if st.button("保存修改"):
            hours = calculate_hours(new_start, new_end)
            if hours <= 0:
                st.error("时间错误")
            else:
                income = hours * new_rate
                courses_df.loc[courses_df['id'] == edit_id, ['日期','学生','科目','开始时间','结束时间','时长(小时)','课时费(元/小时)','本次收入']] = [
                    new_date.strftime("%Y-%m-%d"), new_student, new_subject, new_start, new_end, hours, new_rate, income
                ]
                save_courses(courses_df)
                st.session_state.df_courses = courses_df
                st.success("课程已更新")
                st.rerun()
else:
    st.info("暂无课程，无法编辑")

# ---------- 删除课程 ----------
st.header("🗑️ 删除课程")
if not courses_df.empty:
    del_id = st.selectbox("选择要删除的课程ID", courses_df['id'].tolist(), key="del_id")
    if st.button("确认删除"):
        courses_df = courses_df[courses_df['id'] != del_id]
        save_courses(courses_df)
        st.session_state.df_courses = courses_df
        st.success(f"已删除ID {del_id}")
        st.rerun()
else:
    st.info("暂无课程可删除")

# ---------- 收入统计 ----------
st.header("💰 收入统计")
period = st.selectbox("统计周期", ["本月","最近3个月","最近6个月","最近1年","全部","自定义"], key="period")
end_date = datetime.today()
if period == "本月":
    start_date = end_date.replace(day=1)
elif period == "最近3个月":
    start_date = end_date - timedelta(days=90)
elif period == "最近6个月":
    start_date = end_date - timedelta(days=180)
elif period == "最近1年":
    start_date = end_date - timedelta(days=365)
elif period == "全部":
    start_date = datetime(2000,1,1)
else:
    c_s, c_e = st.columns(2)
    with c_s:
        start_date = st.date_input("开始日期", value=end_date - timedelta(days=30), key="custom_start")
    with c_e:
        end_date = st.date_input("结束日期", value=end_date, key="custom_end")
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

if period != "自定义":
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

courses_df['日期_dt'] = pd.to_datetime(courses_df['日期'])
mask = (courses_df['日期_dt'] >= start_date) & (courses_df['日期_dt'] <= end_date)
filtered = courses_df[mask]
total_income = filtered['本次收入'].sum()
total_hours = filtered['时长(小时)'].sum()
st.metric(f"📆 {period} 总收入", f"{total_income:.0f} 元")
st.caption(f"总课时: {total_hours:.1f} 小时")

# ---------- 月历视图 ----------
st.header("📅 课程月历")
today = datetime.today()
col_y, col_m = st.columns(2)
with col_y:
    year = st.number_input("年份", min_value=2020, max_value=2030, value=today.year, step=1, key="year")
with col_m:
    month = st.number_input("月份", min_value=1, max_value=12, value=today.month, step=1, key="month")

first_day = datetime(year, month, 1)
last_day = datetime(year, month, calendar.monthrange(year, month)[1])
df_month = courses_df[(pd.to_datetime(courses_df["日期"]) >= first_day) & (pd.to_datetime(courses_df["日期"]) <= last_day)]

cal = calendar.monthcalendar(year, month)
days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

html_cal = '<table class="cal-table" style="width:100%; border-collapse: collapse;">'
html_cal += '<thead><tr>' + ''.join(f'<th style="background-color:#FFE0E8; padding:8px;">{d}</th>' for d in days_cn) + '</thead>'
html_cal += '<tbody>'
for week in cal:
    html_cal += '<tr>'
    for day in week:
        if day == 0:
            html_cal += '<td style="background-color:#FFF0F5; height:100px; vertical-align:top; padding:6px;">&nbsp;</td>'
        else:
            date_str = f"{year}-{month:02d}-{day:02d}"
            day_courses = df_month[df_month["日期"] == date_str]
            daily_income = day_courses['本次收入'].sum() if not day_courses.empty else 0
            cell = f'<div class="cal-day-number">{day}</div>'
            for _, row in day_courses.iterrows():
                color = get_color_by_subject(row["科目"])
                subj_short = row["科目"][:6] + ".." if len(row["科目"]) > 6 else row["科目"]
                tag = f'<span style="background-color:{color}; display:inline-block; border-radius:20px; padding:2px 6px; margin:2px; font-size:0.7rem;">{row["学生"]}:{subj_short}</span>'
                cell += tag
            if daily_income > 0:
                cell += f'<div class="daily-income">¥{daily_income:.0f}</div>'
            html_cal += f'<td style="height:100px; vertical-align:top; padding:6px; border:1px solid #FFCCD5;">{cell}</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'

st.markdown(html_cal, unsafe_allow_html=True)

# ---------- 课程记录表格 ----------
st.header("📋 所有课程记录")
if courses_df.empty:
    st.info("暂无课程")
else:
    cols_to_show = [c for c in courses_df.columns if c not in ['日期_dt']]
    display_df = courses_df[cols_to_show].sort_values("日期", ascending=False)
    st.dataframe(display_df, use_container_width=True)

# 清理临时列
if '日期_dt' in courses_df.columns:
    courses_df = courses_df.drop(columns=['日期_dt'])
    save_courses(courses_df)
    st.session_state.df_courses = courses_df
