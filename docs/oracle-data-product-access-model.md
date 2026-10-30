# Mô hình truy cập Data Product trên Oracle

## Mục tiêu

Người dùng nghiệp vụ và công cụ BI chỉ truy vấn dữ liệu qua **Data Product đã được phê duyệt**. Với Oracle, Data Product được công bố dưới dạng một *security view*. Không cấp quyền truy vấn trực tiếp vào bảng nguồn, Bronze, Silver, Gold, ODS hoặc bảng kỹ thuật.

OpenMetadata (OM) là nơi quản trị metadata, request, phê duyệt và entitlement. Oracle Database là nơi thực thi quyền khi query: kiểm tra role, áp row filter, masking/redaction và ghi audit log. Oracle không gọi OM trong từng câu query.

> `backend/scripts/policy_sync.py` triển khai đồng bộ desired-state từ entitlement đã được duyệt trên OpenMetadata sang Oracle. Script mặc định tắt (`ORACLE_POLICY_SYNC_ENABLED=false`) cho đến khi principal và mapping production được cấu hình.

```text
User/BI/Application
        │ request và được duyệt trên OM
        ▼
Policy-sync service
        │ triển khai policy đã duyệt
        ▼
Oracle Data Product security view
        │ role, VPD, Redaction, audit
        ▼
Oracle data tables
```

## Nguyên tắc truy vấn

1. User request quyền tới **Data Product**, không request trực tiếp bảng Oracle.
2. User chỉ có quyền `SELECT` trên security view/Data Product được công bố; không có `SELECT` trên bảng gốc.
3. Definition của view phải liệt kê cột tường minh; cấm dùng `SELECT *`.
4. Cột mới trên bảng nguồn mặc định không được công bố. Cột chỉ được thêm vào Data Product sau khi phân loại, phê duyệt, cập nhật Data Contract và kiểm thử policy.
5. Quyền query, quyền xem dữ liệu rõ và quyền export là ba quyền độc lập.
6. Dữ liệu chưa phân loại không được công bố cho user. Chỉ Data Steward, Data Custodian và công cụ discovery/classification có quyền tối thiểu để xử lý dữ liệu đó.
7. Table browser của portal chỉ hiển thị asset có `tableType = View` và có liên kết Data Product trong OpenMetadata. Bảng vật lý/bảng nguồn và Materialized View là asset nội bộ; chúng bị loại, kể cả khi gọi API tạo request trực tiếp.

Ví dụ view công bố cho analyst:

```sql
CREATE OR REPLACE VIEW dwh_product.dp_booking_analytics_v AS
SELECT booking_id, flight_date, market, revenue
FROM dwh_core.booking;
```

Nếu bảng `dwh_core.booking` có thêm `phone` hoặc `passport_no`, các cột này không tự xuất hiện trong view trên.

## Các lớp policy trong Oracle

| Nhu cầu | Cơ chế thực thi |
| --- | --- |
| Chỉ công bố một số cột | Security view với danh sách cột tường minh |
| Chỉ xem dữ liệu thuộc đơn vị/thị trường được giao | Oracle VPD/FGAC hoặc điều kiện được kiểm soát trong view |
| Hiển thị PII đã che giấu | Oracle Data Redaction hoặc biểu thức masking trong view |
| Cho phép PII dạng rõ theo ngoại lệ | Restricted view/role riêng; approval riêng; có thời hạn |
| Ghi nhận truy cập | Unified Auditing và log ứng dụng/BI |
| Hết hạn hoặc thu hồi quyền | Revoke role hoặc loại user khỏi role qua policy sync |

Ví dụ entitlement chuẩn:

```text
User: nguyenvana
Data Product: Customer Service Masked
Action: query
Row scope: đơn vị CSKH được giao
Phone: masked
Export: denied
Expiry: 2026-12-31
```

Policy sync sẽ map entitlement này thành role Oracle và quyền `SELECT` trên view phù hợp. Nếu application dùng service account chung, application phải thiết lập trusted application context/client identifier của user thực trước khi query để VPD áp đúng row scope.

## Duyệt và tạo Data Product view

| Bước | Trách nhiệm chính | Kết quả |
| --- | --- | --- |
| 1. Đề xuất | Requester hoặc Data Product Owner | Mục đích, consumer, cột, row scope, loại access, thời hạn |
| 2. Rà soát | Data Steward | Metadata, classification, CDE, cột cần mask, Data Product phù hợp hoặc cần tạo mới |
| 3. Thẩm định kỹ thuật | DGO và Data Custodian | Khả năng triển khai view/VPD/redaction/audit; không trùng Data Product hiện có |
| 4. Phê duyệt | Data Owner; DPO/ATTT khi áp dụng | Data Product definition hoặc access policy được phê duyệt |
| 5. Triển khai | Data Custodian | Migration tạo/sửa view, role, VPD/redaction, audit policy |
| 6. Kiểm thử và công bố | Data Custodian xác nhận; DGO công bố | Test quyền âm/dương đạt; Data Product và version trên OM/Catalog |

