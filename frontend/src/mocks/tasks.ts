import type { Classification, Task } from '../types/api'

const DAY = 86_400_000

function daysFromNow(days: number) {
  const date = new Date(Date.now() + days * DAY)
  date.setHours(17, 0, 0, 0)
  return date.toISOString()
}

function businessDaysFromNow(days: number) {
  const date = new Date()
  let remaining = days
  while (remaining > 0) {
    date.setDate(date.getDate() + 1)
    if (date.getDay() !== 0 && date.getDay() !== 6) remaining--
  }
  date.setHours(17, 0, 0, 0)
  return date.toISOString()
}

const processes = {
  P01: 'Đăng ký tài sản dữ liệu',
  P02: 'Xin quyền đọc',
  P04: 'Duyệt nhãn phân loại',
  P11: 'Chia sẻ dữ liệu ra ngoài',
  P16: 'Chứng nhận, phát hành',
} as const

type Seed = { code: string; title: string; process: keyof typeof processes; entity: string; classification: Classification; requester: string; type: 'Approval' | 'Request'; due: string; createdDaysAgo: number }

const seeds: Seed[] = [
  { code: 'REQ-CID-00012', title: 'Phê duyệt: R2 trên V_CUSTOMER_SEGMENT', process: 'P02', entity: 'V_CUSTOMER_SEGMENT', classification: 'C3', requester: 'Nguyễn Văn An', type: 'Approval', due: daysFromNow(-2), createdDaysAgo: 9 },
  { code: 'REQ-CID-00011', title: 'Duyệt nhãn: Nâng cấp cột REVENUE_BAND lên C3', process: 'P04', entity: 'V_CUSTOMER_SEGMENT', classification: 'C3', requester: 'Lê Thị Lan', type: 'Approval', due: businessDaysFromNow(1), createdDaysAgo: 6 },
  { code: 'REQ-CID-00021', title: 'Phê duyệt: R2 trên V_CUSTOMER_PROFILE', process: 'P02', entity: 'V_CUSTOMER_PROFILE', classification: 'C3', requester: 'Phan Văn Tài', type: 'Approval', due: daysFromNow(3), createdDaysAgo: 4 },
  { code: 'REQ-CID-00008', title: 'Duyệt chứng nhận: Chứng nhận customer_journey (Lakehouse)', process: 'P16', entity: 'customer_journey', classification: 'C2', requester: 'Lê Thị Lan', type: 'Request', due: daysFromNow(4), createdDaysAgo: 12 },
  { code: 'REQ-CID-00022', title: 'Phê duyệt: R2 trên V_CUSTOMER_CONSENT', process: 'P02', entity: 'V_CUSTOMER_CONSENT', classification: 'C3', requester: 'Đặng Quốc Việt', type: 'Approval', due: daysFromNow(4), createdDaysAgo: 3 },
  { code: 'REQ-CID-00017', title: 'Phê duyệt: R3 trên V_PASSENGER_PII', process: 'P02', entity: 'V_PASSENGER_PII', classification: 'C4', requester: 'Trần Minh Khoa', type: 'Approval', due: daysFromNow(5), createdDaysAgo: 2 },
  { code: 'REQ-CID-00019', title: 'Đăng ký tài sản: LOYALTY_TIER_HISTORY', process: 'P01', entity: 'LOYALTY_TIER_HISTORY', classification: 'C2', requester: 'Hoàng Thu Trang', type: 'Request', due: daysFromNow(6), createdDaysAgo: 5 },
  { code: 'REQ-CID-00024', title: 'Chia sẻ dữ liệu: V_CUSTOMER_CONTACT cho đối tác Lotusmiles', process: 'P11', entity: 'V_CUSTOMER_CONTACT', classification: 'C4', requester: 'Vũ Đức Minh', type: 'Request', due: daysFromNow(7), createdDaysAgo: 2 },
  { code: 'REQ-CID-00025', title: 'Duyệt nhãn: Gắn nhãn PII cho cột PHONE_NUMBER', process: 'P04', entity: 'CUSTOMER_MASTER', classification: 'C3', requester: 'Nguyễn Thị Hà', type: 'Approval', due: daysFromNow(8), createdDaysAgo: 1 },
  { code: 'REQ-CID-00026', title: 'Đăng ký tài sản: Báo cáo NPS theo chặng bay', process: 'P01', entity: 'nps_by_route', classification: 'C1', requester: 'Bùi Anh Tuấn', type: 'Request', due: daysFromNow(9), createdDaysAgo: 1 },
]

export const mockTasks: Task[] = seeds.map(seed => ({
  id: seed.code.toLowerCase(),
  code: seed.code,
  title: seed.title,
  process: { code: seed.process, name: processes[seed.process] },
  classification: seed.classification,
  type: seed.type,
  status: 'Open',
  assignee: 'pqhung',
  entity: { name: seed.entity },
  created_at: daysFromNow(-seed.createdDaysAgo),
  due_at: seed.due,
  requester: seed.requester,
}))
