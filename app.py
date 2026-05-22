import streamlit as st
import pandas as pd
import simplekml
import numpy as np
import re
from PIL import Image, ImageEnhance
import easyocr
import pyproj

# ==============================================================================
# 1. CẤU HÌNH HỆ TỌA ĐỘ VN2000 KHÁNH HÒA
# ==============================================================================
VN2000_KH_CALIBRATED = (
    "+proj=tmerc +lat_0=0 +lon_0=108.25 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 "
    "+towgs84=-357.3914,436.3274,-1.4739,0,0,0,0 +units=m +no_defs"
)
WGS84_PROJ4 = "epsg:4326"
transformer = pyproj.Transformer.from_crs(VN2000_KH_CALIBRATED, WGS84_PROJ4, always_xy=True)

# Cấu hình trang Streamlit
st.set_page_config(page_title="VN2000 sang KML - Bản Tối Ưu Đa Nguồn", layout="wide")

# ==============================================================================
# 2. THIẾT LẬP CẢNH BÁO BẢN QUYỀN CHUẨN WEB
# ==============================================================================
@st.dialog("⚠️ THÔNG BÁO BẢN QUYỀN ỨNG DỤNG")
def show_copyright_warning():
    st.warning("⚠️ **THÔNG BÁO QUAN TRỌNG VỀ BẢN QUYỀN MÃ NGUỒN**")
    st.markdown("""
    Chương trình này được nghiên cứu và phát triển bởi chuyên viên Sở Xây dựng tỉnh Khánh Hòa.
    
    *Vui lòng không sao chép, thương mại hóa hoặc phân phối trái phép khi chưa được sự đồng ý của tác giả!*
    """)
    if st.button("Tôi Đã Hiểu & Đồng Ý", type="primary"):
        st.rerun()

if 'warning_shown' not in st.session_state:
    st.session_state['warning_shown'] = True
    show_copyright_warning()

# Tải mô hình AI nhận diện ảnh (Cache để tránh load lại làm chậm app)
@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['vi', 'en'], gpu=False)

# Hàm chuẩn hóa chuỗi số tọa độ
def clean_num_str(text):
    cleaned = re.sub(r'[^\d.,]', '', text)
    cleaned = cleaned.replace(',', '.')
    return cleaned

# Hàm tiền xử lý ảnh tăng độ tương phản giúp AI đọc chính xác hơn
def preprocess_image(pil_img):
    gray_img = pil_img.convert('L')
    enhancer = ImageEnhance.Contrast(gray_img)
    return enhancer.enhance(3.0)