Mọi security view công bố cho user, BI, application hoặc service account phải được đăng ký như một Data Product/tài sản dữ liệu có owner, classification, lineage, danh sách cột, version, trạng thái và policy liên quan. View kỹ thuật nội bộ không cung cấp dữ liệu cho consumer không bắt buộc phải công bố như Data Product.

## Cấp quyền và query

```text
User tìm Data Product trên OM
  → gửi request: purpose, action, row scope, expiry, export/unmask nếu có
  → Steward rà soát
  → Owner và các bên kiểm soát phê duyệt theo cấp dữ liệu
  → policy-sync cấp/revoke Oracle role
  → user query security view hoặc sử dụng BI/application đã được cấp
```

Ví dụ cấp quyền Oracle:

```sql
GRANT SELECT ON dwh_product.dp_booking_analytics_v
TO role_revenue_analyst;
GRANT role_revenue_analyst TO user_name;
```

Không thực hiện `GRANT SELECT ON dwh_core.booking TO user_name` cho user nghiệp vụ.

## Policy sync OpenMetadata → Oracle

Chạy `python scripts/policy_sync.py` trong thư mục `backend` theo lịch (ví dụ 5 phút/lần). Mỗi lần chạy script:

1. Phân trang toàn bộ user từ OM, rồi lấy các DataAccessRequest của từng user có trạng thái `Approved` hoặc `Granted`.
2. Chỉ chọn request `READ` chưa hết hạn và chỉ map asset OM qua `ORACLE_POLICY_SYNC_VIEW_MAP`. Mapping là JSON từ OM view FQN (hoặc ID) tới tên `SCHEMA.VIEW` Oracle đã công bố; không có mapping thì không cấp quyền.
3. Kiểm tra object đích trong `ALL_VIEWS`, tạo proxy-client `"om::<OM UUID>"` nếu cần, cấp `CREATE SESSION`, cấu hình `CONNECT THROUGH` cho `ORACLE_PROXY_USER`, rồi `GRANT SELECT` trên view.
4. Lưu các grant do script sở hữu trong bảng `OM_POLICY_SYNC_GRANTS`. Snapshot entitlement hiện tại được so với bảng này; request bị `Revoked`, đổi view/permission, hết hạn, hoặc user không còn trong OM sẽ khiến `REVOKE SELECT` và xoá ledger record ở lần chạy tiếp theo.

Ledger chỉ chứa các grant của policy sync, nên không thu hồi quyền được DBA cấp thủ công. Provisioner phải có `CREATE USER`, `ALTER USER`, `GRANT CREATE SESSION`, quyền `GRANT SELECT` trên các published view và quyền tạo/ghi bảng `OM_POLICY_SYNC_GRANTS`; nó cần đọc được `ALL_USERS` và `ALL_VIEWS`. `ORACLE_PROXY_USER` phải là một Oracle identifier không quote và có thể kết nối bằng proxy authentication.

Ví dụ cấu hình (không đặt credential vào repository):

```dotenv
ORACLE_POLICY_SYNC_ENABLED=true
ORACLE_PROXY_USER=PORTAL_PROXY
ORACLE_POLICY_SYNC_VIEW_MAP={"oracle_service.DWH_PRODUCT.DP_BOOKING_ANALYTICS_V":"DWH_PRODUCT.DP_BOOKING_ANALYTICS_V"}
```

## Ngoại lệ direct table access

Direct table access chỉ dành cho Data Custodian, DBA, ETL/ELT, CDC connector, data-quality/classification scanner hoặc tài khoản vận hành có kiểm soát. Nó không phải đường truy cập tiêu chuẩn cho analyst, CSKH hay BI user.

Một bảng được cấp trực tiếp chỉ có thể được coi là Data Product trong trường hợp ngoại lệ khi bảng đã được phê duyệt để công bố, schema ổn định, không cần policy cột khác nhau theo user và thay đổi schema được kiểm soát bằng Data Contract. Với Oracle, security view vẫn là phương án mặc định an toàn hơn.

## Kiểm thử bắt buộc trước khi công bố

- Role được duyệt query view thành công và chỉ thấy các cột được công bố.
- User không có quyền query bảng gốc.
- Row filter trả đúng phạm vi được duyệt.
- PII hiển thị masked hoặc rõ đúng role/purpose.
- Export bị chặn hoặc có quyền/log riêng theo policy.
- Query vào Data Product restricted có audit record.
- Revoke hoặc expiry làm user mất quyền theo SLA đã quy định.

