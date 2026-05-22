import streamlit as st
import pandas as pd
import simplekml
import numpy as np
import re
from PIL import Image, ImageEnhance
import easyocr
import pyproj

# Cấu hình VN2000 Khánh Hòa
VN2000_KH_CALIBRATED = (
    "+proj=tmerc +lat_0=0 +lon_0=108.25 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 "
    "+towgs84=-357.3914,436.3274,-1.4739,0,0,0,0 +units=m +no_defs"
)
WGS84_PROJ4 = "epsg:4326"
transformer = pyproj.Transformer.from_crs(VN2000_KH_CALIBRATED, WGS84_PROJ4, always_xy=True)

st.set_page_config(page_title="VN2000 to KML Pro", layout="wide")

# Hiển thị thông báo bản quyền (An toàn cho Streamlit Cloud)
@st.dialog("⚠️ THÔNG BÁO")
def show_copyright():
    st.warning("Ứng dụng phát triển bởi Nguyễn Ngô Bá Toàn - Chuyên viên Sở Xây dựng Khánh Hòa.")
    st.markdown("Vui lòng sử dụng đúng mục đích công việc chuyên môn, góp ý xin gửi đến: ba.toan987@gmail.com")
    if st.button("Đồng Ý"): st.rerun()

if 'warning_shown' not in st.session_state:
    st.session_state['warning_shown'] = True
    show_copyright()

st.title("📍 Chuyển Đổi VN2000 Sang KML (Khánh Hòa)")
st.markdown("---")

# --- KHU VỰC TẢI DỮ LIỆU ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📷 Nhập từ Hình ảnh (OCR)")
    uploaded_images = st.file_uploader("Tải ảnh bảng tọa độ", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

with col2:
    st.subheader("📂 Nhập từ Excel")
    uploaded_excel = st.file_uploader("Tải file Excel (.xlsx, .xls)", type=['xlsx', 'xls'])

all_detected_points = []

# --- XỬ LÝ EXCEL ---
if uploaded_excel:
    try:
        df_excel = pd.read_excel(uploaded_excel)
        st.success(f"Đã đọc file Excel: {uploaded_excel.name}")
        
        # Giao diện chọn cột nếu hệ thống không tự tìm được
        with st.expander("Cấu hình cột Excel", expanded=False):
            col_name = st.selectbox("Cột Tên Điểm", df_excel.columns, index=0)
            col_x = st.selectbox("Cột Tọa độ X (Northing)", df_excel.columns, index=min(1, len(df_excel.columns)-1))
            col_y = st.selectbox("Cột Tọa độ Y (Easting)", df_excel.columns, index=min(2, len(df_excel.columns)-1))
        
        for _, row in df_excel.iterrows():
            all_detected_points.append({
                "Tên Điểm": str(row[col_name]),
                "X (Northing)": str(row[col_x]),
                "Y (Easting)": str(row[col_y]),
                "Nguồn": "Excel"
            })
    except Exception as e:
        st.error(f"Lỗi khi đọc file Excel: {e}")

# --- XỬ LÝ HÌNH ẢNH (Giữ nguyên logic cũ của bạn) ---
if uploaded_images:
    reader = easyocr.Reader(['vi', 'en'], gpu=False)
    for file in uploaded_images:
        # (Logic OCR của bạn ở đây...)
        # Lưu ý: Khi append vào all_detected_points, hãy thêm trường "Nguồn": "Hình ảnh"
        pass

# --- BẢNG BIÊN TẬP DỮ LIỆU CHUNG ---
st.markdown("---")
if all_detected_points:
    st.header("📋 Danh Sách Điểm Tổng Hợp")
    df_final = pd.DataFrame(all_detected_points)
    edited_df = st.data_editor(df_final, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 XUẤT FILE KML", type="primary"):
        kml = simplekml.Kml()
        coords = []
        for _, row in edited_df.iterrows():
            try:
                lon, lat = transformer.transform(float(row['Y (Easting)']), float(row['X (Northing)']))
                kml.newpoint(name=row['Tên Điểm'], coords=[(lon, lat)])
                coords.append((lon, lat))
            except: continue
            
        if len(coords) >= 3:
            poly = kml.newpolygon(name="Ranh giới thửa đất")
            if coords[0] != coords[-1]: coords.append(coords[0])
            poly.outerboundaryis = coords
            
        st.download_button("💾 Tải File .KML", data=kml.kml(), file_name="Ket_qua_KML.kml")
