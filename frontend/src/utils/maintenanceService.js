import api from "../api";

export const maintenanceService = {
    getTickets: () => api.get('/tickets/by_org').then(res => res.data),
    createTicket: (ticketData) => api.post('/tickets/create', ticketData).then(res => res.data),
    getAssignableUsers: () => api.get('/users/assignable').then(res => res.data),
    deleteTicket: (ticketId) => api.delete(`/tickets/${ticketId}`).then(res => res.data),
    updateStatus: (ticketId, status) => api.patch(`/tickets/${ticketId}/status`, { status }).then(res => res.data)
};

// add features for updating ticket status and adding logs
// updateTicketStatus: (ticketId, status) => api.patch(`/tickets/${ticketId}`, { status }).then(res => res.data),
// addLog: (ticketId, logText) => api.post(`/tickets/${ticketId}/logs`, { log_text: logText }).then(res => res.data)