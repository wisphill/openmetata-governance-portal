import type { Me } from '../types/api'

export const mockMe: Me = {
  identity: { id: 'u-pqhung', username: 'pqhung', display_name: 'Phạm Quốc Hùng', email: 'pqhung@vietnamairlines.com', title: 'Trưởng ban' },
  teams: [{ id: 't-cid', name: 'CID', displayName: 'Ban Khách hàng (CID)' }],
  roles: {
    direct: [{ id: 'r-do-cid', name: 'DataOwnerCID', displayName: 'Data Owner domain CID' }],
    inherited: [{ id: 'r-consumer', name: 'DataConsumer', displayName: 'Data Consumer' }],
  },
  policies: [{ id: 'p-owner', name: 'DataOwnerPolicy' }, { id: 'p-consumer', name: 'DataConsumerPolicy' }],
  is_admin: false,
  source: 'openmetadata',
}