# ==============================================================================
# 3. GIAO DIỆN CHÍNH - KHU VỰC NHẬP DỮ LIỆU ĐA NGUỒN
# ==============================================================================
st.title("📍 Ứng Dụng Xuất Tọa Độ VN2000 Sang KML (Khánh Hòa)")
st.caption("Chương trình hỗ trợ nhập dữ liệu linh hoạt từ File Excel hoặc Hình ảnh chụp bảng tọa độ")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📷 Phương thức 1: Nhập từ Hình ảnh (OCR)")
    uploaded_images = st.file_uploader("Tải lên các hình ảnh bảng tọa độ (Tối đa 10 ảnh)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

with col2:
    st.subheader("📂 Phương thức 2: Nhập từ File Excel")
    uploaded_excel = st.file_uploader("Tải lên file Excel số liệu trắc địa (.xlsx, .xls)", type=['xlsx', 'xls'])

# Danh sách dùng chung để gộp dữ liệu từ cả 2 nguồn
all_detected_points = []

# ==============================================================================
# 4. LUỒNG XỬ LÝ FILE EXCEL (CHẠY ĐỘC LẬP)
# ==============================================================================
if uploaded_excel:
    try:
        df_excel = pd.read_excel(uploaded_excel)
        st.success(f"🟩 Đã tiếp nhận file Excel: `{uploaded_excel.name}`")
        
        # Tự động gợi ý hoặc cho phép người dùng chọn lại cột dữ liệu
        with st.expander("⚙️ Cấu hình liên kết cột Excel", expanded=True):
            col_name = st.selectbox("Chọn cột chứa Tên Điểm / Số hiệu mốc:", df_excel.columns, index=0)
            col_x = st.selectbox("Chọn cột chứa tọa độ X (Northing):", df_excel.columns, index=min(1, len(df_excel.columns)-1))
            col_y = st.selectbox("Chọn cột chứa tọa độ Y (Easting):", df_excel.columns, index=min(2, len(df_excel.columns)-1))
        
        # Trích xuất dữ liệu từ các cột được chọn
        for _, row in df_excel.iterrows():
            val_name = str(row[col_name]).strip()
            val_x = clean_num_str(str(row[col_x]))
            val_y = clean_num_str(str(row[col_y]))
            
            if val_name and val_x and val_y:
                all_detected_points.append({
                    "Tên Điểm": val_name,
                    "X (Northing)": val_x,
                    "Y (Easting)": val_y,
                    "Nguồn dữ liệu": f"Excel ({uploaded_excel.name})"
                })
    except Exception as e:
        st.error(f"🚨 Lỗi cấu trúc tệp Excel không đọc được: {e}")

# ==============================================================================
# 5. LUỒNG XỬ LÝ HÌNH ẢNH OCR (CHẠY ĐỘC LẬP)
# ==============================================================================
if uploaded_images:
    if len(uploaded_images) > 10:
        st.error("🚨 Vui lòng chỉ chọn tối đa 10 hình ảnh cùng lúc.")
    else:
        with st.spinner("Đang khởi động bộ xử lý hình ảnh OCR nâng cao..."):
            reader = load_ocr_model()
            
        for idx, file in enumerate(uploaded_images):
            with st.expander(f"📷 Đang bóc tách dữ liệu nâng cao cho Ảnh {idx+1}: {file.name}", expanded=True):
                orig_img = Image.open(file)
                processed_img = preprocess_image(orig_img)
                img_np = np.array(processed_img)
                h, w = img_np.shape[:2]
                
                st.write("🔍 *Đang chạy thuật toán cắt lớp và phân tích sâu cấu trúc ô bảng...*")
                
                slice_height = 400  
                overlap = 120       
                raw_lines = {}
                y_start = 0
                
                while y_start < h:
                    y_end = min(y_start + slice_height, h)
                    img_slice = img_np[y_start:y_end, :]
                    
                    slice_results = reader.readtext(
                        img_slice, detail=1, paragraph=False, 
                        contrast_ths=0.1, low_text=0.25, text_threshold=0.6
                    )
                    
                    for (bbox, text, prob) in slice_results:
                        if prob > 0.20:  
                            actual_y_center = int((bbox[0][1] + bbox[2][1]) / 2) + y_start
                            actual_x_start = bbox[0][0]
                            
                            matched_line = None
                            for existing_y in raw_lines.keys():
                                if abs(existing_y - actual_y_center) < 10:
                                    matched_line = existing_y
                                    break
                            
                            if matched_line is not None:
                                if not any(text == t for _, t in raw_lines[matched_line]):
                                    raw_lines[matched_line].append((actual_x_start, text))
                            else:
                                raw_lines[actual_y_center] = [(actual_x_start, text)]
                                
                    y_start += (slice_height - overlap)
                
                for y in sorted(raw_lines.keys()):
                    sorted_row = sorted(raw_lines[y], key=lambda x: x[0])
                    row_texts = [item[1] for item in sorted_row]
                    
                    if len(row_texts) >= 3:
                        numbers = [t for t in row_texts if len(re.sub(r'[^\d]', '', t)) >= 5]
                        if len(numbers) >= 2:
                            pt_name = row_texts[0].strip()
                            x_raw = clean_num_str(numbers[0])
                            y_raw = clean_num_str(numbers[1])
                            
                            if pt_name.upper() != 'STT' and not pt_name.upper().startswith('X') and not pt_name.upper().startswith('Y'):
                                if not any(p['Tên Điểm'] == pt_name and p['X (Northing)'] == x_raw for p in all_detected_points):
                                    all_detected_points.append({
                                        "Tên Điểm": pt_name,
                                        "X (Northing)": x_raw,
                                        "Y (Easting)": y_raw,
                                        "Nguồn dữ liệu": f"Ảnh ({file.name})"
                                    })
                st.write(f"✅ Bóc tách hoàn tất file ảnh: `{file.name}`")

# ==============================================================================
# 6. BẢNG BIÊN TẬP VÀ XUẤT FILE KML CHUNG (CHỈ CẦN 1 TRONG 2 CÓ DỮ LIỆU)
# ==============================================================================
if all_detected_points:
    st.markdown("---")
    st.header("📋 Bảng Biên Tập Dữ Liệu Tổng Hợp")
    st.info(f"📊 Hệ thống ghi nhận tổng cộng: **{len(all_detected_points)}** điểm mốc hợp lệ từ các nguồn dữ liệu trên.")
    
    # Chuyển đổi thành DataFrame và hiển thị lên bảng chỉnh sửa trực tiếp (Data Editor)
    df = pd.DataFrame(all_detected_points)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    # Nút bấm xử lý xuất file KML
    if st.button("🚀 XUẤT FILE KML CHUẨN GOOGLE MAPS", type="primary"):
        kml = simplekml.Kml()
        polygon_coords = []
        
        for _, row in edited_df.iterrows():
            try:
                x_coord = float(str(row['X (Northing)']).strip())
                y_coord = float(str(row['Y (Easting)']).strip())
                
                # Chuyển đổi VN2000 sang WGS84
                lon, lat = transformer.transform(y_coord, x_coord)
                
                # Tạo điểm Ghim (Placemark) trên bản đồ
                kml.newpoint(name=str(row['Tên Điểm']), coords=[(lon, lat)])
                polygon_coords.append((lon, lat))
            except Exception:
                continue
        
        # Nếu có từ 3 điểm trở lên, tự động vẽ đường bao khép kín dạng Polygon
        if len(polygon_coords) >= 3:
            if polygon_coords[0] != polygon_coords[-1]:
                polygon_coords.append(polygon_coords[0])
            
            poly = kml.newpolygon(name="Ranh giới thửa đất")
            poly.outerboundaryis = polygon_coords
            poly.style.linestyle.color = simplekml.Color.red
            poly.style.linestyle.width = 3
            poly.style.polystyle.color = simplekml.Color.changealphaint(40, simplekml.Color.red)
        
        # Tạo luồng tải file trực tiếp trên trình duyệt
        kml_string = kml.kml()
        st.balloons()
        st.download_button(
            label="💾 TẢI FILE .KML TOÀN BỘ CÁC ĐIỂM",
            data=kml_string,
            file_name="Ranh_Gioi_Du_An_Tong_Hop.kml",
            mime="application/vnd.google-earth.kml+xml"
        )
