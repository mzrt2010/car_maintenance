import streamlit as st
from supabase import create_client, Client
from postgrest import ClientOptions
import datetime
import uuid

# --- 1. إعداد الاتصال بـ Supabase ---
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"

@st.cache_resource
def init_supabase() -> Client:
    # إجبار الاتصال على التوجه لسكيمو car_app بشكل افتراضي
    options = ClientOptions(schema="car_app")
    return create_client(SUPABASE_URL, SUPABASE_KEY, options=options)

supabase = init_supabase()

# --- إعدادات الصفحة ---
st.set_page_config(page_title="سجل صيانة السيارات", page_icon="🚗", layout="wide")
st.title("🚗 نظام إدارة وسجل صيانة السيارات")

# --- 2. جلب البيانات من قاعدة البيانات ---
def get_cars():
    # سيبحث تلقائياً داخل جدول cars في سكيمو car_app
    response = supabase.table("cars").select("*").execute()
    return response.data

def get_maintenance_logs(car_id):
    response = supabase.table("maintenance_log").select("*").eq("car_id", car_id).order("maintenance_date", desc=True).execute()
    return response.data

# --- الواجهة البرمجية (Tabs) ---
tab1, tab2, tab3 = st.tabs(["📊 عرض السجلات", "➕ إضافة عملية صيانة", "🚘 إدارة السيارات"])

# ---------------------------------------------------------
# Tab 3: إدارة السيارات (إضافة سيارة جديدة)
# ---------------------------------------------------------
with tab3:
    st.header("إضافة سيارة جديدة")
    with st.form("add_car_form", clear_on_submit=True):
        car_name = st.text_input("اسم/موديل السيارة (مثال: تويوتا كامري 2024)")
        plate_number = st.text_input("رقم اللوحة (اختياري)")
        submit_car = st.form_submit_button("حفظ السيارة")
        
        if submit_car:
            if car_name:
                data = {"car_name": car_name, "plate_number": plate_number}
                supabase.table("cars").insert(data).execute()
                st.success(f"تمت إضافة {car_name} بنجاح!")
                st.rerun()
            else:
                st.error("الرجاء إدخال اسم السيارة.")

# جلب السيارات المتاحة لتغذية القوائم المنسدلة
cars_list = get_cars()
car_options = {car['car_name']: car['id'] for car in cars_list}

# ---------------------------------------------------------
# Tab 2: إضافة عملية صيانة
# ---------------------------------------------------------
with tab2:
    st.header("إضافة سجل صيانة جديد")
    if not car_options:
        st.warning("⚠️ الرجاء إضافة سيارة أولاً من تبويب 'إدارة السيارات'.")
    else:
        with st.form("add_maintenance_form", clear_on_submit=True):
            selected_car_name = st.selectbox("اختر السيارة", list(car_options.keys()))
            car_id = car_options[selected_car_name]
            
            m_date = st.date_input("تاريخ الصيانة", datetime.date.today())
            details = st.text_area("تفاصيل الصيانة (مثال: تغيير زيت المحرك وفلتر)")
            cost = st.number_input("التكلفة (بالعملة المحلية)", min_value=0.0, step=50.0)
            
            uploaded_files = st.file_uploader("إرفاق الفواتير (صور أو PDF)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])
            
            submit_log = st.form_submit_button("حفظ السجل")
            
            if submit_log:
                if details and cost > 0:
                    invoice_urls = []
                    
                    if uploaded_files:
                        for file in uploaded_files:
                            file_extension = file.name.split('.')[-1]
                            unique_filename = f"{uuid.uuid4()}.{file_extension}"
                            
                            try:
                                supabase.storage.from_("invoices").upload(unique_filename, file.read())
                                url_res = supabase.storage.from_("invoices").get_public_url(unique_filename)
                                invoice_urls.append(url_res)
                            except Exception as e:
                                st.error(f"حدث خطأ أثناء رفع الملف {file.name}: {e}")
                    
                    log_data = {
                        "car_id": car_id,
                        "maintenance_date": str(m_date),
                        "details": details,
                        "cost": cost,
                        "invoice_urls": invoice_urls
                    }
                    
                    supabase.table("maintenance_log").insert(log_data).execute()
                    st.success("تم حفظ سجل الصيانة بنجاح!")
                    st.rerun()
                else:
                    st.error("الرجاء ملء تفاصيل الصيانة والتكلفة.")

# ---------------------------------------------------------
# Tab 1: عرض السجلات والفواتير
# ---------------------------------------------------------
with tab1:
    st.header("سجلات الصيانة")
    if not car_options:
        st.info("لا توجد سيارات مضافة حالياً.")
    else:
        view_car_name = st.selectbox("تصفية حسب السيارة", list(car_options.keys()), key="view_filter")
        view_car_id = car_options[view_car_name]
        
        logs = get_maintenance_logs(view_car_id)
        
        if not logs:
            st.info(f"لا توجد سجلات صيانة مضافة لسيارة {view_car_name} بعد.")
        else:
            total_spending = sum(float(log['cost']) for log in logs)
            st.metric(label=f"إجمالي ميزانية الصيانة لـ {view_car_name}", value=f"{total_spending:,.2f}")
            
            st.write("---")
            
            for log in logs:
                with st.container():
                    col1, col2, col3 = st.columns([2, 4, 2])
                    with col1:
                        st.subheader(f"📅 {log['maintenance_date']}")
                    with col2:
                        st.markdown(f"**التفاصيل:** {log['details']}")
                    with col3:
                        st.markdown(f"**التكلفة:** {log['cost']:.2f}")
                    
                    if log.get('invoice_urls'):
                        st.write("**الفواتير المرفقة:**")
                        cols_inv = st.columns(len(log['invoice_urls']))
                        for idx, url in enumerate(log['invoice_urls']):
                            with cols_inv[idx]:
                                st.markdown(f"[📄 فاتورة {idx+1}]({url})", unsafe_allow_html=True)
                                if any(ext in url.lower() for ext in ['jpg', 'jpeg', 'png']):
                                    st.image(url, width=100)
                    st.divider()
