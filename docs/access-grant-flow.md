# Luồng cấp và thu hồi quyền truy cập

Tài liệu này mô tả luồng nghiệp vụ hiện tại của yêu cầu truy cập dữ liệu trong OpenMetadata.

```text
Open → InProgress → Pending → Approved → Granted → Revoked
```

- **Open / InProgress / Pending**: yêu cầu được tạo và chờ người được giao xử lý.
- **Approved**: người xử lý đã phê duyệt yêu cầu.
- **Granted**: quyền truy cập đã được cấp thành công.
- **Revoked**: quyền đã bị thu hồi; đây là trạng thái nghiệp vụ cuối của grant.

Sau khi phê duyệt, hệ thống thực hiện bước cấp quyền Oracle. Nếu bước này lỗi, yêu cầu chuyển sang **Failed** thay vì Granted.

Một số workflow có thêm stage **ManualRevoke** trước Revoked để lưu vết thao tác thu hồi. Cần luôn dùng transition mà OpenMetadata trả về tại thời điểm xử lý.

## Lưu ý về Closed / Cancelled

**Closed** hoặc **Cancelled** chỉ cho biết task đã được đóng hoặc hủy ở mức lifecycle chung; chúng không có nghĩa quyền đã được thu hồi. Chỉ **Revoked** (workflow stage/resolution) xác nhận hành động thu hồi quyền.
