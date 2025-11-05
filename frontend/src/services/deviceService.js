import api from "../api";

export const deviceService = {
  listDevices: (limit = 100) => api.get(`/devices?limit=${limit}`).then(r => r.data),
  getDevice: (deviceId) => api.get(`/devices/${deviceId}`).then(r => r.data),
  provisionDevice: ({ device_id, claim_token, mac, fw_version }) =>
    api.post("/devices/provision", { device_id, claim_token, mac, fw_version }).then(r => r.data),
  getReadings: (deviceId, limit = 50) =>
    api.get(`/devices/${deviceId}/readings?limit=${limit}`).then(r => r.data)
};
