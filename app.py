import streamlit as st
import pandas as pd
import simplekml
import numpy as np
import re
from PIL import Image, ImageEnhance
import easyocr
import pyproj

# Chuỗi cấu hình VN2000 Khánh Hòa (KTT 108.25, Múi 3 độ) đã tối ưu
VN2000_KH_CALIBRATED = (
    "+proj=tmerc +lat_0=0 +lon_0=108.25 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 "
    "+towgs84=-357.3914,436.3274,-1.4739,0,0,0,0 +units=m +no_defs"
)
WGS84_PROJ4 = "epsg:4326"

transformer = pyproj.Transformer.from_crs(VN2000_KH_CALIBRATED, WGS84_PROJ4, always_xy=True)

# 1. Cấu hình giao diện Streamlit trước
st.set_page_config(page_title="VN2000 sang KML - Tác giả: Nguyễn Ngô Bá Toàn", layout="wide")

# ==============================================================================
# THIẾT LẬP CẢNH BÁO BẢN QUYỀN CHUẨN WEB (Tương thích Windows, Linux, Điện thoại)
# ==============================================================================
@st.dialog("⚠️ CẢNH BÁO BẢN QUYỀN ỨNG DỤNG")
def show_copyright_warning():
    st.warning("⚠️ **THÔNG BÁO QUAN TRỌNG VỀ BẢN QUYỀN MÃ NGUỒN**")
    st.markdown("""
    Chương trình này được nghiên cứu và phát triển bởi:
    
    **NGUYỄN NGÔ BÁ TOÀN**
    *Chuyên viên Sở Xây dựng tỉnh Khánh Hòa.*
    
    *Góp ý xin gửi về Email: Ba.toan987@gmail.com*
    """)
    if st.button("Tôi Đã Hiểu & Đồng Ý", type="primary"):
        st.rerun()

# Kiểm tra nếu chưa hiển thị cảnh báo trong phiên làm việc hiện tại thì tự động bật Pop-up lên
if 'warning_shown' not in st.session_state:
    st.session_state['warning_shown'] = True
    show_copyright_warning()
# ==============================================================================

st.title("📍 Ứng Dụng Xuất Tọa Độ VN2000 Sang KML (Khánh Hòa)")
st.caption("Chương trình phát triển bởi: Nguyễn Ngô Bá Toàn - Chuyên viên Sở Xây dựng Khánh Hòa")
st.markdown("---")


# ==============================================================================

# Chuỗi cấu hình VN2000 Khánh Hòa (KTT 108.25, Múi 3 độ) đã tối ưu
VN2000_KH_CALIBRATED = (
    "+proj=tmerc +lat_0=0 +lon_0=108.25 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 "
    "+towgs84=-357.3914,436.3274,-1.4739,0,0,0,0 +units=m +no_defs"
)
WGS84_PROJ4 = "epsg:4326"

transformer = pyproj.Transformer.from_crs(VN2000_KH_CALIBRATED, WGS84_PROJ4, always_xy=True)

st.set_page_config(page_title="VN2000 sang KML - Tác giả: Nguyễn Ngô Bá Toàn", layout="wide")
st.title("📍 Ứng Dụng Xuất Tọa Độ VN2000 Sang KML (Khánh Hòa)")
st.caption("Chương trình phát triển bởi: Nguyễn Ngô Bá Toàn - Chuyên viên Sở Xây dựng Khánh Hòa")
st.markdown("---")

@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['vi', 'en'], gpu=False)

with st.spinner("Đang khởi động bộ xử lý hình ảnh OCR nâng cao..."):
    reader = load_ocr_model()

def clean_num_str(text):
    cleaned = re.sub(r'[^\d.,]', '', text)
    cleaned = cleaned.replace(',', '.')
    return cleaned

def preprocess_image(pil_img):
    gray_img = pil_img.convert('L')
    enhancer = ImageEnhance.Contrast(gray_img)
    enhanced_img = enhancer.enhance(3.0)  
    return enhanced_img

uploaded_files = st.file_uploader("Tải lên các hình ảnh bảng tọa độ (Tối đa 10 ảnh)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

all_detected_points = []

if uploaded_files:
    if len(uploaded_files) > 10:
        st.error("🚨 Vui lòng chỉ chọn tối đa 10 hình ảnh cùng lúc.")
    else:
        for idx, file in enumerate(uploaded_files):
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
                        img_slice, 
                        detail=1, 
                        paragraph=False, 
                        contrast_ths=0.1, 
                        low_text=0.25,
                        text_threshold=0.6
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
                                        "Nguồn Ảnh": file.name
                                    })
                st.write(f"✅ Bóc tách hoàn tất file ảnh: `{file.name}`")

        st.markdown("---")
        st.header("📋 Bảng Kiểm Tra Dữ Liệu Sau Khi Quét")
        st.success(f"📊 Hệ thống đã tìm thấy tổng cộng: {len(all_detected_points)} điểm mốc hợp lệ!")

        if all_detected_points:
            df = pd.DataFrame(all_detected_points)
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            
            if st.button("🚀 XUẤT FILE KML CHUẨN GOOGLE MAPS", type="primary"):
                kml = simplekml.Kml()
                polygon_coords = []
                
                for _, row in edited_df.iterrows():
                    try:
                        x_coord = float(row['X (Northing)'])
                        y_coord = float(row['Y (Easting)'])
                        lon, lat = transformer.transform(y_coord, x_coord)
                        kml.newpoint(name=str(row['Tên Điểm']), coords=[(lon, lat)])
                        polygon_coords.append((lon, lat))
                    except Exception:
                        continue
                
                if len(polygon_coords) >= 3:
                    if polygon_coords[0] != polygon_coords[-1]:
                        polygon_coords.append(polygon_coords[0])
                    
                    poly = kml.newpolygon(name="Ranh giới thửa đất")
                    poly.outerboundaryis = polygon_coords
                    poly.style.linestyle.color = simplekml.Color.red
                    poly.style.linestyle.width = 3
                    poly.style.polystyle.color = simplekml.Color.changealphaint(40, simplekml.Color.red)
                
                kml_string = kml.kml()
                st.balloons()
                st.download_button(
                    label="💾 TẢI FILE .KML TOÀN BỘ CÁC ĐIỂM",
                    data=kml_string,
                    file_name="Ranh_Gioi_Du_An_Day_Du.kml",
                    mime="application/vnd.google-earth.kml+xml"
                )
