import api from "../api";

export const deviceService = {
    listDevices: (limit = 100) => api.get(`/devices?limit=${limit}`).then(r => r.data),
    updateName: (deviceId, deviceName) =>
        api.put(`/devices/${deviceId}/name`, { device_name: deviceName }).then(r => r.data),
    deleteDevice: (deviceId) =>
        api.delete(`/devices/${deviceId}`).then(r => r.data),
};

export const assetService = {
    update: (assetId, payload) =>
        api.put(`/assets/${assetId}`, payload).then(r => r.data),
    remove: (assetId) =>
        api.delete(`/assets/${assetId}`).then(r => r.data),
    resetBaseline: (assetId) =>
        api.delete(`/assets/baseline/${assetId}`).then(r => r.data),
};