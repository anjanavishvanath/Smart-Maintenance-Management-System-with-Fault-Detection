import api from "../api";

export const deviceService = {
    listDevices: (limit = 100) => api.get(`/devices?limit=${limit}`).then(r => r.data)
}