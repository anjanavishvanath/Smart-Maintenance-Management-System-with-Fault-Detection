import { useState, useEffect } from "react";
import { maintenanceService } from "../utils/maintenanceService";
import CreateTicketModal from "../components/CreateTicketModal";
import { useAuth } from "../auth/AuthProvider";

export default function MaintenancePage() {
    const [tickets, setTickets] = useState([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const { user } = useAuth();

    const fetchTickets = async () => {
        try {
            const data = await maintenanceService.getTickets();
            setTickets(data);
        } catch (error) {
            console.error("Failed to fetch tickets", error);
        }
    };

    useEffect(() => { fetchTickets(); }, []);

    const getStatusColor = (status) => {
        switch (status) {
            case 'open': return 'badge-danger';
            case 'in_progress': return 'badge-warning';
            case 'resolved': return 'badge-success';
            default: return 'badge-secondary';
        }
    };

    const handleDelete = async (ticketId) => {
        if (window.confirm("Are you sure you want to delete this ticket? This action cannot be undone.")) {
            try {
                await maintenanceService.deleteTicket(ticketId);
                // remove from UI immediately instead of full refresh for better UX
                setTickets(prev => prev.filter(t => t.id !== ticketId));
            } catch (err) {
                console.error("Failed to delete ticket", err);
                alert("Failed to delete ticket.");
            }
        }
    };

    const handleStatusUpdate = async (ticketId, status) => {
        try {
            await maintenanceService.updateStatus(ticketId, status);
            // optimistic UI update
            setTickets(prev => prev.map(t =>
                t.id === ticketId ? { ...t, status } : t
            ));
        } catch (err) {
            console.error(`Failed to update ticket status to ${status}`, err);
            alert(`Failed to update ticket status.`);
        }
    };

    return (
        <div className="container">
            <div className="header-actions">
                <h1>Maintenance Registry</h1>
                <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
                    + New Manual Ticket
                </button>
            </div>

            <div className="grid-view">
                {tickets.map(ticket => (
                    <div key={ticket.id} className="card">
                        <div className="card-header">
                            <span className={`badge ${getStatusColor(ticket.status)}`}>
                                {ticket.status.replace('_', ' ').toUpperCase()}
                            </span>
                            <span className="priority-text">P{ticket.priority}</span>
                        </div>
                        <h3>{ticket.title}</h3>
                        <p className="text-muted">Asset ID: {ticket.asset_id}</p>
                        <p>{ticket.description}</p>
                        <div className="ticket-meta" style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#555' }}>
                            <div><strong>Assigned To:</strong> {ticket.assigned_to_name || 'Unassigned'}</div>
                            <div><strong>Due Date:</strong> {ticket.due_date ? new Date(ticket.due_date).toLocaleDateString() : 'No date set'}</div>
                        </div>
                        <div className="card-footer">
                            <div style={{ display: 'flex', gap: '0.5rem', width: '100%' }}>
                                {/* ACTION FOR ASSIGNEE: Mark as Resolved */}
                                {(ticket.status === 'open' || ticket.status === 'in_progress') &&
                                    ticket.assigned_to === user?.id && (
                                        <button
                                            className="btn btn-sm btn-success"
                                            onClick={() => handleStatusUpdate(ticket.id, 'resolved')}
                                        >
                                            Mark Resolved
                                        </button>
                                    )}

                                {/* ACTION FOR CREATOR: Verify and Close */}
                                {ticket.status === 'resolved' && ticket.created_by === user?.id && (
                                    <button
                                        className="btn btn-sm btn-primary"
                                        onClick={() => handleStatusUpdate(ticket.id, 'closed')}
                                    >
                                        Verify & Close
                                    </button>
                                )}

                                {/* DELETE ACTION: Only for Creator */}
                                {ticket.created_by === user?.id && ticket.status !== 'closed' && (
                                    <button
                                        className="btn btn-sm"
                                        style={{ backgroundColor: '#ff4d4d', color: '#fff' }}
                                        onClick={() => handleDelete(ticket.id)}
                                    >
                                        Delete
                                    </button>
                                )}
                                <button className="btn btn-sm btn-outline">View</button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {isModalOpen && (
                <CreateTicketModal
                    onClose={() => setIsModalOpen(false)}
                    onSuccess={() => { setIsModalOpen(false); fetchTickets(); }}
                />
            )}
        </div>
    );
}