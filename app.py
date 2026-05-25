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
st.set_page_config(page_title="VN2000 sang KML - Khóa Nhập Đồng Thời", layout="wide")

# ==============================================================================
# 2. THIẾT LẬP CẢNH BÁO BẢN QUYỀN CHUẨN WEB
# ==============================================================================
@st.dialog("⚠️")
def show_copyright_warning():
    st.warning("**THÔNG BÁO**")
    st.markdown("""
    Chương trình này được nghiên cứu và phát triển bởi Bá Toàn chuyên viên Sở Xây dựng tỉnh Khánh Hòa.
    
    *Vui lòng góp ý đến: Ba.toan987@gmail.com!*
    """)
    if st.button("Tôi Đã Hiểu & Đồng Ý", type="primary"):
        st.rerun()

if 'warning_shown' not in st.session_state:
    st.session_state['warning_shown'] = True
    show_copyright_warning()

# Tải mô hình AI nhận diện ảnh (Cache để tránh load lại)
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
# 3. GIAO DIỆN CHÍNH - BỘ CHỌN PHƯƠNG THỨC ĐỘC QUYỀN
# ==============================================================================
st.title("📍 Ứng Dụng Xuất Tọa Độ VN2000 Sang KML (Khánh Hòa)")
st.caption("Hệ thống đã khóa tính năng nhập đồng thời - Vui lòng chọn 1 trong 2 phương thức dưới đây")
st.markdown("---")

# Bộ nút bấm chọn nguồn dữ liệu (Chỉ được chọn 1 trong 2)
input_method = st.radio(
    "👉 **CHỌN NGUỒN DỮ LIỆU ĐẦU VÀO:**",
    ["📂 Nhập từ File Excel (.xlsx, .xls)", "📷 Nhập từ Hình ảnh (Quét OCR)"],
    index=0,
    horizontal=True
)

# Danh sách dùng chung để lưu dữ liệu cuối cùng
all_detected_points = []

st.markdown("---")

# ==============================================================================
# 4. LUỒNG XỬ LÝ FILE EXCEL (CHỈ HIỆN KHI ĐƯỢC CHỌN)
# ==============================================================================
if input_method == "📂 Nhập từ File Excel (.xlsx, .xls)":
    st.subheader("📂 Khu vực tải lên File Excel")
    uploaded_excel = st.file_uploader("Tải lên file Excel số liệu trắc địa", type=['xlsx', 'xls'])
    
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
                        "Nguồn dữ liệu": "File Excel"
                    })
        except Exception as e:
            st.error(f"🚨 Lỗi cấu trúc tệp Excel không đọc được: {e}")

# ==============================================================================
# ==============================================================================
# 5. LUỒNG XỬ LÝ HÌNH ẢNH OCR CHUYÊN DỤNG (ĐÃ KHỬ NHIỄU ĐƯỜNG ĐỨT NÉT VÀ LỆCH DÒNG)
# ==============================================================================
else:
    st.subheader("📷 Khu vực tải lên Hình ảnh")
    uploaded_images = st.file_uploader("Tải lên các hình ảnh bảng tọa độ (Tối đa 10 ảnh)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_images:
        if len(uploaded_images) > 10:
            st.error("🚨 Vui lòng chỉ chọn tối đa 10 hình ảnh cùng lúc.")
        else:
            with st.spinner("Đang khởi động bộ xử lý hình ảnh thông minh..."):
                reader = load_ocr_model()
                
            for idx, file in enumerate(uploaded_images):
                with st.expander(f"📷 Đang bóc tách dữ liệu cho Ảnh {idx+1}: {file.name}", expanded=True):
                    orig_img = Image.open(file)
                    processed_img = preprocess_image(orig_img)
                    img_np = np.array(processed_img)
                    
                    st.write("🔍 *Đang bóc tách văn bản và tự động căn chỉnh dòng...*")
                    
                    # Đọc toàn bộ văn bản trên ảnh mà không cắt lát để giữ nguyên ngữ cảnh hàng
                    ocr_results = reader.readtext(img_np, detail=1, paragraph=False)
                    
                    raw_data = []
                    for (bbox, text, prob) in ocr_results:
                        # Khử nhiễu các ký tự sinh ra do đường kẻ đứt nét hoặc chấm mờ
                        clean_text = text.strip()
                        if prob > 0.25 and len(clean_text) > 0 and not re.match(r'^[\s._,-]+$', clean_text):
                            y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                            x_start = bbox[0][0]
                            raw_data.append({'x': x_start, 'y': y_center, 'text': clean_text})
                    
                    if raw_data:
                        # Tạo DataFrame để xử lý nhóm dòng thông minh bằng Pandas
                        df_raw = pd.DataFrame(raw_data)
                        
                        # Sắp xếp theo chiều dọc (y) trước
                        df_raw = df_raw.sort_values(by='y').reset_index(drop=True)
                        
                        # Thuật toán nhóm các phần tử có khoảng cách chiều dọc sát nhau (chấp nhận ảnh nghiêng)
                        df_raw['group'] = (df_raw['y'].diff() > 15).cumsum()
                        
                        # Duyệt qua từng dòng sau khi đã nhóm thành công
                        for group_id, group_df in df_raw.groupby('group'):
                            # Sắp xếp các từ trong cùng một dòng từ trái sang phải
                            sorted_row = group_df.sort_values(by='x')
                            row_texts = sorted_row['text'].tolist()
                            
                            if len(row_texts) >= 3:
                                # Lọc ra các chuỗi có dáng dấp của tọa độ (chứa nhiều hơn 4 chữ số)
                                numbers = [t for t in row_texts if len(re.sub(r'[^\d]', '', t)) >= 5]
                                
                                if len(numbers) >= 2:
                                    pt_name = row_texts[0].strip()
                                    
                                    # Ép lấy 2 cụm số cuối cùng làm X và Y đề phòng text tiêu đề dính vào
                                    x_raw = clean_num_str(numbers[-2])
                                    y_raw = clean_num_str(numbers[-1])
                                    
                                    # Loại bỏ dòng tiêu đề bảng (STT, X, Y, Tên điểm...)
                                    if not any(k in pt_name.upper() for k in ['STT', 'X (', 'Y (', 'NORTH', 'EAST']):
                                        if not any(p['Tên Điểm'] == pt_name and p['X (Northing)'] == x_raw for p in all_detected_points):
                                            all_detected_points.append({
                                                "Tên Điểm": pt_name,
                                                "X (Northing)": x_raw,
                                                "Y (Easting)": y_raw,
                                                "Nguồn dữ liệu": "Hình ảnh OCR"
                                            })
                                            
                    st.write(f"✅ Đã xử lý xong ảnh: `{file.name}`")
# ==============================================================================
# 6. BẢNG BIÊN TẬP VÀ XUẤT FILE KML CHUNG
# ==============================================================================
if all_detected_points:
    st.markdown("---")
    st.header("📋 Bảng Biên Tập Dữ Liệu")
    st.info(f"📊 Hệ thống hiển thị dữ liệu trích xuất từ nguồn: **{input_method}**")
    
    # Hiển thị bảng chỉnh sửa dữ liệu trực tiếp
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
                
                # Tạo điểm ghim bản đồ
                kml.newpoint(name=str(row['Tên Điểm']), coords=[(lon, lat)])
                polygon_coords.append((lon, lat))
            except Exception:
                continue
        
        # Tạo đường bao Polygon khép kín nếu đủ từ 3 điểm trở lên
        if len(polygon_coords) >= 3:
            if polygon_coords[0] != polygon_coords[-1]:
                polygon_coords.append(polygon_coords[0])
            
            poly = kml.newpolygon(name="Ranh giới thửa đất")
            poly.outerboundaryis = polygon_coords
            poly.style.linestyle.color = simplekml.Color.red
            poly.style.linestyle.width = 3
            poly.style.polystyle.color = simplekml.Color.changealphaint(40, simplekml.Color.red)
        
        # Tải file trực tiếp trên trình duyệt
        kml_string = kml.kml()
        st.balloons()
        st.download_button(
            label="💾 TẢI FILE .KML TOÀN BỘ CÁC ĐIỂM",
            data=kml_string,
            file_name="Ket_Qua_Ranh_Gioi_Tọa_Đo.kml",
            mime="application/vnd.google-earth.kml+xml"
        )
